import hashlib
import os
from fastapi import Request
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeSerializer, BadSignature

SESSION_SECRET = os.getenv("SESSION_SECRET", "changeme")

_admin_username = os.getenv("ADMIN_USERNAME", "admin")
_admin_password = os.getenv("ADMIN_PASSWORD", "")
ADMIN_USERS = {
    _admin_username: hashlib.sha256(_admin_password.encode()).hexdigest(),
}


def is_admin(request: Request) -> bool:
    s = URLSafeSerializer(SESSION_SECRET)
    token = request.cookies.get("admin_token")
    if not token:
        return False
    try:
        s.loads(token)
        return True
    except BadSignature:
        return False


def require_admin(request: Request):
    if not is_admin(request):
        return RedirectResponse(
            url=f"/admin/login?next={request.url.path}", status_code=303
        )
    return None
