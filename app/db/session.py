from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from functools import lru_cache
import os
import urllib.parse

from app.core.family_resolver import resolve_family

# 🔥 ТОЛЬКО из переменной окружения
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set")

_BASE_DATABASE_URL_PARSED = urllib.parse.urlparse(DATABASE_URL)

Base = declarative_base()


def _build_database_url_for_db(db_name: str) -> str:
    return _BASE_DATABASE_URL_PARSED._replace(path=f"/{db_name}").geturl()


@lru_cache(maxsize=32)
def _engine_for_db(db_name: str):
    return create_engine(
        _build_database_url_for_db(db_name),
        pool_pre_ping=True,
        connect_args={"client_encoding": "utf8"},
    )


def _default_db_name() -> str:
    # Backward-compatible default for background jobs / legacy routes.
    return resolve_family("bondarev")["db_name"]


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=_engine_for_db(_default_db_name()),
)


def get_db(slug: str = "bondarev"):
    s = (slug or "").strip() or "bondarev"
    try:
        family = resolve_family(s)
    except Exception:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Family not found: {s}")

    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=_engine_for_db(family["db_name"]),
    )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()