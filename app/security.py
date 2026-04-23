import hashlib
import os
from datetime import datetime

from fastapi import Request
from fastapi.responses import RedirectResponse

ADMIN_COOKIE_NAME = "tw_admin_session"


def get_daily_password() -> str:
    """Return a deterministic daily password derived from date and optional salt."""
    salt = os.getenv("TW_EXPLORER_SALT", "timewoven-explorer")
    today = datetime.utcnow().strftime("%Y-%m-%d")
    digest = hashlib.sha256(f"{salt}:{today}".encode("utf-8")).hexdigest()
    return digest[:16]


def _is_admin_authenticated(request: Request) -> bool:
    """Return True if the request carries a valid admin session cookie."""
    expected_username = os.getenv("ADMIN_USERNAME", "admin")
    expected_password = os.getenv("ADMIN_PASSWORD", "")
    # Cookie value is sha256(username:password) stored at login time.
    expected_token = hashlib.sha256(
        f"{expected_username}:{expected_password}".encode("utf-8")
    ).hexdigest()
    return request.cookies.get(ADMIN_COOKIE_NAME) == expected_token


def require_admin(request: Request):
    """Return a RedirectResponse to /admin/login if not authenticated, else None."""
    if not _is_admin_authenticated(request):
        next_path = request.url.path
        if request.url.query:
            next_path = f"{next_path}?{request.url.query}"
        return RedirectResponse(url=f"/admin/login?next={next_path}", status_code=303)
    return None


def make_admin_token() -> str:
    """Return the expected admin session token (for use when setting cookie at login)."""
    expected_username = os.getenv("ADMIN_USERNAME", "admin")
    expected_password = os.getenv("ADMIN_PASSWORD", "")
    return hashlib.sha256(
        f"{expected_username}:{expected_password}".encode("utf-8")
    ).hexdigest()