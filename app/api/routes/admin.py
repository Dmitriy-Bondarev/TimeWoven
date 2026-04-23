import json
import os

# app/routes/admin.py

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.bot.max_messenger import MaxMessengerBot
from app.db.session import get_db
from app.models import Memory, Person, PersonI18n, Quote
from app.services import create_person_with_i18n
from app.security import get_daily_password, require_admin, make_admin_token, ADMIN_COOKIE_NAME

BASE_DIR = Path(__file__).resolve().parents[2]
router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)

templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))


def _clean_optional_text(value: object) -> str | None:
    text_value = str(value or "").strip()
    return text_value or None


def _normalize_preferred_channel(raw_value: object, is_alive: bool) -> str | None:
    """Map UI channel values to DB-compatible values; no channel is stored as NULL."""
    normalized = str(raw_value or "").strip().upper()

    if not normalized:
        return None if not is_alive else None

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
        if m.transcript_verbatim:
            try:
                metadata = json.loads(m.transcript_verbatim)
            except (json.JSONDecodeError, TypeError):
                metadata = {}

            local_audio_path = metadata.get("local_audio_path") if isinstance(metadata, dict) else None
            if isinstance(local_audio_path, str) and local_audio_path.strip():
                audio_player_src = local_audio_path.strip()
                audio_source = "local"

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
                "created_at": m.created_at,
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
    expected_username = os.getenv("ADMIN_USERNAME", "admin")
    expected_password = os.getenv("ADMIN_PASSWORD", "")

    if username == expected_username and password == expected_password:
        # Validate next to prevent open redirect: only relative internal paths allowed
        safe_next = (
            next
            if (next and next.startswith("/") and not next.startswith("//") and "://" not in next)
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
        return response

    return templates.TemplateResponse(
        "admin/admin_login.html",
        {"request": request, "next": next, "error": "Неверные учётные данные"},
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
            [p for p in (i18n.first_name if i18n else None, i18n.last_name if i18n else None) if p]
        ).strip()
        if not name:
            name = f"Персона #{person.person_id}"

        people.append({"id": person.person_id, "name": name, "avatar_url": person.avatar_url})

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

    avatar_dir = BASE_DIR / "web" / "static" / "images" / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    filename = f"person_{person_id}_{uuid4().hex}{suffix}"
    target = avatar_dir / filename

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    target.write_bytes(content)
    person.avatar_url = f"/static/images/avatars/{filename}"
    db.commit()

    return RedirectResponse(url="/admin/avatars", status_code=303)


@router.get("/people", response_class=HTMLResponse)
async def admin_people(request: Request, db: Session = Depends(get_db)):
    redirect = require_admin(request)
    if redirect:
        return redirect

    people = (
        db.query(Person)
        .order_by(Person.person_id)
        .all()
    )

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
            [part for part in (i18n.first_name if i18n else None, i18n.last_name if i18n else None) if part]
        ).strip()
        if not name:
            name = f"Персона #{p.person_id}"

        memories_count = db.query(Memory).filter(Memory.author_id == p.person_id).count()
        quotes_count = db.query(Quote).filter(Quote.author_id == p.person_id).count()

        rows.append({
            "person_id": p.person_id,
            "name": name,
            "role": p.role or "",
            "phone": p.phone or "",
            "preferred_ch": p.preferred_ch or "",
            "messenger_max_id": p.messenger_max_id or "",
            "messenger_tg_id": p.messenger_tg_id or "",
            "contact_email": p.contact_email or "",
            "is_alive": p.is_alive,
            "avatar_url": p.avatar_url,
            "memories_count": memories_count,
            "quotes_count": quotes_count,
        })

    return templates.TemplateResponse(
        "admin/admin_people.html",
        {"request": request, "rows": rows},
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
        preferred_ch = _normalize_preferred_channel(form.get("preferred_ch"), is_alive=is_alive)
    except ValueError as exc:
        return render_error(str(exc))

    birth_date_prec = (form.get("birth_date_prec") or "").strip() or None
    death_date_prec = (form.get("death_date_prec") or "").strip() or None
    allowed_precisions = {"EXACT", "ABOUT", "YEARONLY", "DECADE"}
    if birth_date_prec and birth_date_prec not in allowed_precisions:
        return render_error("Некорректная точность даты рождения.")
    if death_date_prec and death_date_prec not in allowed_precisions:
        return render_error("Некорректная точность даты смерти.")

    person_data = {
        "gender": gender,
        "is_alive": is_alive,
        "role": (form.get("role") or "placeholder").strip() or "placeholder",
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