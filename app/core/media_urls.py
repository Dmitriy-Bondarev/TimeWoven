import os
from urllib.parse import urlparse

from app.core.family_resolver import resolve_family


def default_family_slug() -> str:
    return (os.getenv("DEFAULT_FAMILY_SLUG") or "bondarev").strip() or "bondarev"


def media_base_url(slug: str) -> str:
    s = (slug or "").strip() or default_family_slug()
    return f"/media/{s}"


def normalize_media_url(url: str | None, slug: str) -> str | None:
    """
    Convert legacy /static media links to new /media/{slug}/... links.

    Rules:
    - Keep http(s) URLs as-is.
    - Keep already-normalized /media/... as-is.
    - Rewrite:
        static audio            -> media audio
        static avatars current  -> media avatars/current
        static avatars history  -> media avatars/history
    """
    raw = (url or "").strip()
    if not raw:
        return None

    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"}:
        return raw

    if raw.startswith("/media/"):
        return raw

    base = media_base_url(slug)

    static_prefix = "/static"

    if raw.startswith(static_prefix + "/audio/"):
        return base + raw[len(static_prefix) :]

    if raw.startswith(static_prefix + "/images/avatars/"):
        filename = raw.split(static_prefix + "/images/avatars/", 1)[1]
        return f"{base}/avatars/current/{filename}"

    if raw.startswith(static_prefix + "/avatars/"):
        filename = raw.split(static_prefix + "/avatars/", 1)[1]
        return f"{base}/avatars/history/{filename}"

    return raw


def family_data_path_for_slug(slug: str) -> str:
    family = resolve_family((slug or "").strip() or default_family_slug())
    return str(family["data_path"])

