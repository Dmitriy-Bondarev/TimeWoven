import logging
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from urllib.parse import quote, unquote, urlparse

from fastapi import APIRouter, Depends, Form, Query, HTTPException, Request, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, or_, func, false
from sqlalchemy.orm import Session

from app.core.i18n import install_jinja_i18n
from app.core.media_urls import default_family_slug, family_data_path_for_slug, normalize_media_url
from app.core.whoami_experiment import is_whoami_experiment_enabled
from app.db.session import get_db
from app.models import Memory, Person, PersonI18n, Quote
from app.schemas.family_graph import FamilyGraph
from app.services.family_graph import build_family_graph
from app.services.timeline_event_view import memory_to_timeline_event_view, TimelineEventView
from app.services.family_access_service import (
    DEFAULT_SESSION_TTL,
    check_rate_limit,
    create_family_access_session,
    decrypt_totp_secret,
    find_person_by_public_uuid,
    person_family_access_permitted,
    resolve_viewer,
    set_family_access_cookies,
    set_totp_last_used,
    use_one_backup_code,
    verify_totp_code,
)

BASE_DIR = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))
install_jinja_i18n(templates)

logger = logging.getLogger(__name__)

router = APIRouter()
FAMILY_COOKIE_NAME = "family_member_id"
FAMILY_SESSION_MAX_AGE = 60 * 60 * 24
FAMILY_NEED_ACCESS_PATH = "/family/need-access"
_JSON_BLOB_RE = re.compile(r"^\s*[\[{].*[\]}]\s*$", re.DOTALL)


def _looks_like_technical_blob(text: str) -> bool:
    """Hide raw payloads/json-like blobs from public family timeline."""
    cleaned = (text or "").strip()
    if not cleaned:
        return True

    if _JSON_BLOB_RE.match(cleaned):
        return True

    lowered = cleaned.lower()
    if lowered.startswith("{'raw':") or lowered.startswith('{"raw":'):
        return True

    return False


def _is_live_visible_person(model):
    return model.record_status == "active"


def _role_caption_friendly(role: str | None) -> str:
    r = (role or "").strip().lower() or "relative"
    mapping = {
        "family_admin": "Администратор семьи",
        "familyadmin": "Администратор семьи",
        "relative": "Родственник",
        "placeholder": "Участник семьи",
        "bot_only": "Голос бота",
    }
    return mapping.get(r, r.replace("_", " "))


def _memory_display_text(m: Memory) -> str:
    return (m.transcript_readable or m.transcript_verbatim or m.content_text or "").strip()


def _text_excerpt(text: str, max_len: int = 220) -> str:
    t = (text or "").replace("\n", " ").strip()
    if len(t) <= max_len:
        return t
    cut = t[: max_len + 1]
    if " " in cut:
        return cut.rsplit(" ", 1)[0] + "…"
    return cut[:max_len] + "…"


def _text_excerpt_consumed_len(flat: str, max_len: int) -> int:
    """
    Сколько символов с начала flat входит в тот же отрезок, что и _text_excerpt(flat, max_len), без суррогатов/…:
    длина префикса в источнике, который покрывает видимая строка (без многоточия-разделителя).
    """
    t = (flat or "").replace("\n", " ").strip()
    if len(t) <= max_len:
        return len(t)
    cut = t[: max_len + 1]
    if " " in cut:
        s = cut.rsplit(" ", 1)[0]
        return len(s)
    return max_len


def _nonempty_display_str(s: object | None) -> str | None:
    """Omit empty, None, and string null-placeholders (any case) from UI. Single gate for profile hero strings."""
    if s is None:
        return None
    if not isinstance(s, str):
        s = str(s)
    t = (s or "").strip()
    if not t:
        return None
    low = t.lower()
    if low in ("none", "null", "undefined"):
        return None
    return t


def _quality_hero_subtitle(raw: str | None) -> str | None:
    base = _nonempty_display_str((raw or "").strip() if raw is not None else None)
    if base is None:
        return None
    t = _text_excerpt(base, 300)
    return _nonempty_display_str(t)


def _hero_date_humane_for_display(s: str) -> str | None:
    """
    YYYY-MM-DD, DD.MM.YYYY (any zero-padding) or YYYY (year) → display string, never raw ISO in output.
    """
    t0 = (s or "").strip()
    if not t0:
        return None
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", t0)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{d:02d}.{mo:02d}.{y}"
        return str(y)  # сырой ISO с нелегальным днём/месяцем — не показывать D.M, только год
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", t0)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{d:02d}.{mo:02d}.{y}"
    m = re.match(r"^(\d{4})$", t0)
    if m:
        return m.group(1)
    return _nonempty_display_str(t0)


def _hero_lifespan_caption(
    birth_raw: str | None,
    death_raw: str | None,
) -> str | None:
    """
    /family/person hero: только нормализованные даты (через _hero_date_humane_for_display), без ISO и без сырого «р.».
    - Только дата рождения:  «Дата рождения: ДД.ММ.ГГГГ» (при валидном парсе).
    - Рождение и смерть:  «Годы жизни: … — …» (и две полные даты, и две сокращения до годов, и любая смешанная — всё в humane-форме).
    - Только смерть:  «Дата смерти: …»
    """
    bdv = _hero_date_humane_for_display(birth_raw) if birth_raw else None
    ddv = _hero_date_humane_for_display(death_raw) if death_raw else None
    if not bdv and not ddv:
        return None
    if bdv and ddv:
        return f"Годы жизни: {bdv} — {ddv}"
    if bdv:
        return f"Дата рождения: {bdv}"
    return f"Дата смерти: {ddv}" if ddv else None


def _family_hero_subtitle_one_line(person: Person, person_i18n: PersonI18n | None) -> str | None:
    """
    One human line under the name for /family/person: dates (not ISO), maiden, short bio.
    Patronymic is not used here (only with first+last in the title line, see family_person).
    """
    parts: list[str] = []
    bd = _nonempty_display_str(getattr(person, "birth_date", None) or None)
    dd = _nonempty_display_str(getattr(person, "death_date", None) or None)
    if bd or dd:
        line = _hero_lifespan_caption(bd, dd)
        if line:
            parts.append(line)
    last_for_maiden = _nonempty_display_str(
        person_i18n.last_name if person_i18n else None
    ) if person_i18n else None
    maiden = _nonempty_display_str(getattr(person, "maiden_name", None) or None)
    if maiden and maiden != (last_for_maiden or ""):
        parts.append(f"урожд. {maiden}")
    if person_i18n is not None:
        bio_s = _nonempty_display_str(person_i18n.biography)
    else:
        bio_s = None
    if bio_s:
        b = _quality_hero_subtitle(bio_s)
        if b:
            parts.append(b)
    if not parts:
        return None
    full = " · ".join(parts)
    return _quality_hero_subtitle(full)


_RU_FIRST_NAME_GENT: dict[str, str] = {
    "александр": "Александра",
    "алексей": "Алексея",
    "андрей": "Андрея",
    "артём": "Артёма",
    "артем": "Артема",
    "борис": "Бориса",
    "вадим": "Вадима",
    "валерий": "Валерия",
    "виктор": "Виктора",
    "владимир": "Владимира",
    "василий": "Василия",
    "вячеслав": "Вячеслава",
    "григорий": "Григория",
    "геннадий": "Геннадия",
    "дмитрий": "Дмитрия",
    "денис": "Дениса",
    "евгений": "Евгения",
    "егор": "Егора",
    "иван": "Ивана",
    "игорь": "Игоря",
    "кирилл": "Кирилла",
    "константин": "Константина",
    "лев": "Льва",
    "максим": "Максима",
    "михаил": "Михаила",
    "николай": "Николая",
    "олег": "Олега",
    "павел": "Павла",
    "пётр": "Петра",
    "петр": "Петра",
    "роман": "Романа",
    "сергей": "Сергея",
    "станислав": "Станислава",
    "тимур": "Тимура",
    "юрий": "Юрия",
    "даниил": "Даниила",
    "анна": "Анны",
    "анастасия": "Анастасии",
    "алёна": "Алёны",
    "алена": "Алены",
    "елена": "Елены",
    "мария": "Марии",
    "наталья": "Натальи",
    "оксана": "Оксаны",
    "ольга": "Ольги",
    "светлана": "Светланы",
    "татьяна": "Татьяны",
    "виктория": "Виктории",
    "даша": "Даши",
    "саша": "Саши",
    "коля": "Коли",
    "миша": "Миши",
    "наташа": "Наташи",
    "тося": "Тоси",
}


def _ru_first_name_genitive_for_photo(first: str | None) -> str | None:
    """
    Род. п. (или близкие формы) имени для «фото {имя}…»: словарь + простые окончания; при сомнении — как в исходнике.
    """
    t0 = _nonempty_display_str(first) if first else None
    if not t0:
        return None
    key = t0.lower().strip()
    if key in _RU_FIRST_NAME_GENT:
        g = _RU_FIRST_NAME_GENT[key]
    else:
        tlow = t0.lower()
        g: str
        if len(tlow) >= 4 and tlow.endswith("ия"):
            g = t0[:-2] + "ии"
        elif len(tlow) >= 2 and tlow.endswith("ья"):
            g = t0[:-2] + "ьи"
        elif len(tlow) >= 2 and tlow.endswith("ий"):
            g = t0[:-2] + "ия"
        elif len(tlow) >= 2 and tlow.endswith("ей"):
            g = t0[:-2] + "ея"
        elif len(tlow) >= 1 and tlow.endswith("й") and not tlow.endswith("ий") and not tlow.endswith("ей"):
            g = t0[:-1] + "я"
        elif tlow.endswith("ь"):
            g = t0[:-1] + "я"
        elif tlow and tlow[-1] in "бвгджзклмнпрстфхцчшщ":
            g = t0 + "а"
        elif tlow.endswith("а") and len(tlow) >= 2:
            g = t0[:-1] + "ы"
        elif tlow.endswith("я") and len(tlow) >= 2 and not tlow.endswith("ия") and not tlow.endswith("ья"):
            g = t0[:-1] + "и"
        elif tlow.endswith("о") and len(tlow) >= 2:
            g = t0[:-1] + "а"
        else:
            g = t0
    if t0[0].isupper() and g and g[0].islower():
        g = g[0].upper() + g[1:]
    return g


def _name_tokens_for_search(person_i18n: PersonI18n | None) -> list[str]:
    """Short tokens (first/last name) for memory text search, min length 2."""
    toks: list[str] = []
    for raw in (person_i18n.first_name if person_i18n else None, person_i18n.last_name if person_i18n else None):
        t = _nonempty_display_str(raw)
        if t and len(t) >= 2:
            toks.append(t)
    return list(dict.fromkeys(toks))  # dedupe, preserve order


def _author_display_name(session: Session, author_id: int | None) -> str:
    if not author_id:
        return "Автор"
    i18n = (
        session.query(PersonI18n)
        .filter(
            PersonI18n.person_id == author_id,
            PersonI18n.lang_code == "ru",
        )
        .first()
    )
    n = " ".join(
        [p for p in (i18n.first_name if i18n else None, i18n.last_name if i18n else None) if p]
    ).strip()
    return n or f"Персона #{author_id}"


def _memory_has_audio(m: Memory | None) -> bool:
    if m is None:
        return False
    return bool((m.audio_url or "").strip())


def _public_memory_list_item(session: Session, m: Memory) -> dict:
    text = _memory_display_text(m)
    if not text or _looks_like_technical_blob(text):
        return {}
    return {
        "id": m.id,
        "excerpt": _text_excerpt(text),
        "date_display": (m.created_at or "—")[:10],
        "author_name": _author_display_name(session, m.author_id),
        "has_audio": _memory_has_audio(m),
    }


def _strip_test_title_prefix(s: str) -> str:
    """
    Убирает служебные префиксы Тест_/тест/Тест_ в начале строки (без учёта регистра).
    """
    t = (s or "").strip()
    if not t:
        return t
    t2 = re.sub(r"^(?i)тест[_\s]+", "", t, count=1).strip()
    return t2 if t2 else t


def _ru_count_phrase(
    n: int,
    *,
    one: str,
    two_four: str,
    other: str,
) -> str:
    """1 история, 2 истории, 5 историй — without broken forms like "3 историй"."""
    n = int(n)
    na = abs(n) % 100
    n1 = na % 10
    if 11 <= na <= 14:
        return f"{n} {other}"
    if n1 == 1:
        return f"{n} {one}"
    if 2 <= n1 <= 4:
        return f"{n} {two_four}"
    return f"{n} {other}"


def _year_key_from_memory(m: Memory) -> str:
    s = (m.created_at or "").strip()
    if len(s) >= 4 and s[:4].isdigit():
        return s[:4]
    return "—"


def _memory_kind_label(m: Memory) -> str:
    st = (getattr(m, "source_type", None) or "").strip().lower()
    if st in ("event", "event_driven", "событие"):
        return "Событие"
    if st in ("note", "thought", "reflection", "мысль", "diary"):
        return "Мысль"
    return "История"


_OWN_STORY_TITLE_MAX = 100
_OWN_STORY_PREVIEW_MAX = 220

# Служебная вводная «Средняя/Короткая/… история:» (после опционального Тест_). Исходный Тест_ в памяти не трогаем;
# из заголовка карточки убираем только эту вводную, без изменения сырой строки в БД.
_RE_OWN_STORY_SERVICE_LABEL = re.compile(
    r"^(?i)(?P<tp>тест_)?\s*"
    r"(?P<lab>(?:(?:очень\s+)?короткая|средняя|длинная)\s+история)\s*:\s*"
    r"(?P<rest>.*)$"
)


def _own_story_line_title_src(first_line: str) -> str:
    """
    Убирает из первой строки только метку (средняя|короткая|длинная) история: …, сохраняя остаток
    и опциональный ведущий «Тест_» в том виде, как в источнике.
    """
    s = (first_line or "").strip()
    if not s:
        return ""
    m = _RE_OWN_STORY_SERVICE_LABEL.match(s)
    if not m:
        return s
    tp = m.group("tp") or ""
    rest = (m.group("rest") or "").lstrip()
    if not rest:
        return s
    if tp:
        if rest and not (tp.endswith(" ") or rest[0] in " \t"):
            return f"{tp} {rest}"
        return f"{tp}{rest}"
    return rest


def _own_memory_body_preview_for_card(full: str) -> str:
    """
    Превью «Свои истории»: не дублирует заголовок.
    - Если в тексте есть \\n: берём все строки после первой, склеиваем, укорачиваем.
    - Если одна строка: превью — хвост после первого .!?… в строке, приведённой к тому же title_src, что
      и в карточке (тот же _own_story_line_title_src, без смены исходника в БД). Если хвоста нет — «».
    """
    full = (full or "").replace("\r\n", "\n").strip()
    if not full:
        return ""
    if "\n" in full:
        rest = full.split("\n", 1)[1].strip()
        if not rest:
            return ""
        lines = [x.strip() for x in rest.split("\n") if x.strip()]
        joined = " ".join(lines)
        return _text_excerpt(joined, _OWN_STORY_PREVIEW_MAX) if joined else ""
    line0 = full.strip()
    lead = _own_story_line_title_src(line0)
    if not lead:
        return ""
    m = re.search(r"[.!?…](?=\s|$)", lead)
    if not m:
        return ""
    if m.end() >= len(lead.rstrip()):
        return ""
    # Не дублировать хвост заголовка, если в заголовок вошла только часть первой(ых) фраз(ы)
    L = _text_excerpt_consumed_len(lead, _OWN_STORY_TITLE_MAX)
    start = max(L, m.end())
    if start >= len(lead):
        return ""
    tail = lead[start:].strip()
    return _text_excerpt(tail, _OWN_STORY_PREVIEW_MAX) if tail else ""


def _own_memory_date_display(created: object) -> str:
    """DD.MM.YYYY, как в подзаголовке /family/person; без сырого ISO в карточке при нормальной дате."""
    raw = (created or "") if isinstance(created, str) else (str(created) if created is not None else "")
    raw = (raw or "").strip()
    if not raw:
        return "—"
    if len(raw) >= 10:
        ds = raw[:10]
        if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", ds):
            return _hero_date_humane_for_display(ds) or ds
    return raw[:10] if len(raw) >= 8 else "—"


_RU_MONTHS_SHORT_3 = (
    "янв",
    "фев",
    "мар",
    "апр",
    "май",
    "июн",
    "июл",
    "авг",
    "сен",
    "окт",
    "ноя",
    "дек",
)


def _family_timeline_date_display(value: object) -> str:
    """
    Дата в /family/timeline (и тот же шаблон): «24 апр 2026», без времени.
    Сортировка элементов по полю «date» не использует это поле.
    """
    return _own_memory_date_line_for_card(value)


def _own_memory_date_line_for_card(created: object) -> str:
    """
    Одна строка для мини‑таймлайна: «24 апр 2026»; год — если только год; иначе как _own_memory_date_display.
    """
    raw = (created or "") if isinstance(created, str) else (str(created) if created is not None else "")
    raw = (raw or "").strip()
    if not raw:
        return "—"
    if len(raw) >= 10:
        ds = raw[:10]
        m0 = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", ds)
        if m0:
            y, mo, d = int(m0.group(1)), int(m0.group(2)), int(m0.group(3))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{d} {_RU_MONTHS_SHORT_3[mo - 1]} {y}"
    m1 = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", raw[:10] if len(raw) >= 10 else raw)
    if m1:
        d, mo, y = int(m1.group(1)), int(m1.group(2)), int(m1.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{d} {_RU_MONTHS_SHORT_3[mo - 1]} {y}"
    m2 = re.match(r"^(\d{4})$", raw)
    if m2:
        return m2.group(1)
    return _own_memory_date_display(created)


def _family_own_memory_card(session: Session, m: Memory) -> dict:
    text = _memory_display_text(m)
    if not text or _looks_like_technical_blob(text):
        return {}
    first_line = text.split("\n", 1)[0].strip()
    title_src = _own_story_line_title_src(first_line)
    display_title = _text_excerpt(title_src, _OWN_STORY_TITLE_MAX).strip() if title_src else ""
    if not display_title or not display_title.replace("…", "").strip():
        display_title = "Без заголовка"
    preview = _own_memory_body_preview_for_card(text)
    yk = _year_key_from_memory(m)
    return {
        "id": m.id,
        "title": display_title,
        "preview": preview,
        "date_display": _own_memory_date_display(m.created_at),
        "date_line": _own_memory_date_line_for_card(m.created_at),
        "year_key": yk,
        "kind_label": _memory_kind_label(m),
        "has_audio": _memory_has_audio(m),
    }


def _group_own_memories_by_year(rows: list[dict]) -> list[tuple[str, list[dict]]]:
    from collections import defaultdict

    buck: dict[str, list[dict]] = defaultdict(list)
    for d in rows:
        yk = d.get("year_key") or "—"
        buck[yk].append(d)
    years = list(buck.keys())

    def _yk_sort(y: str) -> tuple:
        if y.isdigit():
            return (0, -int(y))
        return (1, 0)

    years.sort(key=_yk_sort)
    return [(y, buck[y]) for y in years]


def _get_family_member_id(request: Request) -> int | None:
    raw = request.cookies.get(FAMILY_COOKIE_NAME, "").strip()
    if not raw or not raw.isdigit():
        return None
    return int(raw)


def _require_family_session(request: Request, db: Session | None = None) -> RedirectResponse | None:
    if db is not None and resolve_viewer(request, db) is not None:
        return None
    if _get_family_member_id(request) is not None:
        return None
    next_url = request.url.path
    if request.url.query:
        next_url = f"{next_url}?{request.url.query}"
    encoded_next = quote(next_url, safe="/")
    return RedirectResponse(
        url=f"{FAMILY_NEED_ACCESS_PATH}?next={encoded_next}",
        status_code=303,
    )


def _redirect_if_whoami_disabled(*, next_url: str | None) -> RedirectResponse | None:
    if is_whoami_experiment_enabled():
        return None
    if next_url and next_url.strip():
        return RedirectResponse(
            url=f"{FAMILY_NEED_ACCESS_PATH}?next={quote(next_url.strip(), safe='/')}",
            status_code=303,
        )
    return RedirectResponse(url=FAMILY_NEED_ACCESS_PATH, status_code=303)


@router.get(FAMILY_NEED_ACCESS_PATH, response_class=HTMLResponse)
@router.get("/f/{slug}" + FAMILY_NEED_ACCESS_PATH, response_class=HTMLResponse)
async def family_need_access(
    request: Request,
    next: str = Query("/family/welcome", description="Куда вернуться после входа по семейной ссылке"),
):
    return templates.TemplateResponse(
        "family/need_family_access.html",
        {
            "request": request,
            "next": next,
        },
    )


def _safe_internal_next_url(next_url: str | None, default: str) -> str:
    n = (next_url or "").strip()
    if n.startswith("/") and not n.startswith("//"):
        return n
    return default


@router.get("/family/p/{public_uuid}")
@router.get("/f/{slug}/family/p/{public_uuid}")
async def family_public_entry(
    request: Request,
    public_uuid: str,
    db: Session = Depends(get_db),
):
    """Публичная точка входа по ссылке из админки: валидная сессия → золотое воспоминание, иначе → TOTP."""
    person = find_person_by_public_uuid(db, public_uuid)
    if not person or not _is_live_visible_person(person):
        raise HTTPException(status_code=404, detail="Not found")
    viewer = resolve_viewer(request, db)
    if viewer is not None and viewer.person_id == person.person_id:
        return RedirectResponse(
            url="/family/welcome",
            status_code=303,
        )
    default_next = "/family/welcome"
    enc_next = quote(default_next, safe="/?&=")
    u = (public_uuid or "").strip()
    return RedirectResponse(
        url=f"/family/access/{u}?next={enc_next}",
        status_code=303,
    )


@router.get("/family/access/{public_uuid}", response_class=HTMLResponse)
@router.get("/f/{slug}/family/access/{public_uuid}", response_class=HTMLResponse)
async def family_access_login_page(
    request: Request,
    public_uuid: str,
    next: str | None = Query(None),
    err: str | None = Query(None),
    db: Session = Depends(get_db),
):
    person = find_person_by_public_uuid(db, public_uuid)
    if not person or not _is_live_visible_person(person):
        raise HTTPException(status_code=404, detail="Not found")
    slug = request.path_params.get("slug") or default_family_slug()
    if getattr(person, "avatar_url", None):
        person.avatar_url = normalize_media_url(person.avatar_url, slug)
    default_next = "/family/welcome"
    next_url = _safe_internal_next_url(next, default_next)
    viewer = resolve_viewer(request, db)
    if (
        viewer is not None
        and viewer.person_id == person.person_id
        and person_family_access_permitted(person)
    ):
        return RedirectResponse(url=next_url, status_code=303)
    error_msg = None
    if err == "rate_limited":
        error_msg = "Слишком много попыток, подождите."
    elif err == "invalid_code":
        error_msg = "Неверный или устаревший код."
    elif err == "crypto":
        error_msg = "Внутренняя ошибка конфигурации доступа."
    return templates.TemplateResponse(
        "family/access_login.html",
        {
            "request": request,
            "person": person,
            "public_uuid": str(person.public_uuid),
            "next": next_url,
            "error": error_msg,
            "access_permitted": person_family_access_permitted(person),
        },
    )


@router.post("/family/access/{public_uuid}")
@router.post("/f/{slug}/family/access/{public_uuid}")
async def family_access_login_submit(
    request: Request,
    public_uuid: str,
    code: str = Form(""),
    next: str = Form(""),
    db: Session = Depends(get_db),
):
    person = find_person_by_public_uuid(db, public_uuid)
    if not person or not _is_live_visible_person(person):
        raise HTTPException(status_code=404, detail="Not found")
    if not person_family_access_permitted(person):
        return RedirectResponse(
            url=f"/family/access/{(public_uuid or '').strip()}",
            status_code=303,
        )
    client_ip = request.client.host if request.client else ""
    if not check_rate_limit(client_ip, (public_uuid or "").strip()):
        default_next = "/family/welcome"
        next_param = _safe_internal_next_url(next, default_next)
        return RedirectResponse(
            url=f"/family/access/{(public_uuid or '').strip()}?err=rate_limited&next={quote(next_param, safe='/?&=')}",
            status_code=303,
        )
    secret = decrypt_totp_secret(person.totp_secret_encrypted or "")
    if not secret:
        return RedirectResponse(
            url=f"/family/access/{(public_uuid or '').strip()}?err=crypto",
            status_code=303,
        )
    c = (code or "").strip()
    ok = False
    if c.isdigit() and len(c) == 6:
        ok = verify_totp_code(secret, c)
    if not ok:
        ok = use_one_backup_code(db, person.person_id, c)
    if not ok:
        default_next = "/family/welcome"
        next_param = _safe_internal_next_url(next, default_next)
        return RedirectResponse(
            url=f"/family/access/{(public_uuid or '').strip()}?err=invalid_code&next={quote(next_param, safe='/?&=')}",
            status_code=303,
        )
    set_totp_last_used(db, person.person_id)
    token, _ = create_family_access_session(
        db,
        person_id=person.person_id,
        client_ip=client_ip,
        user_agent=request.headers.get("user-agent"),
    )
    max_age = int(DEFAULT_SESSION_TTL.total_seconds())
    default_next = "/family/welcome"
    dest = _safe_internal_next_url(next, default_next)
    response = RedirectResponse(url=dest, status_code=303)
    set_family_access_cookies(
        response, token=token, max_age_sec=max_age, request=request
    )
    response.set_cookie(
        key=FAMILY_COOKIE_NAME,
        value=str(person.person_id),
        max_age=max_age,
        path="/",
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/family/leave-session")
@router.get("/f/{slug}/family/leave-session")
async def family_leave_session() -> RedirectResponse:
    r = RedirectResponse(FAMILY_NEED_ACCESS_PATH, status_code=303)
    r.delete_cookie(FAMILY_COOKIE_NAME, path="/")
    return r


@router.get("/family/tree", response_class=HTMLResponse, name="family_tree_page")
@router.get("/f/{slug}/family/tree", response_class=HTMLResponse, name="family_tree_page_slug")
async def family_tree_page(
    request: Request,
    root_person_id: int = Query(1, description="ID персоны для корня графа"),
    depth: int = Query(2, ge=1, le=10, description="Глубина поиска (1-10)"),
    year: int | None = Query(None, ge=1000, le=2100, description="Год для temporal-режима"),
    db: Session = Depends(get_db),
):
    """
    Страница визуализации семейного графа.
    
    :param root_person_id: ID персоны для корня графа
    :param depth: Глубина BFS (кол-во уровней Person <-> Union переходов)
    """
    redirect = _require_family_session(request, db)
    if redirect:
        return redirect

    logger.info(f"Family tree page requested: root={root_person_id}, depth={depth}, year={year}")
    return templates.TemplateResponse(
        "family_tree.html",
        {
            "request": request,
            "root_person_id": root_person_id,
            "depth": depth,
            "year": year,
        },
    )


@router.get("/family/tree/json", response_model=FamilyGraph)
@router.get("/f/{slug}/family/tree/json", response_model=FamilyGraph)
async def family_tree_json(
    root_person_id: int = Query(..., description="ID персоны для корня графа"),
    depth: int = Query(2, ge=1, le=10, description="Глубина поиска (1-10)"),
    year: int | None = Query(None, ge=1000, le=2100, description="Год для temporal-режима"),
    session: Session = Depends(get_db),
):
    """
    API эндпоинт для получения семейного графа в формате JSON.
    
    Возвращает структуру:
    {
      "nodes": [...],
      "edges": [...]
    }
    
    Узлы могут быть типов "person" или "union".
    Рёбра типов "partner" (Person <-> Union) или "child" (Union <-> Person).
    
    :param root_person_id: ID персоны для корня графа
    :param depth: Глубина BFS (1-10)
    :param session: Database session
    :return: FamilyGraph с nodes и edges
    """
    logger.info(f"Family tree JSON API: root={root_person_id}, depth={depth}, year={year}")
    
    try:
        graph = build_family_graph(
            root_person_id=root_person_id,
            depth=depth,
            session=session,
            year=year,
        )
        logger.info(
            f"Graph built successfully: {len(graph.nodes)} nodes, {len(graph.edges)} edges"
        )
        return graph
    except ValueError as e:
        logger.error(f"Graph building error: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error building graph: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/family/person/{person_id}", response_class=HTMLResponse)
@router.get("/f/{slug}/family/person/{person_id}", response_class=HTMLResponse)
async def family_person(
    request: Request,
    person_id: int,
    session: Session = Depends(get_db),
):
    viewer = resolve_viewer(request, session)
    viewer_id = viewer.person_id if viewer else None
    person = (
        session.query(Person)
        .filter(
            Person.person_id == person_id,
            _is_live_visible_person(Person),
        )
        .first()
    )
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    person_i18n = (
        session.query(PersonI18n)
        .filter(
            PersonI18n.person_id == person_id,
            PersonI18n.lang_code == "ru",
        )
        .first()
    )

    first_n = _nonempty_display_str(person_i18n.first_name if person_i18n else None)
    last_n = _nonempty_display_str(person_i18n.last_name if person_i18n else None)
    pat_n = _nonempty_display_str(person_i18n.patronymic if person_i18n else None) if person_i18n else None
    if first_n:
        name_segs: list[str] = [first_n] + ([pat_n] if pat_n else [])
        if last_n:
            name_segs.append(last_n)
        name_joined = " ".join(name_segs).strip()
    else:
        # Не выводим отчество отдельно от имени (без first_name)
        name_joined = " ".join([p for p in (last_n,) if p]).strip()
    name_clean = _nonempty_display_str(name_joined) if name_joined else None
    if not name_clean:
        name = f"Персона #{person_id}"
    else:
        name = name_clean

    memories_count = (
        session.query(Memory)
        .filter(
            Memory.author_id == person_id,
            Memory.is_archived == False,
            Memory.transcription_status == "published",
        )
        .count()
    )
    quotes_count = session.query(Quote).filter(Quote.author_id == person_id).count()

    hero_subtitle = _nonempty_display_str(_family_hero_subtitle_one_line(person, person_i18n))

    profile_is_living = (getattr(person, "is_alive", 0) or 0) == 1
    photo_possessive_name = None if profile_is_living else _ru_first_name_genitive_for_photo(first_n)

    tokens = _name_tokens_for_search(person_i18n)
    mention_memories: list[dict] = []
    mentioned_memories_count = 0
    if tokens:
        like_conds = []
        for tok in tokens:
            pat = f"%{tok}%"
            for col in (Memory.transcript_readable, Memory.transcript_verbatim, Memory.content_text):
                like_conds.append(col.ilike(pat))
        mention_base = (
            session.query(Memory)
            .join(Person, Memory.author_id == Person.person_id)
            .filter(
                Memory.author_id != person_id,
                Memory.author_id.isnot(None),
                Memory.is_archived == False,
                Memory.transcription_status == "published",
                _is_live_visible_person(Person),
            )
            .filter(or_(*like_conds))
        )
        mentioned_memories_count = mention_base.count()
        for m in mention_base.order_by(Memory.id.desc()):
            d = _public_memory_list_item(session, m)
            if d:
                ex0 = d.get("excerpt") or ""
                d["excerpt"] = _text_excerpt(_strip_test_title_prefix(ex0), 400)
                mention_memories.append(d)
            if len(mention_memories) >= 12:
                break

    own_memories: list[dict] = []
    for m in (
        session.query(Memory)
        .filter(
            Memory.author_id == person_id,
            Memory.is_archived == False,
            Memory.transcription_status == "published",
        )
        .order_by(Memory.id.desc())
        .limit(20)
    ):
        d = _family_own_memory_card(session, m)
        if d:
            d["can_edit"] = bool(
                viewer_id is not None
                and m.author_id is not None
                and viewer_id == m.author_id
            )
            own_memories.append(d)
        if len(own_memories) >= 8:
            break

    own_memories_by_year = _group_own_memories_by_year(own_memories)

    metric_mentions = _ru_count_phrase(
        mentioned_memories_count,
        one="упоминание",
        two_four="упоминания",
        other="упоминаний",
    )
    metric_memories = _ru_count_phrase(
        memories_count,
        one="история",
        two_four="истории",
        other="историй",
    )
    metric_quotes = _ru_count_phrase(
        quotes_count,
        one="цитата",
        two_four="цитаты",
        other="цитат",
    )

    person_timeline_href = f"/family/timeline?person_id={person_id}"
    family_timeline_href = "/family/timeline"

    slug = request.path_params.get("slug") or default_family_slug()
    if getattr(person, "avatar_url", None):
        person.avatar_url = normalize_media_url(person.avatar_url, slug)

    return templates.TemplateResponse(
        "family/profile.html",
        {
            "request": request,
            "person": person,
            "name": name,
            "memories_count": memories_count,
            "mentioned_memories_count": mentioned_memories_count,
            "quotes_count": quotes_count,
            "metric_mentions": metric_mentions,
            "metric_memories": metric_memories,
            "metric_quotes": metric_quotes,
            "message": None,
            "hero_subtitle": hero_subtitle,
            "mention_memories": mention_memories,
            "own_memories": own_memories,
            "own_memories_by_year": own_memories_by_year,
            "person_timeline_href": person_timeline_href,
            "family_timeline_href": family_timeline_href,
            "profile_is_living": profile_is_living,
            "photo_possessive_name": photo_possessive_name,
        },
    )


@router.get("/family/timeline", response_class=HTMLResponse)
@router.get("/f/{slug}/family/timeline", response_class=HTMLResponse)
async def family_timeline(
    request: Request,
    person_id: int | None = Query(None, description="Фильтр timeline по персоне"),
    union_id: int | None = Query(None, description="Фильтр timeline по союзу"),
    db: Session = Depends(get_db),
):
    redirect = _require_family_session(request, db)
    if redirect:
        return redirect

    from app.models import Union, UnionChild
    slug = request.path_params.get("slug") or default_family_slug()

    items = []
    visible_people = (
        db.query(Person)
        .filter(_is_live_visible_person(Person))
        .order_by(Person.person_id)
        .all()
    )
    visible_person_ids = {person.person_id for person in visible_people}

    related_union = None
    related_person_ids: set[int] = set()
    if union_id is not None:
        related_union = db.query(Union).filter(Union.id == union_id).first()
        if related_union:
            if related_union.partner1_id in visible_person_ids:
                related_person_ids.add(related_union.partner1_id)
            if related_union.partner2_id in visible_person_ids:
                related_person_ids.add(related_union.partner2_id)
            child_ids = [
                row.child_id
                for row in db.query(UnionChild).filter(UnionChild.union_id == related_union.id).all()
                if row.child_id is not None and row.child_id in visible_person_ids
            ]
            related_person_ids.update(child_ids)

    for person in visible_people:
        if person_id is not None and person.person_id != person_id:
            continue
        if union_id is not None and person.person_id not in related_person_ids:
            continue
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

        if person.birth_date:
            items.append(
                {
                    "date": person.birth_date,
                    "date_display": _family_timeline_date_display(person.birth_date),
                    "title": f"Рождение: {name}",
                    "text": "",
                    "person_id": person.person_id,
                    "avatar_url": normalize_media_url(person.avatar_url, slug),
                    "source": "people",
                    "type": "birth",
                }
            )

        if person.death_date:
            items.append(
                {
                    "date": person.death_date,
                    "date_display": _family_timeline_date_display(person.death_date),
                    "title": f"Смерть: {name}",
                    "text": "",
                    "person_id": person.person_id,
                    "avatar_url": normalize_media_url(person.avatar_url, slug),
                    "source": "people",
                    "type": "death",
                }
            )

    for union in db.query(Union).all():
        if union.partner1_id is not None and union.partner1_id not in visible_person_ids:
            continue
        if union.partner2_id is not None and union.partner2_id not in visible_person_ids:
            continue
        if person_id is not None and person_id not in (union.partner1_id, union.partner2_id):
            continue
        if union_id is not None and union.id != union_id:
            continue

        if union.start_date:
            p1_name = "Персона"
            p2_name = "Персона"

            if union.partner1_id:
                i1 = db.query(PersonI18n).filter(
                    PersonI18n.person_id == union.partner1_id,
                    PersonI18n.lang_code == "ru",
                ).first()
                if i1:
                    p1_name = " ".join([p for p in (i1.first_name, i1.last_name) if p]).strip()

            if union.partner2_id:
                i2 = db.query(PersonI18n).filter(
                    PersonI18n.person_id == union.partner2_id,
                    PersonI18n.lang_code == "ru",
                ).first()
                if i2:
                    p2_name = " ".join([p for p in (i2.first_name, i2.last_name) if p]).strip()

            items.append(
                {
                    "date": union.start_date,
                    "date_display": _family_timeline_date_display(union.start_date),
                    "title": f"Союз: {p1_name} + {p2_name}",
                    "text": "",
                    "person_id": union.partner1_id,
                    "avatar_url": None,
                    "source": "events",
                    "type": "wedding",
                }
            )

        if union.end_date:
            items.append(
                {
                    "date": union.end_date,
                    "date_display": _family_timeline_date_display(union.end_date),
                    "title": f"Окончание союза: {p1_name} + {p2_name}",
                    "text": "",
                    "person_id": union.partner1_id,
                    "avatar_url": None,
                    "source": "events",
                    "type": "event",
                }
            )

    text_filter = or_(
        and_(Memory.transcript_readable.isnot(None), Memory.transcript_readable != ""),
        and_(Memory.transcript_verbatim.isnot(None), Memory.transcript_verbatim != ""),
        and_(Memory.content_text.isnot(None), Memory.content_text != ""),
    )

    memories_query = (
        db.query(Memory)
        .join(Person, Person.person_id == Memory.author_id)
        .filter(
            Memory.author_id.isnot(None),
            text_filter,
            Memory.is_archived == False,
            Memory.transcription_status == "published",
            _is_live_visible_person(Person),
        )
    )

    if person_id is not None:
        memories_query = memories_query.filter(Memory.author_id == person_id)
    if union_id is not None:
        if related_person_ids:
            memories_query = memories_query.filter(Memory.author_id.in_(list(related_person_ids)))
        else:
            memories_query = memories_query.filter(false())

    memories = memories_query.all()
    timeline_events: list[TimelineEventView] = []

    for memory in memories:
        author_i18n = (
            db.query(PersonI18n)
            .filter(
                PersonI18n.person_id == memory.author_id,
                PersonI18n.lang_code == "ru",
            )
            .first()
        )
        author_name = " ".join(
            [p for p in (author_i18n.first_name if author_i18n else None, author_i18n.last_name if author_i18n else None) if p]
        ).strip() if author_i18n else None
        if not author_name:
            author_name = f"Персона #{memory.author_id}"

        text = (
            memory.transcript_readable
            or memory.transcript_verbatim
            or memory.content_text
            or ""
        )

        if _looks_like_technical_blob(text):
            continue

        ev = memory_to_timeline_event_view(memory, author_display_name=author_name)
        if ev is not None:
            timeline_events.append(ev)

        items.append(
            {
                "date": memory.created_at or "",
                "date_display": _family_timeline_date_display(memory.created_at),
                "title": author_name,
                "text": text[:280],
                "memory_id": memory.id,
                "person_id": memory.author_id,
                "avatar_url": normalize_media_url(
                    memory.author.avatar_url if memory.author else None,
                    request.path_params.get("slug") or default_family_slug(),
                ),
                "source": "people",
                "type": "memory_recording",
                "has_audio": _memory_has_audio(memory),
            }
        )

    items.sort(key=lambda x: x["date"], reverse=True)
    timeline_events.sort(key=lambda e: e.event_date, reverse=True)
    # Явно сериализуем в dict, чтобы Jinja2 всегда видела author_display_name и остальные поля
    # (датакласс в шаблоне в части окружений отдаёт пустое имя; см. TW-2026-04-26-B3-HOTFIX-AUTHOR-DATA-FLOW)
    timeline_events_template = [asdict(ev) for ev in timeline_events]

    return templates.TemplateResponse(
        "family/timeline.html",
        {
            "request": request,
            "items": items,
            "timeline_events": timeline_events_template,
        },
    )


@router.get("/family/welcome", response_class=HTMLResponse)
@router.get("/f/{slug}/family/welcome", response_class=HTMLResponse)
async def family_welcome(request: Request, person_id: int = Query(None), db: Session = Depends(get_db)):
    redirect = _require_family_session(request, db)
    if redirect:
        return redirect

    cookie_person_id = _get_family_member_id(request)
    if cookie_person_id is not None:
        person_id = cookie_person_id

    text_filter = or_(
        and_(Memory.transcript_readable.isnot(None), Memory.transcript_readable != ""),
        and_(Memory.transcript_verbatim.isnot(None), Memory.transcript_verbatim != ""),
        and_(Memory.content_text.isnot(None), Memory.content_text != ""),
    )

    memory = (
        db.query(Memory)
        .join(Person, Person.person_id == Memory.author_id)
        .filter(
            Memory.author_id.isnot(None),
            Memory.is_archived == False,
            Memory.transcription_status == "published",
            _is_live_visible_person(Person),
            text_filter,
        )
        .order_by(func.random())
        .first()
    )

    memory_text = ""
    golden_memory_date_display = ""
    author_name = ""
    slug = request.path_params.get("slug") or default_family_slug()
    author_avatar = ""
    memory_id = None
    golden_memory = None

    if memory:
        memory_id = memory.id
        golden_memory_date_display = _family_timeline_date_display(memory.created_at)
        memory_text = (
            memory.transcript_readable
            or memory.transcript_verbatim
            or memory.content_text
            or ""
        ).strip()

        if memory.author_id:
            i18n = (
                db.query(PersonI18n)
                .filter(
                    PersonI18n.person_id == memory.author_id,
                    PersonI18n.lang_code == "ru",
                )
                .first()
            )
            if i18n:
                author_name = " ".join([p for p in (i18n.first_name, i18n.last_name) if p]).strip()

            person = db.query(Person).filter(Person.person_id == memory.author_id).first()
            if person and person.avatar_url:
                author_avatar = normalize_media_url(person.avatar_url, slug) or ""

        golden_memory = {
            "id": memory_id,
            "author_display_name": author_name,
        }

    if not memory_text:
        memory_text = "Добро пожаловать в TimeWoven! Напишите боту первую историю."

    memory_audio_url = ""
    if memory and (memory.audio_url or "").strip():
        memory_audio_url = normalize_media_url((memory.audio_url or "").strip(), slug) or ""

    return templates.TemplateResponse(
        "family/welcome.html",
        {
            "request": request,
            "person_id": person_id,
            "memory_id": memory_id,
            "memory_text": memory_text,
            "golden_memory": golden_memory,
            "golden_memory_date_display": golden_memory_date_display,
            "author_avatar": author_avatar,
            "memory_audio_url": memory_audio_url,
        },
    )


@router.get("/who-am-i", response_class=HTMLResponse)
@router.get("/f/{slug}/who-am-i", response_class=HTMLResponse)
async def who_am_i(request: Request, next: str = "/family/welcome", db: Session = Depends(get_db)):
    r = _redirect_if_whoami_disabled(next_url=next)
    if r is not None:
        return r

    if _get_family_member_id(request) is not None:
        return RedirectResponse(url="/family/welcome", status_code=303)

    people = []
    for person in (
        db.query(Person)
        .filter(
            Person.is_alive == 1,
            _is_live_visible_person(Person),
        )
        .order_by(Person.person_id)
        .all()
    ):
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

        people.append({"person_id": person.person_id, "name": name})

    return templates.TemplateResponse(
        "family/who_am_i.html",
        {"request": request, "next": next, "people": people},
    )


@router.post("/who-am-i")
@router.post("/f/{slug}/who-am-i")
async def who_am_i_submit(
    person_id: int = Form(...),
    next: str = Form("/family/welcome"),
    db: Session = Depends(get_db),
):
    r = _redirect_if_whoami_disabled(next_url=None)
    if r is not None:
        return r

    person = (
        db.query(Person)
        .filter(
            Person.person_id == person_id,
            Person.is_alive == 1,
            _is_live_visible_person(Person),
        )
        .first()
    )
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    encoded_next = quote(next or "/family/welcome", safe="/")
    return RedirectResponse(
        url=f"/who-am-i/pin?person_id={person_id}&next={encoded_next}",
        status_code=303,
    )


@router.get("/who-am-i/pin", response_class=HTMLResponse)
@router.get("/f/{slug}/who-am-i/pin", response_class=HTMLResponse)
async def who_am_i_pin(
    request: Request,
    person_id: int = Query(...),
    next: str = Query("/family/welcome"),
    db: Session = Depends(get_db),
):
    r = _redirect_if_whoami_disabled(next_url=next)
    if r is not None:
        return r

    if _get_family_member_id(request) is not None:
        return RedirectResponse(url="/family/welcome", status_code=303)

    person = (
        db.query(Person)
        .filter(
            Person.person_id == person_id,
            Person.is_alive == 1,
            _is_live_visible_person(Person),
        )
        .first()
    )
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    i18n = (
        db.query(PersonI18n)
        .filter(
            PersonI18n.person_id == person_id,
            PersonI18n.lang_code == "ru",
        )
        .first()
    )
    name = " ".join(
        [p for p in (i18n.first_name if i18n else None, i18n.last_name if i18n else None) if p]
    ).strip()
    if not name:
        name = f"Персона #{person_id}"

    slug = request.path_params.get("slug") or default_family_slug()
    return templates.TemplateResponse(
        "family/pin_form.html",
        {
            "request": request,
            "person_id": person_id,
            "name": name,
            "avatar_url": normalize_media_url(person.avatar_url, slug),
            "next": next,
            "error": None,
        },
    )


@router.post("/who-am-i/pin")
@router.post("/f/{slug}/who-am-i/pin")
async def who_am_i_pin_submit(
    person_id: int = Form(...),
    pin: str = Form(...),
    next: str = Form("/family/welcome"),
    db: Session = Depends(get_db),
):
    r = _redirect_if_whoami_disabled(next_url=None)
    if r is not None:
        return r

    decoded_next = unquote(next or "")
    person = (
        db.query(Person)
        .filter(
            Person.person_id == person_id,
            Person.is_alive == 1,
            _is_live_visible_person(Person),
        )
        .first()
    )
    if not person or not person.pin or person.pin != pin:
        encoded_next = quote(decoded_next or "/family/welcome", safe="/")
        return RedirectResponse(
            url=f"/who-am-i/pin?person_id={person_id}&next={encoded_next}&error=invalid_pin",
            status_code=303,
        )

    # Защита от open redirect: принимаем только внутренние пути
    safe_next = decoded_next if (decoded_next and decoded_next.startswith("/") and not decoded_next.startswith("//")) else "/family/welcome"
    response = RedirectResponse(url=safe_next, status_code=303)
    response.set_cookie(
        key=FAMILY_COOKIE_NAME,
        value=str(person_id),
        max_age=FAMILY_SESSION_MAX_AGE,
        path="/",
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/family/reply/{memory_id}", response_class=HTMLResponse)
@router.get("/f/{slug}/family/reply/{memory_id}", response_class=HTMLResponse)
async def family_reply(
    request: Request,
    memory_id: int,
    person_id: int = Query(None),
    saved: bool = Query(False),
    db: Session = Depends(get_db),
):
    memory = db.query(Memory).filter(Memory.id == memory_id).first()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    author_name = "Неизвестный"
    if memory.author_id:
        i18n = db.query(PersonI18n).filter(
            PersonI18n.person_id == memory.author_id,
            PersonI18n.lang_code == "ru",
        ).first()
        if i18n:
            author_name = " ".join([p for p in (i18n.first_name, i18n.last_name) if p]).strip()

    memory_text = (
        memory.transcript_readable
        or memory.transcript_verbatim
        or memory.content_text
        or ""
    )

    responses = []
    slug = request.path_params.get("slug") or default_family_slug()
    quotes = (
        db.query(Quote)
        .filter(Quote.source_memory_id == memory_id)
        .order_by(Quote.created_at.desc())
        .all()
    )
    
    for quote in quotes:
        resp_author_name = "Неизвестный"
        resp_avatar_url = None
        if quote.author_id:
            author = db.query(Person).filter(Person.person_id == quote.author_id).first()
            if author:
                resp_avatar_url = normalize_media_url(author.avatar_url, slug)
                i18n = db.query(PersonI18n).filter(
                    PersonI18n.person_id == quote.author_id,
                    PersonI18n.lang_code == "ru",
                ).first()
                if i18n:
                    resp_author_name = " ".join([p for p in (i18n.first_name, i18n.last_name) if p]).strip()
        
        responses.append({
            "text": quote.content_text,
            "author_name": resp_author_name,
            "author_id": quote.author_id,
            "avatar_url": resp_avatar_url,
            "created_at": quote.created_at,
        })
    
    message = "Ответ сохранён" if saved else None

    original_audio_url = normalize_media_url((memory.audio_url or "").strip() if memory else "", slug) or ""

    return templates.TemplateResponse(
        "family/reply.html",
        {
            "request": request,
            "memory": memory,
            "memory_id": memory_id,
            "author_name": author_name,
            "memory_text": memory_text,
            "responses": responses,
            "message": message,
            "person_id": person_id or 1,
            "original_audio_url": original_audio_url,
        },
    )


@router.post("/family/reply/{memory_id}", response_class=HTMLResponse)
@router.post("/f/{slug}/family/reply/{memory_id}", response_class=HTMLResponse)
async def family_reply_submit(
    memory_id: int,
    text: str = Form(...),
    person_id: int = Form(None),
    db: Session = Depends(get_db),
):
    memory = db.query(Memory).filter(Memory.id == memory_id).first()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    if text and text.strip() and person_id:
        from datetime import datetime
        quote = Quote(
            author_id=person_id,
            content_text=text,
            source_memory_id=memory_id,
            created_at=datetime.now().isoformat(),
        )
        db.add(quote)
        db.commit()

    # Never put None in the redirect URL — FastAPI would 422 on the receiving GET.
    if person_id is not None:
        redirect_url = f"/family/reply/{memory_id}?person_id={person_id}&saved=1"
    else:
        redirect_url = f"/family/reply/{memory_id}?saved=1"
    return RedirectResponse(url=redirect_url, status_code=303)


@router.get(
    "/family/memory/new",
    response_class=HTMLResponse,
    name="family_memory_new",
)
@router.get(
    "/f/{slug}/family/memory/new",
    response_class=HTMLResponse,
    name="family_memory_new_slug",
)
async def family_memory_new_get(
    request: Request,
    person_id: int = Query(...),
    err: str | None = Query(None),
    db: Session = Depends(get_db),
):
    red = _require_family_session(request, db)
    if red:
        return red
    viewer = resolve_viewer(request, db)
    if not viewer or viewer.person_id != person_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    empty_hint = err == "empty"
    return templates.TemplateResponse(
        "family/memory_new.html",
        {
            "request": request,
            "person_id": person_id,
            "empty_hint": empty_hint,
        },
    )


@router.post("/family/memory/new", response_class=HTMLResponse)
@router.post("/f/{slug}/family/memory/new", response_class=HTMLResponse)
async def family_memory_new_post(
    request: Request,
    return_person_id: int = Form(...),
    transcript_readable: str = Form(""),
    essence_text: str = Form(""),
    db: Session = Depends(get_db),
):
    red = _require_family_session(request, db)
    if red:
        return red
    viewer = resolve_viewer(request, db)
    if not viewer or viewer.person_id != return_person_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    body = (transcript_readable or "").strip()
    if not body:
        return RedirectResponse(
            url=f"/family/memory/new?person_id={return_person_id}&err=empty",
            status_code=303,
        )
    ess = (essence_text or "").strip()
    memory = Memory(
        author_id=viewer.person_id,
        created_by=viewer.person_id,
        content_text=body,
        transcript_verbatim=body,
        transcript_readable=body,
        essence_text=ess or None,
        source_type="family_web",
        transcription_status="published",
        is_archived=False,
        created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    db.add(memory)
    db.commit()
    return RedirectResponse(url=f"/family/person/{return_person_id}", status_code=303)


@router.get("/family/memory/{memory_id}/edit", response_class=HTMLResponse)
@router.get("/f/{slug}/family/memory/{memory_id}/edit", response_class=HTMLResponse)
async def family_memory_edit_get(
    request: Request,
    memory_id: int,
    person_id: int | None = Query(
        None,
        description="person_id карточки для ссылки «назад» и редиректа после сохранения",
    ),
    db: Session = Depends(get_db),
):
    red = _require_family_session(request, db)
    if red:
        return red
    viewer = resolve_viewer(request, db)
    if not viewer:
        return red
    memory = db.query(Memory).filter(Memory.id == memory_id).first()
    if not memory or memory.is_archived:
        raise HTTPException(status_code=404, detail="Memory not found")
    if memory.author_id is None or viewer.person_id != memory.author_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return_pid = person_id if person_id is not None else (memory.author_id or 0)
    return templates.TemplateResponse(
        "family/memory_edit.html",
        {
            "request": request,
            "memory": memory,
            "memory_id": memory_id,
            "person_id": return_pid,
            "transcript_readable": memory.transcript_readable or "",
            "transcript_verbatim": memory.transcript_verbatim or "",
            "essence_text": memory.essence_text or "",
        },
    )


@router.post("/family/memory/{memory_id}/edit", response_class=HTMLResponse)
@router.post("/f/{slug}/family/memory/{memory_id}/edit", response_class=HTMLResponse)
async def family_memory_edit_post(
    request: Request,
    memory_id: int,
    return_person_id: int = Form(...),
    transcript_readable: str = Form(""),
    essence_text: str = Form(""),
    db: Session = Depends(get_db),
):
    red = _require_family_session(request, db)
    if red:
        return red
    viewer = resolve_viewer(request, db)
    if not viewer:
        return red
    memory = db.query(Memory).filter(Memory.id == memory_id).first()
    if not memory or memory.is_archived:
        raise HTTPException(status_code=404, detail="Memory not found")
    if memory.author_id is None or viewer.person_id != memory.author_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    # Оригинал (transcript_verbatim) не меняется с family-редактора
    memory.transcript_readable = transcript_readable
    memory.essence_text = essence_text
    db.commit()
    return RedirectResponse(url=f"/family/person/{return_person_id}", status_code=303)


@router.post("/profile/avatar")
@router.post("/f/{slug}/profile/avatar")
async def profile_avatar_upload(
    request: Request,
    person_id: int = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    resolved_person_id = person_id
    if resolved_person_id is None:
        referer = request.headers.get("referer", "")
        referer_path = urlparse(referer).path
        if referer_path.startswith("/family/person/"):
            candidate = referer_path.rsplit("/", 1)[-1]
            if candidate.isdigit():
                resolved_person_id = int(candidate)

    if resolved_person_id is None:
        raise HTTPException(status_code=400, detail="Missing person_id")

    person = db.query(Person).filter(Person.person_id == resolved_person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        suffix = ".jpg"

    slug = default_family_slug()
    avatar_dir = Path(family_data_path_for_slug(slug)) / "media" / "avatars" / "current"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    filename = f"profile_{resolved_person_id}_{uuid4().hex}{suffix}"
    target = avatar_dir / filename

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    target.write_bytes(content)
    person.avatar_url = f"/media/{slug}/avatars/current/{filename}"
    db.commit()

    return RedirectResponse(url=f"/family/person/{resolved_person_id}", status_code=303)

