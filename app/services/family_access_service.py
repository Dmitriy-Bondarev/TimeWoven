import base64
import hashlib
import os
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Deque, Tuple

import pyotp
from cryptography.fernet import Fernet
from fastapi import Request
from sqlalchemy.orm import Session

from app.models import FamilyAccessSession, Person, PersonAccessBackupCode

FAMILY_ACCESS_COOKIE = "tw_family_access"
FAMILY_ACCESS_LEGACY_COOKIE = "family_member_id"

DEFAULT_SESSION_TTL = timedelta(days=7)

_pepper: str = os.environ.get("TW_FAMILY_ACCESS_PEPPER", "")
_fernet: Fernet | None = None

_rate_windows: dict[Tuple[str, str], Deque[float]] = defaultdict(
    lambda: deque(maxlen=64)
)
_RATE_WINDOW_SEC = 15 * 60
_RATE_MAX = 20


def _token_hash(token: str) -> str:
    p = _pepper or "default-pepper-configure-TW_FAMILY_ACCESS_PEPPER"
    return hashlib.sha256(f"{p}:{token}".encode("utf-8")).hexdigest()


def _backup_code_hash(code_normalized: str) -> str:
    c = code_normalized.strip().upper().replace(" ", "")
    p = _pepper or "default-pepper-configure-TW_FAMILY_ACCESS_PEPPER"
    return hashlib.sha256(f"backup:{p}:{c}".encode("utf-8")).hexdigest()


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet

    raw = os.environ.get("TW_FAMILY_FERNET_KEY", "").strip()
    if not raw:
        seed = os.environ.get("TW_FAMILY_FERNET_DEV_SEED", "timewoven-dev-fernet-seed")
        key = base64.urlsafe_b64encode(hashlib.sha256(seed.encode("utf-8")).digest())
        _fernet = Fernet(key)
    else:
        _fernet = Fernet(raw.encode("ascii") if isinstance(raw, str) else raw)
    return _fernet


def encrypt_totp_secret(secret_b32: str) -> str:
    f = get_fernet()
    return f.encrypt(secret_b32.encode("utf-8")).decode("ascii")


def decrypt_totp_secret(stored: str) -> str:
    f = get_fernet()
    return f.decrypt(stored.encode("ascii")).decode("utf-8")


def new_totp_provisioning_uri(secret_b32: str, person_label: str) -> str:
    issuer = os.environ.get("TW_FAMILY_TOTP_ISSUER", "TimeWoven")
    return pyotp.totp.TOTP(secret_b32).provisioning_uri(
        name=person_label, issuer_name=issuer
    )


def verify_totp_code(secret_b32: str, code: str) -> bool:
    c = (code or "").strip().replace(" ", "")
    if not c.isdigit() or len(c) != 6:
        return False
    return bool(pyotp.TOTP(secret_b32).verify(c, valid_window=1))


def check_rate_limit(client_ip: str, public_uuid: str) -> bool:
    now = time.time()
    key = (client_ip or "unknown", str(public_uuid))
    dq = _rate_windows[key]
    while dq and now - dq[0] > _RATE_WINDOW_SEC:
        dq.popleft()
    if len(dq) >= _RATE_MAX:
        return False
    dq.append(now)
    return True


@dataclass
class FamilyViewer:
    person_id: int
    source: str  # "totp_session" | "legacy_cookie"


def _legacy_family_member_id(request: Request) -> int | None:
    raw = request.cookies.get(FAMILY_ACCESS_LEGACY_COOKIE, "").strip()
    if not raw or not raw.isdigit():
        return None
    return int(raw)


def resolve_viewer(request: Request, db: Session) -> FamilyViewer | None:
    tok = (request.cookies.get(FAMILY_ACCESS_COOKIE) or "").strip()
    sess = get_valid_family_access_session(db, tok)
    if sess:
        return FamilyViewer(person_id=sess.person_id, source="totp_session")

    if os.environ.get("TW_FAMILY_ALLOW_LEGACY_COOKIE", "1") == "1":
        leg = _legacy_family_member_id(request)
        if leg is not None:
            return FamilyViewer(person_id=leg, source="legacy_cookie")
    return None


def _cookie_secure_flag(request: Request) -> bool:
    if os.environ.get("TW_COOKIE_SECURE", "1") == "0":
        return False
    if request.url.scheme == "https":
        return True
    return bool(os.environ.get("TW_BEHIND_HTTPS", ""))


def set_family_access_cookies(
    response, *, token: str, max_age_sec: int, request: Request
) -> None:
    response.set_cookie(
        key=FAMILY_ACCESS_COOKIE,
        value=token,
        max_age=max_age_sec,
        path="/",
        httponly=True,
        samesite="lax",
        secure=_cookie_secure_flag(request),
    )


def clear_family_access_cookie(response, request: Request) -> None:
    response.set_cookie(
        key=FAMILY_ACCESS_COOKIE,
        value="",
        max_age=0,
        path="/",
        httponly=True,
        samesite="lax",
        secure=_cookie_secure_flag(request),
    )


def find_person_by_public_uuid(db: Session, u: str) -> Person | None:
    s = (u or "").strip()
    if not s:
        return None
    return db.query(Person).filter(Person.public_uuid == s).first()


def get_valid_family_access_session(
    db: Session, raw_cookie: str | None
) -> FamilyAccessSession | None:
    t = (raw_cookie or "").strip()
    if not t or len(t) < 20:
        return None
    h = _token_hash(t)
    now = datetime.now(timezone.utc)
    return (
        db.query(FamilyAccessSession)
        .filter(
            FamilyAccessSession.session_token_hash == h,
            FamilyAccessSession.expires_at > now,
            FamilyAccessSession.revoked_at.is_(None),
        )
        .first()
    )


def create_family_access_session(
    db: Session,
    *,
    person_id: int,
    client_ip: str | None,
    user_agent: str | None,
    ttl: timedelta = DEFAULT_SESSION_TTL,
) -> tuple[str, FamilyAccessSession]:
    token = secrets.token_urlsafe(32)
    h = _token_hash(token)
    now = datetime.now(timezone.utc)
    row = FamilyAccessSession(
        person_id=person_id,
        session_token_hash=h,
        created_at=now,
        expires_at=now + ttl,
        revoked_at=None,
        created_ip=(client_ip or None) and client_ip[:64],
        user_agent=(user_agent or None) and user_agent[:2000],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return token, row


def revoke_all_sessions_for_person(db: Session, person_id: int) -> int:
    now = datetime.now(timezone.utc)
    n = 0
    for row in (
        db.query(FamilyAccessSession)
        .filter(
            FamilyAccessSession.person_id == person_id,
            FamilyAccessSession.revoked_at.is_(None),
        )
        .all()
    ):
        row.revoked_at = now
        n += 1
    if n:
        db.commit()
    return n


def generate_backup_code_plain() -> str:
    parts = [secrets.token_hex(2).upper() for _ in range(4)]
    return "-".join(parts)


def store_backup_codes(db: Session, person_id: int, plaintext_codes: list[str]) -> None:
    now = datetime.now(timezone.utc)
    for c in plaintext_codes:
        db.add(
            PersonAccessBackupCode(
                person_id=person_id,
                code_hash=_backup_code_hash(c),
                used_at=None,
                created_at=now,
            )
        )


def use_one_backup_code(db: Session, person_id: int, code: str) -> bool:
    h = _backup_code_hash(code)
    now = datetime.now(timezone.utc)
    row = (
        db.query(PersonAccessBackupCode)
        .filter(
            PersonAccessBackupCode.person_id == person_id,
            PersonAccessBackupCode.code_hash == h,
            PersonAccessBackupCode.used_at.is_(None),
        )
        .first()
    )
    if not row:
        return False
    row.used_at = now
    db.commit()
    return True


def clear_backup_codes(db: Session, person_id: int) -> None:
    db.query(PersonAccessBackupCode).filter(
        PersonAccessBackupCode.person_id == person_id
    ).delete()
    db.commit()


def person_family_access_permitted(p: Person) -> bool:
    if not p.family_access_enabled:
        return False
    if p.family_access_revoked_at is not None:
        return False
    if not p.totp_secret_encrypted:
        return False
    return True


def set_totp_last_used(db: Session, person_id: int) -> None:
    p = db.query(Person).filter(Person.person_id == person_id).first()
    if p:
        p.totp_last_used_at = datetime.now(timezone.utc)
        db.commit()
