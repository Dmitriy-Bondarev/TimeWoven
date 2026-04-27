import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.routes.tree import _family_timeline_date_display
from app.db.session import get_db
from app.services.timeline_service import get_timeline, create_event

router = APIRouter(prefix="/timeline", tags=["timeline"])
BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))
logger = logging.getLogger(__name__)


@router.get("/{family_id}")
def read_timeline(request: Request, family_id: int, db: Session = Depends(get_db)):
    try:
        events = get_timeline(db, family_id)
    except Exception as error:
        logger.warning("Timeline read error for family_id=%s: %s", family_id, error)
        return templates.TemplateResponse(
            "family/timeline.html",
            {
                "request": request,
                "items": [],
                "timeline_events": [],
                "empty_message": "Воспоминаний пока нет",
            },
            status_code=200,
        )

    items = []
    for event in events or []:
        raw_date = getattr(event, "date", None)
        date_sort = raw_date.isoformat() if hasattr(raw_date, "isoformat") else str(raw_date or "")
        date_display = _family_timeline_date_display(raw_date)
        items.append(
            {
                "date": date_sort,
                "date_display": date_display or "—",
                "title": getattr(event, "title", "Событие") or "Событие",
                "text": getattr(event, "description", "") or "",
                "person_id": getattr(event, "person_id", None),
                "avatar_url": None,
                "source": "events",
                "type": "event",
            }
        )

    if not items:
        return templates.TemplateResponse(
            "family/timeline.html",
            {
                "request": request,
                "items": [],
                "timeline_events": [],
                "empty_message": "Воспоминаний пока нет",
            },
            status_code=200,
        )

    return templates.TemplateResponse(
        "family/timeline.html",
        {
            "request": request,
            "items": items,
            "timeline_events": [],
            "empty_message": "",
        },
        status_code=200,
    )


@router.post("/")
def add_event(data: dict, db: Session = Depends(get_db)):
    return create_event(db, data)
    
