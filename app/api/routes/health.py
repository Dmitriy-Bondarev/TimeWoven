from fastapi import APIRouter
from sqlalchemy import text
from app.db.session import SessionLocal
from app.core.family_resolver import resolve_family

router = APIRouter()

@router.get("/health")
def health():
    db_status = "ok"
    resolver_status = "ok"

    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "fail"

    try:
        resolve_family("bondarev")
    except Exception:
        resolver_status = "fail"

    return {
        "status": "ok" if db_status == "ok" and resolver_status == "ok" else "degraded",
        "db": db_status,
        "resolver": resolver_status
    }