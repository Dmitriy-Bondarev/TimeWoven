import os
import urllib.parse

from sqlalchemy import create_engine, text


def _build_core_database_url() -> str:
    base_url = os.getenv("DATABASE_URL")
    if not base_url:
        raise ValueError("DATABASE_URL is not set")

    parsed = urllib.parse.urlparse(base_url)
    return parsed._replace(path="/timewoven_core").geturl()


CORE_DATABASE_URL = _build_core_database_url()

core_engine = create_engine(
    CORE_DATABASE_URL,
    pool_pre_ping=True,
    connect_args={"client_encoding": "utf8"},
)


def resolve_family(slug: str) -> dict:
    with core_engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT db_name, data_path
                FROM families
                WHERE slug = :slug
                """
            ),
            {"slug": slug},
        ).fetchone()

    if not result:
        raise Exception(f"Family not found: {slug}")

    return {
        "db_name": result[0],
        "data_path": result[1],
    }
