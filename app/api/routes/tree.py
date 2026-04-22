import logging
from pathlib import Path
from uuid import uuid4
from urllib.parse import quote, unquote, urlparse

from fastapi import APIRouter, Depends, Form, Query, HTTPException, Request, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Memory, Person, PersonI18n, Quote
from app.schemas.family_graph import FamilyGraph
from app.services.family_graph import build_family_graph

BASE_DIR = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

logger = logging.getLogger(__name__)

router = APIRouter()
FAMILY_COOKIE_NAME = "family_member_id"
FAMILY_SESSION_MAX_AGE = 60 * 60 * 24


def _get_family_member_id(request: Request) -> int | None:
    raw = request.cookies.get(FAMILY_COOKIE_NAME, "").strip()
    if not raw or not raw.isdigit():
        return None
    return int(raw)


def _require_family_session(request: Request) -> RedirectResponse | None:
    if _get_family_member_id(request) is None:
        next_url = request.url.path
        if request.url.query:
            next_url = f"{next_url}?{request.url.query}"
        encoded_next = quote(next_url, safe="/")
        return RedirectResponse(url=f"/who-am-i?next={encoded_next}", status_code=303)
    return None


@router.get("/family/tree", response_class=HTMLResponse)
async def family_tree_page(
    request: Request,
    root_person_id: int = Query(1, description="ID персоны для корня графа"),
    depth: int = Query(2, ge=1, le=6, description="Глубина поиска (1-6)"),
    year: int | None = Query(None, ge=1000, le=2100, description="Год для temporal-режима"),
):
    """
    Страница визуализации семейного графа.
    
    :param root_person_id: ID персоны для корня графа
    :param depth: Глубина BFS (кол-во уровней Person <-> Union переходов)
    """
    redirect = _require_family_session(request)
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
async def family_tree_json(
    root_person_id: int = Query(..., description="ID персоны для корня графа"),
    depth: int = Query(2, ge=1, le=6, description="Глубина поиска (1-6)"),
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
    :param depth: Глубина BFS (1-6)
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
async def family_person(
    request: Request,
    person_id: int,
    session: Session = Depends(get_db),
):
    person = session.query(Person).filter(Person.person_id == person_id).first()
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

    name = " ".join(
        [p for p in (person_i18n.first_name if person_i18n else None, person_i18n.last_name if person_i18n else None) if p]
    ).strip()
    if not name:
        name = f"Персона #{person_id}"

    memories_count = session.query(Memory).filter(Memory.author_id == person_id).count()
    quotes_count = session.query(Quote).filter(Quote.author_id == person_id).count()

    return templates.TemplateResponse(
        "family/profile.html",
        {
            "request": request,
            "person": person,
            "name": name,
            "memories_count": memories_count,
            "quotes_count": quotes_count,
            "message": None,
        },
    )


@router.get("/family/timeline", response_class=HTMLResponse)
async def family_timeline(
    request: Request,
    person_id: int | None = Query(None, description="Фильтр timeline по персоне"),
    union_id: int | None = Query(None, description="Фильтр timeline по союзу"),
    db: Session = Depends(get_db),
):
    redirect = _require_family_session(request)
    if redirect:
        return redirect

    from app.models import Union, UnionChild
    
    items = []

    related_union = None
    related_person_ids: set[int] = set()
    if union_id is not None:
        related_union = db.query(Union).filter(Union.id == union_id).first()
        if related_union:
            if related_union.partner1_id:
                related_person_ids.add(related_union.partner1_id)
            if related_union.partner2_id:
                related_person_ids.add(related_union.partner2_id)
            child_ids = [
                row.child_id
                for row in db.query(UnionChild).filter(UnionChild.union_id == related_union.id).all()
                if row.child_id is not None
            ]
            related_person_ids.update(child_ids)

    for person in db.query(Person).all():
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
                    "date_display": person.birth_date or "—",
                    "title": f"Рождение: {name}",
                    "text": "",
                    "person_id": person.person_id,
                    "avatar_url": person.avatar_url,
                    "source": "people",
                    "type": "birth",
                }
            )

        if person.death_date:
            items.append(
                {
                    "date": person.death_date,
                    "date_display": person.death_date or "—",
                    "title": f"Смерть: {name}",
                    "text": "",
                    "person_id": person.person_id,
                    "avatar_url": person.avatar_url,
                    "source": "people",
                    "type": "death",
                }
            )

    for union in db.query(Union).all():
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
                    "date_display": union.start_date or "—",
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
                    "date_display": union.end_date or "—",
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

    memories_query = db.query(Memory).filter(
        Memory.author_id.isnot(None),
        text_filter,
        Memory.is_archived == False,
    )

    if person_id is not None:
        memories_query = memories_query.filter(Memory.author_id == person_id)
    if union_id is not None and related_person_ids:
        memories_query = memories_query.filter(Memory.author_id.in_(list(related_person_ids)))

    memories = memories_query.all()

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

        items.append(
            {
                "date": memory.created_at or "",
                "date_display": memory.created_at or "—",
                "title": author_name,
                "text": text[:280],
                "memory_id": memory.id,
                "person_id": memory.author_id,
                "avatar_url": memory.author.avatar_url if memory.author else None,
                "source": "people",
                "type": "memory_recording",
            }
        )

    items.sort(key=lambda x: x["date"], reverse=True)

    return templates.TemplateResponse(
        "family/timeline.html",
        {"request": request, "items": items},
    )


@router.get("/family/welcome", response_class=HTMLResponse)
async def family_welcome(request: Request, person_id: int = Query(None), db: Session = Depends(get_db)):
    redirect = _require_family_session(request)
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
        .filter(Memory.transcription_status == "published", text_filter)
        .order_by(func.random())
        .first()
    )

    memory_text = ""
    memory_date = ""
    author_name = ""
    author_avatar = ""
    memory_id = None

    if memory:
        memory_id = memory.id
        memory_date = memory.created_at or ""
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
                author_avatar = person.avatar_url

    if not memory_text:
        memory_text = "Добро пожаловать в TimeWoven! Напишите боту первую историю."

    return templates.TemplateResponse(
        "family/welcome.html",
        {
            "request": request,
            "person_id": person_id,
            "memory_id": memory_id,
            "memory_text": memory_text,
            "memory_date": memory_date,
            "author_name": author_name,
            "author_avatar": author_avatar,
        },
    )


@router.get("/who-am-i", response_class=HTMLResponse)
async def who_am_i(request: Request, next: str = "/family/welcome", db: Session = Depends(get_db)):
    if _get_family_member_id(request) is not None:
        return RedirectResponse(url="/family/welcome", status_code=303)

    people = []
    for person in (
        db.query(Person)
        .filter(Person.is_alive == 1)
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
async def who_am_i_submit(
    person_id: int = Form(...),
    next: str = Form("/family/welcome"),
    db: Session = Depends(get_db),
):
    person = (
        db.query(Person)
        .filter(
            Person.person_id == person_id,
            Person.is_alive == 1,
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
async def who_am_i_pin(
    request: Request,
    person_id: int = Query(...),
    next: str = Query("/family/welcome"),
    db: Session = Depends(get_db),
):
    if _get_family_member_id(request) is not None:
        return RedirectResponse(url="/family/welcome", status_code=303)

    person = (
        db.query(Person)
        .filter(
            Person.person_id == person_id,
            Person.is_alive == 1,
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

    return templates.TemplateResponse(
        "family/pin_form.html",
        {
            "request": request,
            "person_id": person_id,
            "name": name,
            "avatar_url": person.avatar_url,
            "next": next,
            "error": None,
        },
    )


@router.post("/who-am-i/pin")
async def who_am_i_pin_submit(
    person_id: int = Form(...),
    pin: str = Form(...),
    next: str = Form("/family/welcome"),
    db: Session = Depends(get_db),
):
    decoded_next = unquote(next or "")
    person = (
        db.query(Person)
        .filter(
            Person.person_id == person_id,
            Person.is_alive == 1,
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
                resp_avatar_url = author.avatar_url
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
        },
    )


@router.post("/family/reply/{memory_id}", response_class=HTMLResponse)
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


@router.post("/profile/avatar")
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

    avatar_dir = BASE_DIR / "web" / "static" / "images" / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    filename = f"profile_{resolved_person_id}_{uuid4().hex}{suffix}"
    target = avatar_dir / filename

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    target.write_bytes(content)
    person.avatar_url = f"/static/images/avatars/{filename}"
    db.commit()

    return RedirectResponse(url=f"/family/person/{resolved_person_id}", status_code=303)

