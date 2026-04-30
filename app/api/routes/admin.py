# app/routes/admin.py
import base64
import io
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import pyotp
import qrcode
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.bot.max_messenger import MaxMessengerBot
from app.core.admin_audit import log_login_attempt
from app.core.i18n import install_jinja_i18n
from app.core.media_urls import (
    default_family_slug,
    family_data_path_for_slug,
    normalize_media_url,
)
from app.db.session import get_db
from app.models import (
    AvatarHistory,
    EarlyAccessRequest,
    FamilyAccessSession,
    Memory,
    Person,
    PersonAccessBackupCode,
    PersonAlias,
    PersonI18n,
    Quote,
    Union,
    UnionChild,
)
from app.security import (
    ADMIN_COOKIE_NAME,
    admin_register_login,
    admin_register_logout,
    check_login_rate_limit,
    get_client_ip,
    get_daily_password,
    make_admin_token,
    require_admin,
)
from app.services import create_person_with_i18n, update_person_with_i18n
from app.services.ai_analyzer import ProviderAgnosticAnalyzer
from app.services.family_access_service import (
    clear_backup_codes,
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_backup_code_plain,
    new_totp_provisioning_uri,
    person_family_access_permitted,
    revoke_all_sessions_for_person,
    store_backup_codes,
    verify_totp_code,
)
from app.services.person_alias_service import ALIAS_STATUS, ALIAS_TYPES

BASE_DIR = Path(__file__).resolve().parents[2]
router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)

templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))
install_jinja_i18n(templates)
ALLOWED_ROLES = {"placeholder", "relative", "family_admin", "bot_only"}


def _clean_optional_text(value: object) -> str | None:
    text_value = str(value or "").strip()
    return text_value or None


def _parse_datetime_safe(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    variants = [raw]
    if raw.endswith("Z"):
        variants.append(raw[:-1] + "+00:00")

    for candidate in variants:
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    return None


def _role_filter_key(role: str | None) -> str:
    value = str(role or "").strip().lower()
    mapping = {
        "placeholder": "placeholder",
        "relative": "relative",
        "family_admin": "familyadmin",
        "familyadmin": "familyadmin",
        "bot_only": "botonly",
        "botonly": "botonly",
    }
    return mapping.get(value, "placeholder")


def _status_filter_key(record_status: str | None) -> str:
    value = str(record_status or "active").strip().lower()
    mapping = {
        "active": "active",
        "archived": "archived",
        "test_archived": "testarchived",
        "testarchived": "testarchived",
    }
    return mapping.get(value, "active")


def _channel_filter_key(preferred_ch: str | None) -> str:
    value = str(preferred_ch or "").strip().lower()
    mapping = {
        "max": "max",
        "tg": "tg",
        "email": "email",
        "push": "push",
        "none": "none",
        "": "none",
    }
    return mapping.get(value, "none")


def _avatar_filter_state(
    *,
    has_avatar: bool,
    is_alive: bool,
    avatar_last_dt: datetime | None,
    now_utc: datetime,
) -> tuple[str, bool]:
    if not has_avatar:
        return "no_avatar", False

    # Product rule v1: expired applies primarily to living people with avatar age > 365 days.
    if is_alive and avatar_last_dt and (now_utc - avatar_last_dt > timedelta(days=365)):
        return "expired_avatar", True

    return "actual_avatar", False


def _normalize_preferred_channel(raw_value: object, is_alive: bool) -> str | None:
    """Map UI channel values to DB-compatible values.

    No channel is persisted as NULL for backward-compatible DB constraints.
    """
    normalized = str(raw_value or "").strip().upper()

    if not normalized:
        return None

    if normalized in {"NONE", "NO", "NULL", "НЕ ЗАДАН", "НЕТ КАНАЛА", "NONE/NULL"}:
        return None
    if normalized == "MAX":
        return "Max"
    if normalized == "TG":
        return "TG"
    if normalized == "EMAIL":
        return "Email"
    if normalized == "PUSH":
        return "Push"

    raise ValueError("Недопустимое значение канала связи")


def _person_name_ru(db: Session, person_id: int | None) -> str:
    if not person_id:
        return "—"

    i18n = (
        db.query(PersonI18n)
        .filter(PersonI18n.person_id == person_id, PersonI18n.lang_code == "ru")
        .first()
    )
    if i18n:
        name = " ".join(
            [part for part in (i18n.first_name, i18n.last_name) if part]
        ).strip()
        if name:
            return name
    return f"Персона #{person_id}"


def _build_people_options(
    db: Session, exclude_person_ids: set[int] | None = None
) -> list[dict]:
    excluded = exclude_person_ids or set()
    options: list[dict] = []
    for person in db.query(Person).order_by(Person.person_id.asc()).all():
        if person.person_id in excluded:
            continue
        options.append(
            {
                "person_id": person.person_id,
                "name": _person_name_ru(db, person.person_id),
            }
        )
    return options


def _sync_pk_sequence(db: Session, table_name: str) -> None:
    """Synchronize SERIAL sequence with MAX(id) for legacy DBs where sequence drifted."""
    allowed_tables = {"Unions", "UnionChildren"}
    if table_name not in allowed_tables:
        raise ValueError("Unsupported table for sequence sync")

    db.execute(text(f"""
            SELECT setval(
                pg_get_serial_sequence('"{table_name}"', 'id'),
                COALESCE((SELECT MAX(id) FROM "{table_name}"), 1),
                true
            )
            """))


def _build_union_rows_for_person(db: Session, person_id: int) -> list[dict]:
    unions = (
        db.query(Union)
        .filter(or_(Union.partner1_id == person_id, Union.partner2_id == person_id))
        .order_by(Union.id.asc())
        .all()
    )

    rows: list[dict] = []
    for union in unions:
        other_partner_id = (
            union.partner2_id if union.partner1_id == person_id else union.partner1_id
        )

        children_links = (
            db.query(UnionChild)
            .filter(UnionChild.union_id == union.id)
            .order_by(UnionChild.id.asc())
            .all()
        )
        children = [
            {
                "child_id": link.child_id,
                "name": _person_name_ru(db, link.child_id),
            }
            for link in children_links
        ]

        rows.append(
            {
                "union_id": union.id,
                "partner_id": other_partner_id,
                "partner_name": _person_name_ru(db, other_partner_id),
                "start_date": union.start_date or "—",
                "end_date": union.end_date or "—",
                "children": children,
            }
        )

    return rows


def _build_person_form_data(
    person: Person, ru_i18n: PersonI18n | None, en_i18n: PersonI18n | None
) -> dict:
    return {
        "gender": person.gender or "Unknown",
        "default_lang": person.default_lang or "ru",
        "is_alive": bool(person.is_alive),
        "is_user": bool(person.is_user),
        "role": person.role or "placeholder",
        "birth_date": person.birth_date or "",
        "birth_date_prec": person.birth_date_prec or "",
        "death_date": person.death_date or "",
        "death_date_prec": person.death_date_prec or "",
        "phone": person.phone or "",
        "max_user_id": person.messenger_max_id or "",
        "preferred_ch": person.preferred_ch or "None",
        "avatar_url": person.avatar_url or "",
        "contact_email": person.contact_email or "",
        "maiden_name_ru": person.maiden_name or "",
        "first_name_ru": ru_i18n.first_name if ru_i18n else "",
        "last_name_ru": ru_i18n.last_name if ru_i18n else "",
        "patronymic_ru": ru_i18n.patronymic if ru_i18n else "",
        "biography_ru": ru_i18n.biography if ru_i18n else "",
        "first_name_en": en_i18n.first_name if en_i18n else "",
        "last_name_en": en_i18n.last_name if en_i18n else "",
        "patronymic_en": en_i18n.patronymic if en_i18n else "",
        "biography_en": en_i18n.biography if en_i18n else "",
    }


def _load_person_for_edit(
    db: Session, person_id: int
) -> tuple[Person, dict, list[dict]]:
    person = db.query(Person).filter(Person.person_id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    ru_i18n = (
        db.query(PersonI18n)
        .filter(PersonI18n.person_id == person_id, PersonI18n.lang_code == "ru")
        .first()
    )
    en_i18n = (
        db.query(PersonI18n)
        .filter(PersonI18n.person_id == person_id, PersonI18n.lang_code == "en")
        .first()
    )
    form_data = _build_person_form_data(person, ru_i18n, en_i18n)
    union_rows = _build_union_rows_for_person(db, person_id)
    return person, form_data, union_rows


@router.get("/")
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    redirect = require_admin(request)
    if redirect:
        return redirect

    return templates.TemplateResponse(
        "admin/admin_dashboard.html",
        {
            "request": request,
            "explorer_url": "/explorer/",
            "local_llm_check_url": "/admin/ai/local-llm-check",
        },
    )


@router.get("/explorer/password", response_class=JSONResponse)
async def admin_explorer_password(request: Request):
    redirect = require_admin(request)
    if redirect:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    return JSONResponse({"password": get_daily_password()})


@router.post("/test-impulse/{person_id}", response_class=JSONResponse)
async def admin_test_impulse(person_id: int, request: Request):
    redirect = require_admin(request)
    if redirect:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    bot = MaxMessengerBot()
    result = await bot.send_daily_impulse(person_id=person_id)
    return JSONResponse(result)


@router.get("/ai/local-llm-check", response_class=HTMLResponse)
async def admin_local_llm_check(request: Request):
    redirect = require_admin(request)
    if redirect:
        return redirect

    result: dict = {"status": "error", "message": "not executed"}
    try:
        analyzer = ProviderAgnosticAnalyzer(provider_name="local_llm")
        result = analyzer.analyze_memory_text("Это тестовая история о семье")
    except Exception as exc:
        result = {"status": "error", "message": str(exc), "type": type(exc).__name__}
    ok = (result or {}).get("status") == "ok" and bool(
        str((result or {}).get("summary") or "").strip()
    )

    return templates.TemplateResponse(
        "admin/admin_ai_local_llm_check.html",
        {
            "request": request,
            "ok": ok,
            "provider": "local_llm",
            "result": result,
        },
    )


@router.get("/whisper/local-test", response_class=HTMLResponse)
async def admin_whisper_local_test_form(request: Request):
    redirect = require_admin(request)
    if redirect:
        return redirect

    return templates.TemplateResponse(
        "admin/admin_whisper_local_test.html",
        {
            "request": request,
            "result": None,
            "error": None,
            "whisper_local_url": os.getenv("WHISPER_LOCAL_URL", "").strip(),
            "whisper_provider": (os.getenv("WHISPER_PROVIDER", "") or "").strip(),
        },
    )


@router.post("/whisper/local-test", response_class=HTMLResponse)
async def admin_whisper_local_test_submit(
    request: Request, file: UploadFile = File(...)
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    whisper_local_url = os.getenv("WHISPER_LOCAL_URL", "").strip()
    whisper_provider = (os.getenv("WHISPER_PROVIDER", "") or "").strip()
    if not whisper_local_url:
        return templates.TemplateResponse(
            "admin/admin_whisper_local_test.html",
            {
                "request": request,
                "result": None,
                "error": "WHISPER_LOCAL_URL не задан (нельзя вызвать локальный Whisper).",
                "whisper_local_url": whisper_local_url,
                "whisper_provider": whisper_provider,
            },
            status_code=400,
        )

    content = await file.read()
    if not content:
        return templates.TemplateResponse(
            "admin/admin_whisper_local_test.html",
            {
                "request": request,
                "result": None,
                "error": "Пустой файл.",
                "whisper_local_url": whisper_local_url,
                "whisper_provider": whisper_provider,
            },
            status_code=400,
        )

    start = time.monotonic()
    try:
        files = {
            "file": (file.filename or "audio.bin", content, "application/octet-stream")
        }
        response = httpx.post(whisper_local_url, files=files, timeout=240.0)
        status_code = response.status_code
        payload = response.json() if response.content else {}
    except Exception as exc:
        elapsed = round(time.monotonic() - start, 3)
        return templates.TemplateResponse(
            "admin/admin_whisper_local_test.html",
            {
                "request": request,
                "result": {
                    "status": "error",
                    "error": str(exc),
                    "processing_seconds": elapsed,
                },
                "error": f"Ошибка вызова локального Whisper: {exc}",
                "whisper_local_url": whisper_local_url,
                "whisper_provider": whisper_provider,
            },
            status_code=502,
        )

    elapsed = round(time.monotonic() - start, 3)
    result = payload if isinstance(payload, dict) else {"raw": payload}
    if isinstance(result, dict):
        result.setdefault("http_status_code", status_code)
        result.setdefault("processing_seconds", elapsed)

    ok = (
        isinstance(result, dict)
        and result.get("status") == "ok"
        and bool(str(result.get("text") or "").strip())
    )
    error = None if ok else "Whisper вернул пустой/ошибочный результат."

    return templates.TemplateResponse(
        "admin/admin_whisper_local_test.html",
        {
            "request": request,
            "result": result,
            "error": error,
            "whisper_local_url": whisper_local_url,
            "whisper_provider": whisper_provider,
        },
        status_code=200 if ok else 502,
    )


@router.get("/pipeline/memory-test", response_class=HTMLResponse)
async def admin_memory_pipeline_test_form(request: Request):
    redirect = require_admin(request)
    if redirect:
        return redirect

    return templates.TemplateResponse(
        "admin/admin_memory_pipeline_test.html",
        {
            "request": request,
            "result": None,
            "error": None,
            "input_text": "",
            "whisper_local_url": os.getenv("WHISPER_LOCAL_URL", "").strip(),
            "whisper_provider": (os.getenv("WHISPER_PROVIDER", "") or "").strip(),
            "ai_local_llm_url": os.getenv("AI_LOCAL_LLM_URL", "").strip(),
            "ai_provider": (os.getenv("AI_PROVIDER", "") or "").strip()
            or (os.getenv("AIPROVIDER", "") or "").strip(),
        },
    )


@router.post("/pipeline/memory-test", response_class=HTMLResponse)
async def admin_memory_pipeline_test_submit(
    request: Request,
    input_text: str = Form(""),
    file: UploadFile | None = File(None),
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    whisper_local_url = os.getenv("WHISPER_LOCAL_URL", "").strip()
    whisper_provider = (os.getenv("WHISPER_PROVIDER", "") or "").strip()
    ai_local_llm_url = os.getenv("AI_LOCAL_LLM_URL", "").strip()
    ai_provider = (os.getenv("AI_PROVIDER", "") or "").strip() or (
        os.getenv("AIPROVIDER", "") or ""
    ).strip()

    transcript_text = (input_text or "").strip()
    transcript_payload = None
    whisper_timing = None

    if file is not None and (file.filename or "").strip():
        if not whisper_local_url:
            return templates.TemplateResponse(
                "admin/admin_memory_pipeline_test.html",
                {
                    "request": request,
                    "result": None,
                    "error": "WHISPER_LOCAL_URL не задан (нельзя прогнать аудио через local Whisper).",
                    "input_text": transcript_text,
                    "whisper_local_url": whisper_local_url,
                    "whisper_provider": whisper_provider,
                    "ai_local_llm_url": ai_local_llm_url,
                    "ai_provider": ai_provider,
                },
                status_code=400,
            )

        audio_content = await file.read()
        if not audio_content:
            return templates.TemplateResponse(
                "admin/admin_memory_pipeline_test.html",
                {
                    "request": request,
                    "result": None,
                    "error": "Пустой аудиофайл.",
                    "input_text": transcript_text,
                    "whisper_local_url": whisper_local_url,
                    "whisper_provider": whisper_provider,
                    "ai_local_llm_url": ai_local_llm_url,
                    "ai_provider": ai_provider,
                },
                status_code=400,
            )

        start = time.monotonic()
        try:
            files = {
                "file": (
                    file.filename or "audio.bin",
                    audio_content,
                    "application/octet-stream",
                )
            }
            response = httpx.post(whisper_local_url, files=files, timeout=240.0)
            transcript_payload = response.json() if response.content else {}
        except Exception as exc:
            whisper_timing = round(time.monotonic() - start, 3)
            return templates.TemplateResponse(
                "admin/admin_memory_pipeline_test.html",
                {
                    "request": request,
                    "result": None,
                    "error": f"Ошибка вызова local Whisper: {exc}",
                    "input_text": transcript_text,
                    "whisper_local_url": whisper_local_url,
                    "whisper_provider": whisper_provider,
                    "ai_local_llm_url": ai_local_llm_url,
                    "ai_provider": ai_provider,
                },
                status_code=502,
            )
        whisper_timing = round(time.monotonic() - start, 3)
        if isinstance(transcript_payload, dict):
            transcript_payload.setdefault("processing_seconds", whisper_timing)
        if (
            isinstance(transcript_payload, dict)
            and transcript_payload.get("status") == "ok"
        ):
            transcript_text = str(transcript_payload.get("text") or "").strip()

    if not transcript_text:
        return templates.TemplateResponse(
            "admin/admin_memory_pipeline_test.html",
            {
                "request": request,
                "result": {
                    "transcript": {"status": "empty", "text": ""},
                    "analysis": None,
                    "providers": {
                        "whisper": {
                            "provider": whisper_provider,
                            "endpoint": whisper_local_url,
                        },
                        "local_llm": {
                            "provider": "local_llm",
                            "endpoint": ai_local_llm_url,
                        },
                    },
                },
                "error": "Пустой результат: нет текста для анализа (введите текст или загрузите аудио).",
                "input_text": (input_text or "").strip(),
                "whisper_local_url": whisper_local_url,
                "whisper_provider": whisper_provider,
                "ai_local_llm_url": ai_local_llm_url,
                "ai_provider": ai_provider,
            },
            status_code=400,
        )

    analyzer = ProviderAgnosticAnalyzer(provider_name="local_llm")
    analysis_start = time.monotonic()
    analysis = analyzer.analyze_memory_text(transcript_text)
    analysis_timing = round(time.monotonic() - analysis_start, 3)

    result = {
        "transcript": {
            "status": "ok",
            "text": transcript_text,
            "raw": transcript_payload,
        },
        "analysis": analysis,
        "timings": {
            "whisper_seconds": whisper_timing,
            "analysis_seconds": analysis_timing,
        },
        "providers": {
            "whisper": {
                "provider": whisper_provider or "local_small",
                "endpoint": whisper_local_url,
            },
            "local_llm": {
                "provider": "local_llm",
                "endpoint": ai_local_llm_url,
            },
        },
    }

    ok = isinstance(analysis, dict) and analysis.get("status") == "ok"
    error = None if ok else "Анализатор вернул ошибку (см. JSON ниже)."

    return templates.TemplateResponse(
        "admin/admin_memory_pipeline_test.html",
        {
            "request": request,
            "result": result,
            "error": error,
            "input_text": (input_text or "").strip(),
            "whisper_local_url": whisper_local_url,
            "whisper_provider": whisper_provider,
            "ai_local_llm_url": ai_local_llm_url,
            "ai_provider": ai_provider,
        },
        status_code=200 if ok else 502,
    )


@router.get("/transcriptions")
async def admin_transcriptions(
    request: Request,
    status: str = "pending",
    db: Session = Depends(get_db),
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    # Нормализуем статус
    normalized_status = (status or "pending").strip().lower()
    if normalized_status not in {"pending", "archived", "all"}:
        normalized_status = "pending"

    # Строим запрос
    memories_query = db.query(Memory).filter(Memory.audio_url.isnot(None))

    if normalized_status == "pending":
        # Показываем pending, draft и pending_manual_text (аудио из MAX, ожидает текста)
        memories_query = memories_query.filter(
            Memory.transcription_status.in_(["pending", "draft", "pending_manual_text"])
        )
    elif normalized_status == "archived":
        # Показываем только archived
        memories_query = memories_query.filter(
            Memory.transcription_status == "archived"
        )
    # Если "all", не добавляем фильтр по статусу, уже есть фильтр по audio_url

    memories = memories_query.order_by(Memory.created_at.desc()).all()

    result = []
    for m in memories:
        author_name = None
        author_avatar = None
        author_id = None
        if m.author_id:
            author_id = m.author_id
            i18n = (
                db.query(PersonI18n)
                .filter(
                    PersonI18n.person_id == m.author_id,
                    PersonI18n.lang_code == "ru",
                )
                .first()
            )
            if i18n:
                parts = [i18n.first_name, i18n.last_name]
                author_name = " ".join([p for p in parts if p])

            person = db.query(Person).filter(Person.person_id == m.author_id).first()
            if person:
                author_avatar = person.avatar_url

        audio_player_src = m.audio_url
        audio_source = "external"
        analysis = None
        analysis_status = None
        analysis_summary = None
        analysis_persons = []
        analysis_dates = []
        analysis_locations = []
        transcription_substatus = None
        if m.transcript_verbatim:
            try:
                metadata = json.loads(m.transcript_verbatim)
            except (json.JSONDecodeError, TypeError):
                metadata = {}

            local_audio_path = (
                metadata.get("local_audio_path") if isinstance(metadata, dict) else None
            )
            if isinstance(local_audio_path, str) and local_audio_path.strip():
                audio_player_src = local_audio_path.strip()
                audio_source = "local"

            if isinstance(metadata, dict):
                cand = metadata.get("analysis")
                if isinstance(cand, dict):
                    analysis = cand
                    analysis_status = (
                        str(cand.get("status") or "").strip().lower() or None
                    )
                    analysis_summary = str(cand.get("summary") or "").strip() or None
                    analysis_persons = (
                        cand.get("persons")
                        if isinstance(cand.get("persons"), list)
                        else []
                    )
                    analysis_dates = (
                        cand.get("dates") if isinstance(cand.get("dates"), list) else []
                    )
                    analysis_locations = (
                        cand.get("locations")
                        if isinstance(cand.get("locations"), list)
                        else []
                    )

                items = metadata.get("draft_items")
                if isinstance(items, list):
                    statuses = [
                        str((it or {}).get("transcription_status") or "")
                        .strip()
                        .lower()
                        for it in items
                        if isinstance(it, dict) and it.get("type") == "audio"
                    ]
                    if any(s == "error" for s in statuses):
                        transcription_substatus = "transcription_error"
                    elif any(s == "pending" for s in statuses):
                        transcription_substatus = "transcription_pending"

        result.append(
            {
                "id": m.id,
                "author_name": author_name,
                "author_avatar": author_avatar,
                "author_id": author_id,
                "audio_url": m.audio_url,
                "audio_player_src": audio_player_src,
                "audio_source": audio_source,
                "transcript_verbatim": m.transcript_verbatim,
                "transcript_readable": m.transcript_readable,
                "transcription_status": m.transcription_status,
                "transcription_substatus": transcription_substatus,
                "source_type": m.source_type,
                "created_at": m.created_at,
                "analysis": analysis,
                "analysis_status": analysis_status,
                "analysis_summary": analysis_summary,
                "analysis_persons": analysis_persons,
                "analysis_dates": analysis_dates,
                "analysis_locations": analysis_locations,
            }
        )

    return templates.TemplateResponse(
        "admin/admin_transcriptions.html",
        {
            "request": request,
            "memories": result,
            "current_status": normalized_status,
        },
    )


@router.post("/transcriptions/{memory_id}/publish")
async def publish_transcription(
    memory_id: int,
    request: Request,
    transcript_verbatim: str = Form(""),
    transcript_readable: str = Form(""),
    transcription_status: str = Form("published"),
    action: str = Form("publish"),
    status: str = Form("pending"),
    db: Session = Depends(get_db),
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    memory = db.query(Memory).filter(Memory.id == memory_id).first()
    if memory:
        memory.transcript_verbatim = transcript_verbatim
        memory.transcript_readable = transcript_readable

        if action == "archive":
            next_status = "archived"
        else:
            # Кнопка публикации всегда переводит запись в публичный статус.
            next_status = "published"

        allowed_statuses = {"published", "archived"}
        if next_status not in allowed_statuses:
            next_status = "published"
        memory.transcription_status = next_status
        db.commit()

    redirect_status = (status or "pending").strip().lower()
    if redirect_status not in {"pending", "archived", "all"}:
        redirect_status = "pending"

    return RedirectResponse(
        url=f"/admin/transcriptions?status={redirect_status}",
        status_code=303,
    )


@router.get("/login", response_class=HTMLResponse)
async def admin_login(request: Request, next: str = "/admin"):
    return templates.TemplateResponse(
        "admin/admin_login.html",
        {"request": request, "next": next, "error": None},
    )


@router.post("/login", response_class=HTMLResponse)
async def admin_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/admin"),
):
    ip = get_client_ip(request)
    if not check_login_rate_limit(ip):
        log_login_attempt(ip, username, "rate_limited")
        return HTMLResponse(
            content="<h1>429 — слишком много попыток входа</h1>"
            "<p>Попробуйте через минуту.</p>",
            status_code=429,
        )

    expected_username = os.getenv("ADMIN_USERNAME", "admin")
    expected_password = os.getenv("ADMIN_PASSWORD", "")

    if username == expected_username and password == expected_password:
        log_login_attempt(ip, username, "success")
        # Validate next to prevent open redirect: only relative internal paths allowed
        safe_next = (
            next
            if (
                next
                and next.startswith("/")
                and not next.startswith("//")
                and "://" not in next
            )
            else "/admin"
        )
        response = RedirectResponse(url=safe_next, status_code=303)
        response.set_cookie(
            key=ADMIN_COOKIE_NAME,
            value=make_admin_token(),
            max_age=60 * 60 * 8,  # 8 hours
            path="/",
            httponly=True,
            samesite="lax",
        )
        admin_register_login(make_admin_token())
        return response

    log_login_attempt(ip, username, "fail")
    return templates.TemplateResponse(
        "admin/admin_login.html",
        {"request": request, "next": next, "error": "Неверные учётные данные"},
    )


@router.get("/logout")
async def admin_logout_get(request: Request):
    token = request.cookies.get(ADMIN_COOKIE_NAME, "")
    if token:
        admin_register_logout(token)
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(key=ADMIN_COOKIE_NAME, path="/")
    return response


@router.post("/logout")
async def admin_logout_post(request: Request):
    token = request.cookies.get(ADMIN_COOKIE_NAME, "")
    if token:
        admin_register_logout(token)
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(key=ADMIN_COOKIE_NAME, path="/")
    return response


@router.get("/early-access", response_class=HTMLResponse)
async def admin_early_access_list(request: Request, db: Session = Depends(get_db)):
    redirect = require_admin(request)
    if redirect:
        return redirect

    rows = (
        db.query(EarlyAccessRequest)
        .order_by(EarlyAccessRequest.created_at.desc())
        .limit(200)
        .all()
    )

    return templates.TemplateResponse(
        "admin/adminearly-access.html",
        {"request": request, "rows": rows},
    )


@router.get("/avatars", response_class=HTMLResponse)
async def admin_avatars(request: Request, db: Session = Depends(get_db)):
    redirect = require_admin(request)
    if redirect:
        return redirect

    people = []
    for person in db.query(Person).order_by(Person.person_id).all():
        i18n = (
            db.query(PersonI18n)
            .filter(
                PersonI18n.person_id == person.person_id,
                PersonI18n.lang_code == "ru",
            )
            .first()
        )
        name = " ".join(
            [
                p
                for p in (
                    i18n.first_name if i18n else None,
                    i18n.last_name if i18n else None,
                )
                if p
            ]
        ).strip()
        if not name:
            name = f"Персона #{person.person_id}"

        slug = default_family_slug()
        people.append(
            {
                "id": person.person_id,
                "name": name,
                "avatar_url": normalize_media_url(person.avatar_url, slug),
            }
        )

    return templates.TemplateResponse(
        "admin/avatars_form.html",
        {"request": request, "people": people},
    )


@router.post("/avatars")
async def admin_avatars_upload(
    request: Request,
    person_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    person = db.query(Person).filter(Person.person_id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        suffix = ".jpg"

    slug = default_family_slug()
    avatar_dir = Path(family_data_path_for_slug(slug)) / "media" / "avatars" / "current"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    filename = f"person_{person_id}_{uuid4().hex}{suffix}"
    target = avatar_dir / filename

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    target.write_bytes(content)
    person.avatar_url = f"/media/{slug}/avatars/current/{filename}"
    db.commit()

    return RedirectResponse(url="/admin/avatars", status_code=303)


@router.get("/people", response_class=HTMLResponse, name="admin_people")
async def admin_people(
    request: Request,
    q: str | None = Query(None, description="ID или подстрока имени (ru)"),
    db: Session = Depends(get_db),
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    people = db.query(Person).order_by(Person.person_id).all()

    person_ids = [p.person_id for p in people]
    avatar_rows = (
        db.query(AvatarHistory).filter(AvatarHistory.person_id.in_(person_ids)).all()
        if person_ids
        else []
    )

    avatar_by_person: dict[int, list[AvatarHistory]] = {}
    for row in avatar_rows:
        avatar_by_person.setdefault(row.person_id, []).append(row)

    now_utc = datetime.now(timezone.utc)

    rows = []
    for p in people:
        i18n = (
            db.query(PersonI18n)
            .filter(
                PersonI18n.person_id == p.person_id,
                PersonI18n.lang_code == "ru",
            )
            .first()
        )
        name = " ".join(
            [
                part
                for part in (
                    i18n.first_name if i18n else None,
                    i18n.last_name if i18n else None,
                )
                if part
            ]
        ).strip()
        if not name:
            name = f"Персона #{p.person_id}"

        memories_count = (
            db.query(Memory).filter(Memory.author_id == p.person_id).count()
        )
        quotes_count = db.query(Quote).filter(Quote.author_id == p.person_id).count()
        alias_rows = (
            db.query(PersonAlias)
            .filter(
                PersonAlias.person_id == p.person_id,
                PersonAlias.status == "active",
            )
            .order_by(PersonAlias.id.asc())
            .all()
        )
        aliases = [
            {
                "id": alias.id,
                "label": alias.label,
                "alias_type": alias.alias_type,
                "used_by_generation": alias.used_by_generation,
                "note": alias.note,
            }
            for alias in alias_rows
        ]

        person_avatar_rows = avatar_by_person.get(p.person_id, [])
        current_avatars = [a for a in person_avatar_rows if int(a.is_current or 0) == 1]
        candidate_rows = current_avatars or person_avatar_rows
        latest_avatar = max(
            candidate_rows,
            key=lambda a: _parse_datetime_safe(a.created_at)
            or datetime.min.replace(tzinfo=timezone.utc),
            default=None,
        )

        history_has_avatar = bool(
            latest_avatar and str(latest_avatar.storage_path or "").strip()
        )
        has_avatar = bool(str(p.avatar_url or "").strip()) or history_has_avatar
        avatar_last_dt = (
            _parse_datetime_safe(latest_avatar.created_at) if latest_avatar else None
        )
        is_alive_bool = bool(p.is_alive)
        avatar_state, avatar_is_expired = _avatar_filter_state(
            has_avatar=has_avatar,
            is_alive=is_alive_bool,
            avatar_last_dt=avatar_last_dt,
            now_utc=now_utc,
        )

        rows.append(
            {
                "person_id": p.person_id,
                "name": name,
                "role": p.role or "",
                "record_status": p.record_status or "active",
                "phone": p.phone or "",
                "preferred_ch": p.preferred_ch or "",
                "messenger_max_id": p.messenger_max_id or "",
                "messenger_tg_id": p.messenger_tg_id or "",
                "contact_email": p.contact_email or "",
                "is_alive": p.is_alive,
                "avatar_url": normalize_media_url(p.avatar_url, default_family_slug()),
                "memories_count": memories_count,
                "quotes_count": quotes_count,
                "aliases": aliases,
                "has_avatar": has_avatar,
                "avatar_is_expired": avatar_is_expired,
                "avatar_state": avatar_state,
                "avatar_state_label": (
                    "Нет аватара"
                    if avatar_state == "no_avatar"
                    else (
                        "Аватар истёк"
                        if avatar_state == "expired_avatar"
                        else "Аватар актуален"
                    )
                ),
                "avatar_last_updated_at": (
                    latest_avatar.created_at if latest_avatar else None
                ),
                "role_key": _role_filter_key(p.role),
                "record_status_key": _status_filter_key(p.record_status),
                "preferred_ch_key": _channel_filter_key(p.preferred_ch),
                "is_alive_key": "yes" if is_alive_bool else "no",
            }
        )

    q_clean = (q or "").strip()
    if q_clean:
        if q_clean.isdigit():
            pid = int(q_clean)
            rows = [r for r in rows if r["person_id"] == pid]
        else:
            needle = q_clean.casefold()
            rows = [r for r in rows if needle in (r.get("name") or "").casefold()]

    return templates.TemplateResponse(
        "admin/admin_people.html",
        {"request": request, "rows": rows, "search_q": q_clean},
    )


def _parse_alias_spoken_by(form_value: object) -> int | None:
    raw = str(form_value or "").strip()
    if not raw or raw == "0":
        return None
    try:
        return int(raw)
    except Exception:
        return None


def _normalize_alias_list_filters(
    status_filter: str, source_filter: str
) -> tuple[str, str]:
    if status_filter not in {"all", "active", "rejected"}:
        status_filter = "all"
    if source_filter not in {"all", "ai_extracted", "manual"}:
        source_filter = "all"
    return status_filter, source_filter


def _load_person_alias_row_dicts(
    db: Session, person_id: int, status_filter: str, source_filter: str
) -> tuple[str, str, list[dict]]:
    status_filter, source_filter = _normalize_alias_list_filters(
        status_filter, source_filter
    )
    q = (
        db.query(PersonAlias)
        .filter(PersonAlias.person_id == person_id)
        .order_by(PersonAlias.id.asc())
    )
    if status_filter == "active":
        q = q.filter(PersonAlias.status == "active")
    elif status_filter == "rejected":
        q = q.filter(PersonAlias.status == "rejected")
    if source_filter == "ai_extracted":
        q = q.filter(PersonAlias.source == "ai_extracted")
    elif source_filter == "manual":
        q = q.filter(PersonAlias.source == "manual")

    rows_out: list[dict] = []
    for a in q.all():
        sp_name = "Универсальный"
        if a.spoken_by_person_id:
            sp_name = _person_name_ru(db, a.spoken_by_person_id)
        rows_out.append(
            {
                "id": a.id,
                "label": a.label,
                "alias_type": a.alias_type,
                "source": a.source,
                "status": a.status,
                "spoken_by_person_id": a.spoken_by_person_id,
                "spoken_by_label": sp_name,
                "created_at": a.created_at,
                "updated_at": a.updated_at,
            }
        )
    return status_filter, source_filter, rows_out


@router.get(
    "/people/{person_id}/aliases",
    response_class=HTMLResponse,
    name="admin_person_aliases",
)
async def admin_person_aliases_page(
    request: Request,
    person_id: int,
    db: Session = Depends(get_db),
    status_filter: str = Query("all"),
    source_filter: str = Query("all"),
    edit: int | None = Query(None, description="id алиаса для формы правки"),
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    person = db.query(Person).filter(Person.person_id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    status_filter, source_filter, rows_out = _load_person_alias_row_dicts(
        db, person_id, status_filter, source_filter
    )

    editing: dict | None = None
    if edit is not None:
        ed = (
            db.query(PersonAlias)
            .filter(PersonAlias.id == edit, PersonAlias.person_id == person_id)
            .first()
        )
        if ed:
            sn = "Универсальный"
            if ed.spoken_by_person_id:
                sn = _person_name_ru(db, ed.spoken_by_person_id)
            editing = {
                "id": ed.id,
                "label": ed.label,
                "alias_type": ed.alias_type,
                "source": ed.source,
                "status": ed.status,
                "spoken_by_person_id": ed.spoken_by_person_id,
                "spoken_by_label": sn,
            }

    people_spoken = _build_people_options(db, exclude_person_ids={person_id})

    return templates.TemplateResponse(
        "admin/adminpersonaliases.html",
        {
            "request": request,
            "person_id": person_id,
            "person_name": _person_name_ru(db, person_id),
            "rows": rows_out,
            "editing": editing,
            "people_spoken": people_spoken,
            "status_filter": status_filter,
            "source_filter": source_filter,
            "alias_types": sorted(ALIAS_TYPES),
            "form_error": None,
        },
    )


@router.post("/people/{person_id}/aliases", response_class=HTMLResponse)
async def admin_person_alias_create_submit(
    person_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    person = db.query(Person).filter(Person.person_id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    form = await request.form()
    label = str(form.get("label") or "").strip()
    alias_type = str(form.get("alias_type") or "").strip()
    spoken_id = _parse_alias_spoken_by(form.get("spoken_by_person_id"))

    def re_render_error(message: str) -> HTMLResponse:
        _, _, rows_out = _load_person_alias_row_dicts(db, person_id, "all", "all")
        return templates.TemplateResponse(
            "admin/adminpersonaliases.html",
            {
                "request": request,
                "person_id": person_id,
                "person_name": _person_name_ru(db, person_id),
                "rows": rows_out,
                "editing": None,
                "people_spoken": _build_people_options(
                    db, exclude_person_ids={person_id}
                ),
                "status_filter": "all",
                "source_filter": "all",
                "alias_types": sorted(ALIAS_TYPES),
                "form_error": message,
            },
            status_code=400,
        )

    if not label:
        return re_render_error("Укажите текст алиаса (label).")
    if alias_type not in ALIAS_TYPES:
        return re_render_error("Некорректный тип алиаса.")
    if (
        spoken_id is not None
        and not db.query(Person).filter(Person.person_id == spoken_id).first()
    ):
        return re_render_error("Выбранный «Кто называет» не найден.")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row = PersonAlias(
        person_id=person_id,
        label=label,
        alias_type=alias_type,
        spoken_by_person_id=spoken_id,
        source="manual",
        status="active",
        updated_at=now,
    )
    db.add(row)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        return re_render_error(f"Не удалось сохранить: {exc}")

    return RedirectResponse(
        url=f"/admin/people/{person_id}/aliases",
        status_code=303,
    )


@router.post("/people/{person_id}/aliases/{alias_id}/edit", response_class=HTMLResponse)
async def admin_person_alias_edit_submit(
    person_id: int,
    alias_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    al = (
        db.query(PersonAlias)
        .filter(PersonAlias.id == alias_id, PersonAlias.person_id == person_id)
        .first()
    )
    if not al:
        raise HTTPException(status_code=404, detail="Alias not found")

    form = await request.form()
    label = str(form.get("label") or "").strip()
    alias_type = str(form.get("alias_type") or "").strip()
    status = str(form.get("status") or "").strip()
    spoken_id = _parse_alias_spoken_by(form.get("spoken_by_person_id"))

    if not label:
        return RedirectResponse(
            url=f"/admin/people/{person_id}/aliases?edit={alias_id}",
            status_code=303,
        )
    if alias_type not in ALIAS_TYPES or status not in ALIAS_STATUS:
        return RedirectResponse(
            url=f"/admin/people/{person_id}/aliases?edit={alias_id}",
            status_code=303,
        )
    if (
        spoken_id is not None
        and not db.query(Person).filter(Person.person_id == spoken_id).first()
    ):
        return RedirectResponse(
            url=f"/admin/people/{person_id}/aliases?edit={alias_id}",
            status_code=303,
        )

    al.label = label
    al.alias_type = alias_type
    al.status = status
    al.spoken_by_person_id = spoken_id
    al.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Save failed")

    return RedirectResponse(
        url=f"/admin/people/{person_id}/aliases",
        status_code=303,
    )


@router.post(
    "/people/{person_id}/aliases/{alias_id}/reject", response_class=HTMLResponse
)
async def admin_person_alias_reject(
    person_id: int,
    alias_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    al = (
        db.query(PersonAlias)
        .filter(PersonAlias.id == alias_id, PersonAlias.person_id == person_id)
        .first()
    )
    if not al:
        raise HTTPException(status_code=404, detail="Alias not found")

    al.status = "rejected"
    al.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Save failed")

    return RedirectResponse(
        url=f"/admin/people/{person_id}/aliases",
        status_code=303,
    )


@router.get("/people/new", response_class=HTMLResponse)
async def admin_person_new_form(request: Request):
    redirect = require_admin(request)
    if redirect:
        return redirect

    return templates.TemplateResponse(
        "admin/admin_person_new.html",
        {
            "request": request,
            "error": None,
            "form_data": {},
        },
    )


@router.post("/people/new", response_class=HTMLResponse)
async def admin_person_new_submit(request: Request, db: Session = Depends(get_db)):
    redirect = require_admin(request)
    if redirect:
        return redirect

    form = await request.form()

    def render_error(message: str):
        return templates.TemplateResponse(
            "admin/admin_person_new.html",
            {
                "request": request,
                "error": message,
                "form_data": dict(form),
            },
            status_code=400,
        )

    ru_first_name = str(form.get("first_name_ru") or "").strip()
    if not ru_first_name:
        return render_error("Поле «Имя (RU)» обязательно для заполнения.")

    allowed_genders = {"M", "F", "Unknown"}
    gender = (form.get("gender") or "Unknown").strip()
    if gender not in allowed_genders:
        return render_error("Некорректное значение поля «Пол».")

    allowed_langs = {"ru", "en"}
    default_lang = (form.get("default_lang") or "ru").strip()
    if default_lang not in allowed_langs:
        return render_error("Некорректное значение языка по умолчанию.")

    is_alive = "is_alive" in form
    try:
        preferred_ch = _normalize_preferred_channel(
            form.get("preferred_ch"), is_alive=is_alive
        )
    except ValueError as exc:
        return render_error(str(exc))

    birth_date_prec = (form.get("birth_date_prec") or "").strip() or None
    death_date_prec = (form.get("death_date_prec") or "").strip() or None
    allowed_precisions = {"EXACT", "ABOUT", "YEARONLY", "DECADE"}
    raw_role = (form.get("role") or "placeholder").strip()
    role = raw_role if raw_role in ALLOWED_ROLES else "placeholder"
    if birth_date_prec and birth_date_prec not in allowed_precisions:
        return render_error("Некорректная точность даты рождения.")
    if death_date_prec and death_date_prec not in allowed_precisions:
        return render_error("Некорректная точность даты смерти.")

    person_data = {
        "gender": gender,
        "is_alive": is_alive,
        "role": role,
        "default_lang": default_lang,
        "is_user": "is_user" in form,
        "birth_date": _clean_optional_text(form.get("birth_date")),
        "birth_date_prec": birth_date_prec,
        "death_date": _clean_optional_text(form.get("death_date")),
        "death_date_prec": death_date_prec,
        "phone": _clean_optional_text(form.get("phone")),
        "contact_email": _clean_optional_text(form.get("contact_email")),
        "max_user_id": _clean_optional_text(form.get("max_user_id")),
        "preferred_ch": preferred_ch,
        "avatar_url": _clean_optional_text(form.get("avatar_url")),
    }
    maiden_name = (form.get("maiden_name_ru") or "").strip() or None
    person_data["maiden_name"] = maiden_name

    ru_data = {
        "first_name": ru_first_name,
        "last_name": (form.get("last_name_ru") or "").strip() or None,
        "patronymic": (form.get("patronymic_ru") or "").strip() or None,
        "biography": (form.get("biography_ru") or "").strip() or None,
    }

    en_first = (form.get("first_name_en") or "").strip()
    en_data = None
    if en_first:
        en_data = {
            "first_name": en_first,
            "last_name": (form.get("last_name_en") or "").strip() or None,
            "patronymic": (form.get("patronymic_en") or "").strip() or None,
            "biography": (form.get("biography_en") or "").strip() or None,
        }

    try:
        create_person_with_i18n(db, person_data, ru_data, en_data)
    except IntegrityError as exc:
        db.rollback()
        details = str(getattr(exc, "orig", exc)).lower()
        if "messenger_max_id" in details and "unique" in details:
            return render_error("Такой Max ID уже существует")
        if "preferred_ch" in details or "people_preferred_ch_check" in details:
            return render_error("Недопустимое значение канала связи")
        return render_error("Не удалось сохранить запись, проверь поля контактов")
    except ValueError as exc:
        return render_error(str(exc))
    except Exception as exc:
        return render_error(f"Ошибка при создании персоны: {exc}")

    return RedirectResponse(url="/admin/people", status_code=302)


@router.get("/people/{person_id}", response_class=RedirectResponse)
async def admin_person_redirect_to_edit(request: Request, person_id: int):
    """Канонический URL карточки — /edit; короткий /people/{id} ведёт туда же (без 404)."""
    redirect = require_admin(request)
    if redirect:
        return redirect
    return RedirectResponse(url=f"/admin/people/{person_id}/edit", status_code=303)


@router.get("/people/{person_id}/edit", response_class=HTMLResponse)
async def admin_person_edit_form(
    person_id: int, request: Request, db: Session = Depends(get_db)
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    person, form_data, union_rows = _load_person_for_edit(db, person_id)
    return templates.TemplateResponse(
        "admin/admin_person_edit.html",
        {
            "request": request,
            "error": None,
            "person": person,
            "form_data": form_data,
            "union_rows": union_rows,
        },
    )


@router.post("/people/{person_id}/edit", response_class=HTMLResponse)
async def admin_person_edit_submit(
    person_id: int, request: Request, db: Session = Depends(get_db)
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    person, _, union_rows = _load_person_for_edit(db, person_id)
    form = await request.form()

    def render_error(message: str):
        form_data = dict(form)
        form_data["is_alive"] = "is_alive" in form
        form_data["is_user"] = "is_user" in form
        return templates.TemplateResponse(
            "admin/admin_person_edit.html",
            {
                "request": request,
                "error": message,
                "person": person,
                "form_data": form_data,
                "union_rows": union_rows,
            },
            status_code=400,
        )

    ru_first_name = str(form.get("first_name_ru") or "").strip()
    if not ru_first_name:
        return render_error("Поле «Имя (RU)» обязательно для заполнения.")

    allowed_genders = {"M", "F", "Unknown"}
    gender = (form.get("gender") or "Unknown").strip()
    if gender not in allowed_genders:
        return render_error("Некорректное значение поля «Пол».")

    allowed_langs = {"ru", "en"}
    default_lang = (form.get("default_lang") or "ru").strip()
    if default_lang not in allowed_langs:
        return render_error("Некорректное значение языка по умолчанию.")

    is_alive = "is_alive" in form
    try:
        preferred_ch = _normalize_preferred_channel(
            form.get("preferred_ch"), is_alive=is_alive
        )
    except ValueError as exc:
        return render_error(str(exc))

    birth_date_prec = (form.get("birth_date_prec") or "").strip() or None
    death_date_prec = (form.get("death_date_prec") or "").strip() or None
    allowed_precisions = {"EXACT", "ABOUT", "YEARONLY", "DECADE"}
    raw_role = (form.get("role") or "placeholder").strip()
    role = raw_role if raw_role in ALLOWED_ROLES else "placeholder"
    if birth_date_prec and birth_date_prec not in allowed_precisions:
        return render_error("Некорректная точность даты рождения.")
    if death_date_prec and death_date_prec not in allowed_precisions:
        return render_error("Некорректная точность даты смерти.")

    person_data = {
        "gender": gender,
        "is_alive": is_alive,
        "role": role,
        "default_lang": default_lang,
        "is_user": "is_user" in form,
        "birth_date": _clean_optional_text(form.get("birth_date")),
        "birth_date_prec": birth_date_prec,
        "death_date": _clean_optional_text(form.get("death_date")),
        "death_date_prec": death_date_prec,
        "phone": _clean_optional_text(form.get("phone")),
        "contact_email": _clean_optional_text(form.get("contact_email")),
        "max_user_id": _clean_optional_text(form.get("max_user_id")),
        "preferred_ch": preferred_ch,
        "avatar_url": _clean_optional_text(form.get("avatar_url")),
    }
    maiden_name = (form.get("maiden_name_ru") or "").strip() or None
    person_data["maiden_name"] = maiden_name

    ru_data = {
        "first_name": ru_first_name,
        "last_name": (form.get("last_name_ru") or "").strip() or None,
        "patronymic": (form.get("patronymic_ru") or "").strip() or None,
        "biography": (form.get("biography_ru") or "").strip() or None,
    }

    en_data = {
        "first_name": (form.get("first_name_en") or "").strip(),
        "last_name": (form.get("last_name_en") or "").strip() or None,
        "patronymic": (form.get("patronymic_en") or "").strip() or None,
        "biography": (form.get("biography_en") or "").strip() or None,
    }

    try:
        update_person_with_i18n(
            db,
            person_id=person_id,
            person_data=person_data,
            ru_data=ru_data,
            en_data=en_data,
        )
    except IntegrityError as exc:
        db.rollback()
        details = str(getattr(exc, "orig", exc)).lower()
        if "messenger_max_id" in details and "unique" in details:
            return render_error("Такой Max ID уже существует")
        if "preferred_ch" in details or "people_preferred_ch_check" in details:
            return render_error("Недопустимое значение канала связи")
        return render_error("Не удалось сохранить запись, проверь поля контактов")
    except ValueError as exc:
        return render_error(str(exc))
    except Exception as exc:
        return render_error(f"Ошибка при сохранении персоны: {exc}")

    return RedirectResponse(url="/admin/people", status_code=302)


@router.get("/unions/new", response_class=HTMLResponse)
async def admin_union_new_form(
    person_id: int, request: Request, db: Session = Depends(get_db)
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    person = db.query(Person).filter(Person.person_id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    return templates.TemplateResponse(
        "admin/admin_union_new.html",
        {
            "request": request,
            "error": None,
            "person": person,
            "person_name": _person_name_ru(db, person.person_id),
            "people_options": _build_people_options(
                db, exclude_person_ids={person.person_id}
            ),
            "form_data": {
                "person_id": person.person_id,
                "partner_id": "",
                "start_date": "",
                "end_date": "",
            },
        },
    )


@router.post("/unions/new", response_class=HTMLResponse)
async def admin_union_new_submit(request: Request, db: Session = Depends(get_db)):
    redirect = require_admin(request)
    if redirect:
        return redirect

    form = await request.form()

    def render_error(message: str, status_code: int = 400):
        person_id_raw = str(form.get("person_id") or "").strip()
        person_id_for_context = int(person_id_raw) if person_id_raw.isdigit() else None
        person_for_context = None
        person_name = ""
        excluded: set[int] = set()
        if person_id_for_context is not None:
            person_for_context = (
                db.query(Person)
                .filter(Person.person_id == person_id_for_context)
                .first()
            )
            excluded = {person_id_for_context}
            if person_for_context:
                person_name = _person_name_ru(db, person_for_context.person_id)

        return templates.TemplateResponse(
            "admin/admin_union_new.html",
            {
                "request": request,
                "error": message,
                "person": person_for_context,
                "person_name": person_name,
                "people_options": _build_people_options(
                    db, exclude_person_ids=excluded
                ),
                "form_data": dict(form),
            },
            status_code=status_code,
        )

    try:
        person_id = int(str(form.get("person_id") or "").strip())
    except Exception:
        return render_error("Некорректный person_id")

    try:
        partner_id = int(str(form.get("partner_id") or "").strip())
    except Exception:
        return render_error("Выберите партнёра")

    if partner_id == person_id:
        return render_error("Партнёр должен отличаться от выбранной персоны")

    person = db.query(Person).filter(Person.person_id == person_id).first()
    if not person:
        return render_error("Персона не найдена", status_code=404)

    partner = db.query(Person).filter(Person.person_id == partner_id).first()
    if not partner:
        return render_error("Партнёр не найден")

    start_date = _clean_optional_text(form.get("start_date"))
    end_date = _clean_optional_text(form.get("end_date"))

    union = Union(
        partner1_id=person_id,
        partner2_id=partner_id,
        start_date=start_date,
        end_date=end_date,
    )
    try:
        _sync_pk_sequence(db, "Unions")
        db.add(union)
        db.commit()
    except IntegrityError:
        db.rollback()
        return render_error(
            "Не удалось создать союз. Проверьте выбранных участников и попробуйте снова."
        )
    except Exception as exc:
        db.rollback()
        return render_error(f"Ошибка при создании союза: {exc}")

    return RedirectResponse(url=f"/admin/people/{person_id}/edit", status_code=303)


@router.get("/unions/{union_id}/add-child", response_class=HTMLResponse)
async def admin_union_add_child_form(
    union_id: int,
    request: Request,
    person_id: int | None = None,
    db: Session = Depends(get_db),
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    union = db.query(Union).filter(Union.id == union_id).first()
    if not union:
        raise HTTPException(status_code=404, detail="Union not found")

    context_person_id = person_id or union.partner1_id or union.partner2_id

    return templates.TemplateResponse(
        "admin/admin_union_add_child.html",
        {
            "request": request,
            "error": None,
            "union": union,
            "person_id": context_person_id,
            "partner1_name": _person_name_ru(db, union.partner1_id),
            "partner2_name": _person_name_ru(db, union.partner2_id),
            "people_options": _build_people_options(db),
            "form_data": {
                "child_id": "",
                "person_id": context_person_id or "",
            },
        },
    )


@router.post("/unions/{union_id}/add-child", response_class=HTMLResponse)
async def admin_union_add_child_submit(
    union_id: int, request: Request, db: Session = Depends(get_db)
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    union = db.query(Union).filter(Union.id == union_id).first()
    if not union:
        raise HTTPException(status_code=404, detail="Union not found")

    form = await request.form()

    def render_error(message: str):
        person_id_raw = str(form.get("person_id") or "").strip()
        person_id_for_context = int(person_id_raw) if person_id_raw.isdigit() else None
        return templates.TemplateResponse(
            "admin/admin_union_add_child.html",
            {
                "request": request,
                "error": message,
                "union": union,
                "person_id": person_id_for_context,
                "partner1_name": _person_name_ru(db, union.partner1_id),
                "partner2_name": _person_name_ru(db, union.partner2_id),
                "people_options": _build_people_options(db),
                "form_data": dict(form),
            },
            status_code=400,
        )

    try:
        child_id = int(str(form.get("child_id") or "").strip())
    except Exception:
        return render_error("Выберите ребёнка")

    child = db.query(Person).filter(Person.person_id == child_id).first()
    if not child:
        return render_error("Ребёнок не найден")

    duplicate = (
        db.query(UnionChild)
        .filter(UnionChild.union_id == union_id, UnionChild.child_id == child_id)
        .first()
    )
    if duplicate:
        return render_error("Такой ребёнок уже добавлен в этот союз")

    link = UnionChild(union_id=union_id, child_id=child_id)
    try:
        _sync_pk_sequence(db, "UnionChildren")
        db.add(link)
        db.commit()
    except IntegrityError:
        db.rollback()
        return render_error("Не удалось добавить ребёнка к союзу. Попробуйте снова.")
    except Exception as exc:
        db.rollback()
        return render_error(f"Ошибка при добавлении ребёнка: {exc}")

    person_id_raw = str(form.get("person_id") or "").strip()
    person_id_for_redirect = int(person_id_raw) if person_id_raw.isdigit() else None
    fallback_person_id = union.partner1_id or union.partner2_id
    redirect_person_id = person_id_for_redirect or fallback_person_id

    if redirect_person_id:
        return RedirectResponse(
            url=f"/admin/people/{redirect_person_id}/edit", status_code=303
        )
    return RedirectResponse(url="/admin/people", status_code=303)


def _qr_png_b64(otpauth_uri: str) -> str:
    img = qrcode.make(otpauth_uri, box_size=4, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _absolute_app_base_url(request: Request) -> str:
    """Схема+хост для публичных ссылок: прокси (TW_PUBLIC_BASE_URL) или Host из запроса, иначе дефолт."""
    o = (os.environ.get("TW_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if o:
        return o
    b = str(request.base_url).rstrip("/")
    if b and b not in ("http://", "https://"):
        return b
    return (
        (os.environ.get("TW_DEFAULT_PUBLIC_BASE_URL") or "https://app.timewoven.ru")
        .strip()
        .rstrip("/")
    )


def _family_profile_public_url(request: Request, public_uuid) -> str:
    """Ссылка на семейный профиль по public_uuid: https://…/family/p/{uuid}."""
    base = _absolute_app_base_url(request)
    s = (str(public_uuid) if public_uuid is not None else "").strip()
    if not s or s == "None":
        return ""
    return f"{base}/family/p/{s}"


def _ensure_public_uuid(db: Session, person: Person) -> None:
    """Публичный UUID обязателен для ссылки; при отсутствии — присваиваем и сохраняем (как в /access/setup)."""
    if person.public_uuid is not None:
        return
    person.public_uuid = uuid4()
    db.commit()
    db.refresh(person)


@router.get(
    "/people/{person_id}/access",
    response_class=HTMLResponse,
    name="admin_person_access_page",
)
async def admin_person_access_page(
    person_id: int, request: Request, db: Session = Depends(get_db)
):
    redir = require_admin(request)
    if redir:
        return redir
    person = db.query(Person).filter(Person.person_id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    _ensure_public_uuid(db, person)
    name = _person_name_ru(db, person_id)
    pending = bool(
        person.totp_secret_encrypted
        and not person.family_access_enabled
        and not person.family_access_revoked_at
    )
    n_sessions = (
        db.query(FamilyAccessSession)
        .filter(
            FamilyAccessSession.person_id == person_id,
            FamilyAccessSession.revoked_at.is_(None),
        )
        .count()
    )
    n_backup = (
        db.query(PersonAccessBackupCode)
        .filter(
            PersonAccessBackupCode.person_id == person_id,
            PersonAccessBackupCode.used_at.is_(None),
        )
        .count()
    )
    family_public_url = _family_profile_public_url(request, person.public_uuid)
    return templates.TemplateResponse(
        "admin/person_access.html",
        {
            "request": request,
            "person": person,
            "name": name,
            "pending": pending,
            "access_permitted": person_family_access_permitted(person),
            "n_active_sessions": n_sessions,
            "n_backup_left": n_backup,
            "family_public_url": family_public_url,
        },
    )


@router.post("/people/{person_id}/access/setup", response_class=HTMLResponse)
async def admin_person_access_setup(
    person_id: int, request: Request, db: Session = Depends(get_db)
):
    redir = require_admin(request)
    if redir:
        return redir
    person = db.query(Person).filter(Person.person_id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    if person.public_uuid is None:
        person.public_uuid = uuid4()
    person.family_access_revoked_at = None
    secret = pyotp.random_base32()
    codes = [generate_backup_code_plain() for _ in range(8)]
    person.totp_secret_encrypted = encrypt_totp_secret(secret)
    person.family_access_enabled = False
    person.totp_enabled_at = None
    person.totp_last_used_at = None
    clear_backup_codes(db, person_id)
    store_backup_codes(db, person_id, codes)
    db.commit()
    label = f"{_person_name_ru(db, person_id)} (TW)"
    uri = new_totp_provisioning_uri(secret, label)
    b64 = _qr_png_b64(uri)
    return templates.TemplateResponse(
        "admin/person_access_setup.html",
        {
            "request": request,
            "person": person,
            "name": _person_name_ru(db, person_id),
            "qr_data_uri": f"data:image/png;base64,{b64}",
            "otpauth_uri": uri,
            "backup_codes": codes,
            "public_uuid": str(person.public_uuid),
        },
    )


@router.post("/people/{person_id}/access/confirm", response_class=HTMLResponse)
async def admin_person_access_confirm(
    person_id: int,
    request: Request,
    code: str = Form(...),
    db: Session = Depends(get_db),
):
    redir = require_admin(request)
    if redir:
        return redir
    person = db.query(Person).filter(Person.person_id == person_id).first()
    if not person or not person.totp_secret_encrypted:
        raise HTTPException(status_code=400, detail="Run setup first")
    try:
        raw = decrypt_totp_secret(person.totp_secret_encrypted)
    except Exception:
        return RedirectResponse(
            url=f"/admin/people/{person_id}/access?err=crypto", status_code=303
        )
    if not verify_totp_code(raw, code):
        return RedirectResponse(
            url=f"/admin/people/{person_id}/access?err=bad_code", status_code=303
        )
    now = datetime.now(timezone.utc)
    person.family_access_enabled = True
    if person.totp_enabled_at is None:
        person.totp_enabled_at = now
    person.family_access_revoked_at = None
    db.commit()
    db.refresh(person)
    return RedirectResponse(
        url=f"/admin/people/{person_id}/access?activated=1", status_code=303
    )


@router.post("/people/{person_id}/access/reset", response_class=HTMLResponse)
async def admin_person_access_reset(
    person_id: int, request: Request, db: Session = Depends(get_db)
):
    redir = require_admin(request)
    if redir:
        return redir
    person = db.query(Person).filter(Person.person_id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    person.totp_secret_encrypted = None
    person.family_access_enabled = False
    person.totp_enabled_at = None
    person.totp_last_used_at = None
    person.family_access_revoked_at = datetime.now(timezone.utc)
    clear_backup_codes(db, person_id)
    revoke_all_sessions_for_person(db, person_id)
    db.commit()
    return RedirectResponse(url=f"/admin/people/{person_id}/access", status_code=303)


@router.post("/people/{person_id}/access/revoke-sessions", response_class=HTMLResponse)
async def admin_person_access_revoke_sessions(
    person_id: int, request: Request, db: Session = Depends(get_db)
):
    redir = require_admin(request)
    if redir:
        return redir
    person = db.query(Person).filter(Person.person_id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    revoke_all_sessions_for_person(db, person_id)
    return RedirectResponse(url=f"/admin/people/{person_id}/access", status_code=303)


SECRET = "super-secret-timewoven-key"
