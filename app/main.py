import random
import hashlib
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request, Depends, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from .db import get_db
from .models import Quote, PersonI18n, Person, Memory, AvatarHistory, Event

# Admin credentials (в продакшене вынести в .env)
ADMIN_USERS = {
    "admin": hashlib.sha256("timewoven2026".encode()).hexdigest(),
}

def is_admin(request: Request) -> bool:
    return request.cookies.get("is_admin") == "1"

def require_admin(request: Request):
    if not is_admin(request):
        return RedirectResponse(url=f"/admin/login?next={request.url.path}", status_code=303)
    return None


app = FastAPI(title="TimeWoven")

templates = Jinja2Templates(directory="app/templates")

try:
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
except RuntimeError:
    pass


def build_person_name(person_i18n):
    if not person_i18n:
        return "Неизвестный участник"
    parts = [person_i18n.first_name, person_i18n.last_name]
    name = " ".join([p for p in parts if p]).strip()
    return name or "Неизвестный участник"


def pick_memory_text(memory):
    candidates = [
        getattr(memory, "transcript_readable", None),
        getattr(memory, "transcriptreadable", None),
        getattr(memory, "content_text", None),
        getattr(memory, "contenttext", None),
        getattr(memory, "transcript_verbatim", None),
        getattr(memory, "transcriptverbatim", None),
    ]
    for value in candidates:
        if value and str(value).strip():
            return " ".join(str(value).strip().split())
    return "Текст воспоминания пока отсутствует."


def format_created_at(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M")

    raw = str(value).strip()
    if not raw:
        return None

    raw = raw.replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d %H%M%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            if fmt == "%Y-%m-%d":
                return dt.strftime("%d.%m.%Y")
            return dt.strftime("%d.%m.%Y %H:%M")
        except ValueError:
            continue

    return raw


def collect_replies(db: Session, source_memory_id: int):
    replies = (
        db.query(Memory)
        .filter(Memory.event_id == source_memory_id)
        .order_by(Memory.id.desc())
        .all()
    )

    results = []
    for reply in replies:
        if reply.id == source_memory_id:
            continue

        reply_author = None
        reply_author_i18n = None

        if reply.author_id:
            reply_author = db.query(Person).filter(Person.person_id == reply.author_id).first()
            reply_author_i18n = (
                db.query(PersonI18n)
                .filter(
                    PersonI18n.person_id == reply.author_id,
                    PersonI18n.lang_code == "ru"
                )
                .first()
            )

        results.append(
            {
                "id": reply.id,
                "text": pick_memory_text(reply),
                "author_name": build_person_name(reply_author_i18n),
                "author_id": reply.author_id,
                "avatar_url": reply_author.avatar_url if reply_author and reply_author.avatar_url else None,
                "created_at": format_created_at(reply.created_at),
            }
        )
    return results

@app.get("/", response_class=HTMLResponse)
async def home_presence(request: Request, db: Session = Depends(get_db)):
    all_quotes = db.query(Quote).all()

    if not all_quotes:
        return templates.TemplateResponse(
            request,
            "family/home.html",
            {"quote": None, "lang": "ru"}
        )

    selected_quote = random.choice(all_quotes)

    author_info = db.query(PersonI18n).filter(
        PersonI18n.person_id == selected_quote.author_id,
        PersonI18n.lang_code == "ru"
    ).first()

    if author_info:
        parts = [author_info.first_name, author_info.last_name]
        author_name = " ".join([p for p in parts if p])
    else:
        author_name = "Неизвестный предок"

    author_avatar = None
    if selected_quote.author and getattr(selected_quote.author, "avatar_url", None):
        author_avatar = selected_quote.author.avatar_url

    raw_audio = selected_quote.memory.audio_url if selected_quote.memory else None
    audio_url = None
    if raw_audio:
        filename = raw_audio.split("/")[-1].strip()
        audio_url = f"/static/processed/{filename}"

    quote_data = {
        "text": selected_quote.content_text,
        "author_name": author_name,
        "author_avatar": author_avatar,
        "audio_url": audio_url,
        "memory_id": selected_quote.source_memory_id,
        "author_id": selected_quote.author_id,
    }

    return templates.TemplateResponse(
        request,
        "family/home.html",
        {"quote": quote_data, "lang": "ru"}
    )


@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login(request: Request, next: str = "/admin/people"):
    if is_admin(request):
        return RedirectResponse(url=next, status_code=303)
    return templates.TemplateResponse(
        request,
        "family/admin_login.html",
        {"next": next, "error": None},
    )


@app.post("/admin/login", response_class=HTMLResponse)
async def admin_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/admin/people"),
):
    import hashlib
    hashed = hashlib.sha256(password.encode()).hexdigest()
    if ADMIN_USERS.get(username) == hashed:
        response = RedirectResponse(url=next, status_code=303)
        response.set_cookie("is_admin", "1", max_age=60 * 60 * 8)  # 8 часов
        return response
    return templates.TemplateResponse(
        request,
        "family/admin_login.html",
        {"next": next, "error": "Неверный логин или пароль."},
    )


@app.get("/admin/logout")
async def admin_logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("is_admin")
    return response


@app.get("/admin/avatars", response_class=HTMLResponse)
async def avatars_form(request: Request, db: Session = Depends(get_db)):
    guard = require_admin(request)
    if guard:
        return guard
    people = (
        db.query(Person, PersonI18n)
        .join(PersonI18n, Person.person_id == PersonI18n.person_id)
        .filter(PersonI18n.lang_code == "ru")
        .order_by(Person.person_id)
        .all()
    )

    data = []
    for person, p18n in people:
        name_parts = [p18n.first_name, p18n.last_name]
        display_name = " ".join([p for p in name_parts if p]) or f"Person {person.person_id}"
        data.append(
            {
                "id": person.person_id,
                "name": display_name,
                "avatar_url": person.avatar_url,
            }
        )

    return templates.TemplateResponse(
        request,
        "family/avatars_form.html",
        {"people": data}
    )


@app.post("/admin/avatars")
async def upload_avatar(
    person_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    avatars_dir = Path("app/static/avatars")
    avatars_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename).suffix.lower() or ".jpg"
    filename = f"person_{person_id}{suffix}"
    filepath = avatars_dir / filename

    contents = await file.read()
    filepath.write_bytes(contents)

    person = db.query(Person).filter(Person.person_id == person_id).first()
    if person:
        person.avatar_url = f"/static/avatars/{filename}"
        db.add(person)
        db.commit()

    return RedirectResponse(url="/admin/avatars", status_code=303)


@app.get("/who-am-i", response_class=HTMLResponse)
async def who_am_i(request: Request, db: Session = Depends(get_db), next: str = "/"):
    people_rows = (
        db.query(Person, PersonI18n)
        .join(PersonI18n, Person.person_id == PersonI18n.person_id)
        .filter(PersonI18n.lang_code == "ru")
        .order_by(Person.person_id)
        .all()
    )

    people = []
    for person, p18n in people_rows:
        parts = [p18n.first_name, p18n.last_name]
        name = " ".join([p for p in parts if p]) or f"Person {person.person_id}"
        people.append({"id": person.person_id, "name": name})

    return templates.TemplateResponse(
        request,
        "family/who_am_i.html",
        {"people": people, "next": next},
    )


@app.post("/who-am-i")
async def who_am_i_submit(
    person_id: int = Form(...),
    next: str = Form("/"),
):
    return RedirectResponse(url=f"/who-am-i/pin?person_id={person_id}&next={next}", status_code=303)


@app.get("/who-am-i/pin", response_class=HTMLResponse)
async def pin_form(request: Request, person_id: int, next: str = "/", db: Session = Depends(get_db)):
    person = db.query(Person).filter(Person.person_id == person_id).first()
    i18n = db.query(PersonI18n).filter(PersonI18n.person_id == person_id, PersonI18n.lang_code == "ru").first()
    name = build_person_name(i18n)
    return templates.TemplateResponse(
        request,
        "family/pin_form.html",
        {
            "person_id": person_id,
            "name": name,
            "avatar_url": person.avatar_url if person else None,
            "next": next,
            "error": None,
        },
    )


@app.post("/who-am-i/pin", response_class=HTMLResponse)
async def pin_submit(
    request: Request,
    person_id: int = Form(...),
    pin: str = Form(...),
    next: str = Form("/"),
    db: Session = Depends(get_db),
):
    person = db.query(Person).filter(Person.person_id == person_id).first()
    i18n = db.query(PersonI18n).filter(PersonI18n.person_id == person_id, PersonI18n.lang_code == "ru").first()
    name = build_person_name(i18n)

    if not person or person.pin != pin.strip():
        return templates.TemplateResponse(
            request,
            "family/pin_form.html",
            {
                "person_id": person_id,
                "name": name,
                "avatar_url": person.avatar_url if person else None,
                "next": next,
                "error": "Неверный PIN. Попробуйте ещё раз.",
            },
        )

    response = RedirectResponse(url="/profile" if next == "/" else next, status_code=303)
    response.set_cookie("current_person_id", str(person_id), max_age=60 * 60 * 24 * 365)
    return response


@app.get("/family/reply/{memory_id}", response_class=HTMLResponse)
async def reply_form(memory_id: int, request: Request, db: Session = Depends(get_db)):
    memory = db.query(Memory).filter(Memory.id == memory_id).first()

    if not memory:
        return templates.TemplateResponse(
            request,
            "family/reply.html",
            {
                "memory": None,
                "author_name": "Предок",
                "memory_text": None,
                "message": "Исходное воспоминание не найдено.",
                "responses": [],
            },
        )

    author_i18n = (
        db.query(PersonI18n)
        .filter(
            PersonI18n.person_id == memory.author_id,
            PersonI18n.lang_code == "ru"
        )
        .first()
    )

    if author_i18n:
        parts = [author_i18n.first_name, author_i18n.last_name]
        author_name = " ".join([p for p in parts if p]) or "Предок"
    else:
        author_name = "Предок"

    responses = collect_replies(db, memory_id)

    return templates.TemplateResponse(
        request,
        "family/reply.html",
        {
            "memory": memory,
            "memory_text": pick_memory_text(memory),
            "author_name": author_name,
            "message": None,
            "responses": responses,
        },
    )


@app.post("/family/reply/{memory_id}", response_class=HTMLResponse)
async def reply_submit(
    memory_id: int,
    request: Request,
    text: str = Form(...),
    db: Session = Depends(get_db),
):
    current_person_id = request.cookies.get("current_person_id")
    try:
        current_author_id = int(current_person_id) if current_person_id else None
    except ValueError:
        current_author_id = None

    memory = db.query(Memory).filter(Memory.id == memory_id).first()

    if not memory:
        return templates.TemplateResponse(
            request,
            "family/reply.html",
            {
                "memory": None,
                "author_name": "Предок",
                "memory_text": None,
                "message": "Исходное воспоминание не найдено.",
                "responses": [],
            },
        )

    reply = Memory(
        author_id=current_author_id,
        event_id=memory_id,
        parent_memory_id=memory.id,
        content_text=text,
        audio_url=None,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )

    db.add(reply)
    db.commit()
    db.refresh(reply)

    author_i18n = (
        db.query(PersonI18n)
        .filter(
            PersonI18n.person_id == memory.author_id,
            PersonI18n.lang_code == "ru"
        )
        .first()
    )

    if author_i18n:
        parts = [author_i18n.first_name, author_i18n.last_name]
        author_name = " ".join([p for p in parts if p]) or "Предок"
    else:
        author_name = "Предок"

    return RedirectResponse(
        url=f"/family/reply/{memory_id}/sent?author={author_name}",
        status_code=303,
    )


@app.get("/family/reply/{memory_id}/sent", response_class=HTMLResponse)
async def reply_sent(memory_id: int, request: Request, author: str = "", db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request,
        "family/reply_sent.html",
        {
            "memory_id": memory_id,
            "author_name": author,
        },
    )


@app.get("/admin/people", response_class=HTMLResponse)
async def admin_people(request: Request, db: Session = Depends(get_db)):
    guard = require_admin(request)
    if guard:
        return guard
    people = db.query(Person).order_by(Person.person_id).all()

    rows = []
    for p in people:
        i18n = (
            db.query(PersonI18n)
            .filter(PersonI18n.person_id == p.person_id, PersonI18n.lang_code == "ru")
            .first()
        )
        name = " ".join(filter(None, [
            getattr(i18n, "first_name", None),
            getattr(i18n, "last_name", None),
            getattr(i18n, "patronymic", None),
        ])) or "—"

        memories_count = db.query(Memory).filter(Memory.author_id == p.person_id).count()
        quotes_count = db.query(Quote).filter(Quote.author_id == p.person_id).count()

        rows.append({
            "person_id": p.person_id,
            "name": name,
            "role": p.role or "—",
            "phone": p.phone or "—",
            "preferred_ch": p.preferred_ch or "—",
            "avatar_url": p.avatar_url,
            "is_alive": p.is_alive,
            "memories_count": memories_count,
            "quotes_count": quotes_count,
        })

    return templates.TemplateResponse(
        request,
        "family/admin_people.html",
        {"rows": rows},
    )


@app.get("/family/person/{person_id}", response_class=HTMLResponse)
async def person_card(person_id: int, request: Request, db: Session = Depends(get_db)):
    person = db.query(Person).filter(Person.person_id == person_id).first()
    if not person:
        return HTMLResponse("Человек не найден", status_code=404)

    i18n = (
        db.query(PersonI18n)
        .filter(PersonI18n.person_id == person_id, PersonI18n.lang_code == "ru")
        .first()
    )

    name = " ".join(filter(None, [
        getattr(i18n, "first_name", None),
        getattr(i18n, "last_name", None),
        getattr(i18n, "patronymic", None),
    ])) or "Неизвестный"

    memories = (
        db.query(Memory)
        .filter(Memory.author_id == person_id, Memory.audio_url != None)
        .order_by(Memory.id.desc())
        .all()
    )

    quotes = (
        db.query(Quote)
        .filter(Quote.author_id == person_id)
        .order_by(Quote.id.desc())
        .all()
    )

    memories_data = []
    for m in memories:
        raw_audio = m.audio_url or ""
        filename = raw_audio.split("/")[-1].strip()
        audio_url = f"/static/processed/{filename}" if filename else None
        memories_data.append({
            "id": m.id,
            "text": pick_memory_text(m),
            "audio_url": audio_url,
            "created_at": format_created_at(m.created_at),
        })

    quotes_data = [
        {
            "id": q.id,
            "text": q.content_text,
            "created_at": format_created_at(q.created_at),
        }
        for q in quotes
    ]

    def fmt_date(val):
        if not val:
            return None
        parts = val.split("-")
        if len(parts) == 3:
            return f"{parts[2]}.{parts[1]}.{parts[0]}"
        return val

    return templates.TemplateResponse(
        request,
        "family/person_card.html",
        {
            "person": person,
            "name": name,
            "biography": getattr(i18n, "biography", None),
            "birth_date": fmt_date(person.birth_date),
            "death_date": fmt_date(person.death_date),
            "memories": memories_data,
            "quotes": quotes_data,
        },
    )


@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request, db: Session = Depends(get_db)):
    current_person_id = request.cookies.get("current_person_id")
    if not current_person_id:
        return RedirectResponse(url="/who-am-i?next=/profile", status_code=303)

    person = db.query(Person).filter(Person.person_id == int(current_person_id)).first()
    if not person:
        return RedirectResponse(url="/who-am-i?next=/profile", status_code=303)

    i18n = db.query(PersonI18n).filter(
        PersonI18n.person_id == person.person_id,
        PersonI18n.lang_code == "ru"
    ).first()

    name = build_person_name(i18n)
    memories_count = db.query(Memory).filter(Memory.author_id == person.person_id).count()
    quotes_count = db.query(Quote).filter(Quote.author_id == person.person_id).count()

    return templates.TemplateResponse(
        request,
        "family/profile.html",
        {
            "person": person,
            "name": name,
            "memories_count": memories_count,
            "quotes_count": quotes_count,
            "message": request.query_params.get("message"),
        },
    )


@app.post("/profile/avatar")
async def profile_avatar_upload(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    current_person_id = request.cookies.get("current_person_id")
    if not current_person_id:
        return RedirectResponse(url="/who-am-i?next=/profile", status_code=303)

    person_id = int(current_person_id)
    avatars_dir = Path("app/static/avatars")
    avatars_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(file.filename).suffix.lower() or ".jpg"
    filename = f"person_{person_id}{suffix}"
    filepath = avatars_dir / filename

    contents = await file.read()
    filepath.write_bytes(contents)

    person = db.query(Person).filter(Person.person_id == person_id).first()
    if person:
        # Снимаем флаг is_current у предыдущих аватаров
        db.query(AvatarHistory).filter(
            AvatarHistory.person_id == person_id,
            AvatarHistory.is_current == 1
        ).update({"is_current": 0})

        # Пишем новый аватар в историю
        new_avatar = AvatarHistory(
            person_id=person_id,
            storage_path=f"/static/avatars/{filename}",
            is_current=1,
            source_type="upload",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        db.add(new_avatar)

        # Обновляем основную запись
        person.avatar_url = f"/static/avatars/{filename}"
        db.add(person)
        db.commit()

    return RedirectResponse(url="/profile?message=Фото обновлено", status_code=303)


@app.get("/family/timeline", response_class=HTMLResponse)
async def timeline(request: Request, db: Session = Depends(get_db)):
    from sqlalchemy import text

    # Три источника объединяем в один список
    items = []

    # 1. Рождения и смерти из People
    people = db.query(Person).all()
    for p in people:
        i18n = db.query(PersonI18n).filter(
            PersonI18n.person_id == p.person_id,
            PersonI18n.lang_code == "ru"
        ).first()
        name = build_person_name(i18n)

        is_female = p.gender == "F"
        born_word = "Родилась" if is_female else "Родился"
        died_word = "Ушла из жизни" if is_female else "Ушёл из жизни"

        if p.birth_date:
            items.append({
                "date": p.birth_date,
                "date_prec": p.birth_date_prec or "EXACT",
                "type": "birth",
                "title": f"{born_word} {name}",
                "person_id": p.person_id,
                "avatar_url": p.avatar_url,
                "source": "people",
            })
        if p.death_date:
            items.append({
                "date": p.death_date,
                "date_prec": p.death_date_prec or "EXACT",
                "type": "death",
                "title": f"{died_word} {name}",
                "person_id": p.person_id,
                "avatar_url": p.avatar_url,
                "source": "people",
            })

    # 2. События из Events
    type_labels = {
        "wedding": "Свадьба",
        "birth": "Рождение",
        "death": "Смерть",
        "memory_recording": "Запись посланий",
        "anniversary": "Юбилей",
        "graduation": "Окончание учёбы",
        "move": "Переезд",
    }
    # Birth events are excluded from Event table: they're already represented as personalized cards
    # from Person.birth_date (e.g. "Родился Иван"). Including them separately would duplicate timeline
    # entries since Event.author_id doesn't reflect the actual birth subject.
    events = db.query(Event).filter(Event.is_private == 0, Event.event_type != "birth", Event.event_type != "death").all()
    for e in events:
        label = type_labels.get(e.event_type, e.event_type)
        items.append({
            "date": e.date_start,
            "date_prec": e.date_start_prec or "EXACT",
            "type": e.event_type,
            "title": label,
            "person_id": e.author_id,
            "avatar_url": None,
            "source": "events",
        })

    # 3. Воспоминания с аудио
    memories = db.query(Memory).filter(
        Memory.audio_url != None,
        Memory.event_id == None,
    ).all()
    for m in memories:
        if not m.created_at:
            continue
        i18n = db.query(PersonI18n).filter(
            PersonI18n.person_id == m.author_id,
            PersonI18n.lang_code == "ru"
        ).first()
        author = db.query(Person).filter(Person.person_id == m.author_id).first()
        name = build_person_name(i18n)
        items.append({
            "date": m.created_at[:10] if m.created_at else None,
            "date_prec": "EXACT",
            "type": "memory",
            "title": f"Послание от {name}",
            "text": pick_memory_text(m),
            "person_id": m.author_id,
            "avatar_url": author.avatar_url if author else None,
            "memory_id": m.id,
            "source": "memories",
        })



    # Сортируем по дате
    def sort_key(x):
        d = x.get("date") or "0000"
        return d[:10] if d else "0000"

    items.sort(key=sort_key)

    # Форматируем даты для отображения
    for item in items:
        raw = item.get("date", "")
        prec = item.get("date_prec", "EXACT")
        if raw:
            parts = raw[:10].split("-")
            if prec == "DECADE":
                item["date_display"] = f"{parts[0][:3]}0-е"
            elif prec in ("YEARONLY", "ABOUT"):
                item["date_display"] = f"ок. {parts[0]}"
            elif len(parts) == 3:
                item["date_display"] = f"{parts[2]}.{parts[1]}.{parts[0]}"
            else:
                item["date_display"] = raw[:10]
        else:
            item["date_display"] = "Дата неизвестна"

    return templates.TemplateResponse(
        request,
        "family/timeline.html",
        {"items": items},
    )

from app.routes.family_tree import router as family_router
app.include_router(family_router)
