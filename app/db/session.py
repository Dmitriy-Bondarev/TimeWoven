from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import os
import urllib.parse

from app.core.family_resolver import resolve_family

# 🔥 ТОЛЬКО из переменной окружения
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set")

slug = os.getenv("DEFAULT_FAMILY_SLUG", "bondarev")
family = resolve_family(slug)

DATABASE_URL = urllib.parse.urlparse(DATABASE_URL)._replace(
    path=f"/{family['db_name']}"
).geturl()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"client_encoding": "utf8"},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()