import hashlib
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
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


def get_client_ip(request: Request) -> str:
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        # Take first IP from the list: "client, proxy1, proxy2"
        first = xff.split(",")[0].strip()
        if first:
            return first
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client else None
    return str(host or "unknown")


def _admin_session_idle_timeout_seconds() -> int:
    raw = os.getenv("ADMIN_SESSION_IDLE_TIMEOUT_MINUTES", "").strip()
    try:
        minutes = int(raw) if raw else 120
    except Exception:
        minutes = 120
    if minutes <= 0:
        minutes = 120
    return minutes * 60


def admin_session_cookie_max_age_seconds() -> int:
    return _admin_session_idle_timeout_seconds()


def make_admin_token(*, issued_at: int | None = None) -> str:
    """Return admin session cookie value: '<issued_at>:<sha256(username:password:issued_at)>'."""
    ts = int(issued_at if issued_at is not None else time.time())
    expected_username = os.getenv("ADMIN_USERNAME", "admin")
    expected_password = os.getenv("ADMIN_PASSWORD", "")
    digest = hashlib.sha256(f"{expected_username}:{expected_password}:{ts}".encode("utf-8")).hexdigest()
    return f"{ts}:{digest}"


def _parse_admin_cookie(raw: str | None) -> tuple[int, str] | None:
    value = (raw or "").strip()
    if not value:
        return None
    if ":" not in value:
        return None
    issued_at_s, digest = value.split(":", 1)
    issued_at_s = issued_at_s.strip()
    digest = digest.strip()
    if not issued_at_s.isdigit() or not digest:
        return None
    try:
        issued_at = int(issued_at_s)
    except Exception:
        return None
    return issued_at, digest


def _is_admin_authenticated(request: Request) -> bool:
    parsed = _parse_admin_cookie(request.cookies.get(ADMIN_COOKIE_NAME))
    if not parsed:
        return False
    issued_at, digest = parsed
    now = int(time.time())
    if now - issued_at > _admin_session_idle_timeout_seconds():
        return False
    expected_username = os.getenv("ADMIN_USERNAME", "admin")
    expected_password = os.getenv("ADMIN_PASSWORD", "")
    expected_digest = hashlib.sha256(
        f"{expected_username}:{expected_password}:{issued_at}".encode("utf-8")
    ).hexdigest()
    return digest == expected_digest


def require_admin(request: Request):
    """Return a RedirectResponse to /admin/login if not authenticated, else None."""
    if _is_admin_authenticated(request):
        return None

    next_path = request.url.path
    if request.url.query:
        next_path = f"{next_path}?{request.url.query}"
    resp = RedirectResponse(url=f"/admin/login?next={next_path}", status_code=303)
    resp.delete_cookie(key=ADMIN_COOKIE_NAME, path="/")
    return resp


@dataclass
class _RateLimitDecision:
    allowed: bool
    retry_after_seconds: int | None = None


class InMemoryRateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()

    def allow(self, key: str, *, limit: int, window_seconds: int) -> _RateLimitDecision:
        if limit <= 0:
            return _RateLimitDecision(allowed=True)
        if window_seconds <= 0:
            return _RateLimitDecision(allowed=True)

        now = time.time()
        window_start = now - float(window_seconds)
        with self._lock:
            q = self._hits.get(key)
            if q is None:
                q = deque()
                self._hits[key] = q

            while q and q[0] < window_start:
                q.popleft()

            if len(q) >= limit:
                retry_after = int(max(1.0, (q[0] + float(window_seconds)) - now))
                return _RateLimitDecision(allowed=False, retry_after_seconds=retry_after)

            q.append(now)
            return _RateLimitDecision(allowed=True)


_admin_login_rate_limiter = InMemoryRateLimiter()


def check_admin_login_rate_limit(request: Request) -> _RateLimitDecision:
    raw_limit = os.getenv("ADMIN_LOGIN_RATE_LIMIT", "").strip()
    raw_window = os.getenv("ADMIN_LOGIN_RATE_WINDOW_SECONDS", "").strip()
    try:
        limit = int(raw_limit) if raw_limit else 10
    except Exception:
        limit = 10
    try:
        window_seconds = int(raw_window) if raw_window else 900
    except Exception:
        window_seconds = 900
    if limit <= 0:
        limit = 10
    if window_seconds <= 0:
        window_seconds = 900

    ip = get_client_ip(request)
    return _admin_login_rate_limiter.allow(ip, limit=limit, window_seconds=window_seconds)


def _clear_admin_login_rate_limiter_for_tests() -> None:
    _admin_login_rate_limiter.clear()