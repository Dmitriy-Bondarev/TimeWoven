from fastapi import APIRouter
from sqlalchemy import text

from app.core.family_resolver import resolve_family
from app.db.session import SessionLocal

router = APIRouter()


@router.get("/health")
def health():
    db_status = "ok"
    resolver_status = "ok"

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    try:
        resolve_family(None)
    except Exception:
        resolver_status = "error"

    return {
        "status": "ok" if db_status == "ok" and resolver_status == "ok" else "degraded",
        "db": db_status,
        "resolver": resolver_status,
    }
