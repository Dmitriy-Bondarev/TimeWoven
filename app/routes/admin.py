# app/routes/admin.py

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Memory, PersonI18n
from app.security import require_admin

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)

templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def admin_index():
    return {"message": "Admin index"}


@router.get("/transcriptions")
async def admin_transcriptions(request: Request, db: Session = Depends(get_db)):
    redirect = require_admin(request)
    if redirect:
        return redirect

    memories = (
        db.query(Memory)
        .filter(
            Memory.transcription_status.in_(["review", "pending"]),
            Memory.audio_url.isnot(None),
        )
        .order_by(Memory.id.desc())
        .all()
    )

    result = []
    for m in memories:
        author_name = None
        if m.author_id:
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

        result.append(
            {
                "id": m.id,
                "author_name": author_name,
                "audio_url": m.audio_url,
                "transcript_verbatim": m.transcript_verbatim,
                "transcript_readable": m.transcript_readable,
                "transcription_status": m.transcription_status,
                "created_at": m.created_at,
            }
        )

    return templates.TemplateResponse(
        "admin/admin_transcriptions.html",
        {"request": request, "memories": result},
    )


@router.post("/transcriptions/{memory_id}/publish")
async def publish_transcription(
    memory_id: int,
    request: Request,
    transcript_verbatim: str = Form(""),
    transcript_readable: str = Form(""),
    db: Session = Depends(get_db),
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    memory = db.query(Memory).filter(Memory.id == memory_id).first()
    if memory:
        memory.transcript_verbatim = transcript_verbatim
        memory.transcript_readable = transcript_readable
        memory.transcription_status = "published"
        db.commit()

    return RedirectResponse(url="/admin/transcriptions", status_code=303)