# from __future__ import annotations

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
MAX_BODY_BYTES = 10_000

_pepper: str = os.environ.get("TW_FAMILY_ACCESS_PEPPER", "")
_fernet: Fernet | None = None

_rate_windows: dict[Tuple[str, str], Deque[float]] = defaultdict(lambda: deque(maxlen=64))
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
    return pyotp.totp.TOTP(secret_b32).provisioning_uri(name=person_label, issuer_name=issuer)


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


def cookie_secure_flag(request: Request) -> bool:
    if os.environ.get("TW_COOKIE_SECURE", "1") == "0":
        return False
    if request is not None and request.url.scheme == "https":
        return True
    return bool(os.environ.get("TW_BEHIND_HTTPS", ""))


def set_family_access_cookies(response, *, token: str, max_age_sec: int, request: Request) -> None:
    secure = cookie_secure_flag(request)
    response.set_cookie(
        key=FAMILY_ACCESS_COOKIE,
        value=token,
        max_age=max_age_sec,
        path="/",
        httponly=True,
        samesite="lax",
        secure=secure,
    )


def clear_family_access_cookie(response, request: Request) -> None:
    secure = cookie_secure_flag(request)
    response.set_cookie(
        key=FAMILY_ACCESS_COOKIE,
        value="",
        max_age=0,
        path="/",
        httponly=True,
        samesite="lax",
        secure=secure,
    )


def find_person_by_public_uuid(db: Session, u: str) -> Person | None:
    s = (u or "").strip()
    if not s:
        return None
    return db.query(Person).filter(Person.public_uuid == s).first()


def get_valid_family_access_session(db: Session, raw_cookie: str | None) -> FamilyAccessSession | None:
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


def clear_backup_codes(db: Session, person_id: int) -> None:
    db.query(PersonAccessBackupCode).filter(PersonAccessBackupCode.person_id == person_id).delete()
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

# from __future__ import annotations

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
MAX_BODY_BYTES = 10_000

_pepper: str = os.environ.get("TW_FAMILY_ACCESS_PEPPER", "")
_fernet: Fernet | None = None

_rate_windows: dict[Tuple[str, str], Deque[float]] = defaultdict(lambda: deque(maxlen=64))
_RATE_WINDOW_SEC = 15 * 60
_RATE_MAX = 20


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
    return pyotp.totp.TOTP(secret_b32).provisioning_uri(name=person_label, issuer_name=issuer)


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


def cookie_secure_flag(request: Request) -> bool:
    if os.environ.get("TW_COOKIE_SECURE", "1") == "0":
        return False
    if request is not None and request.url.scheme == "https":
        return True
    return bool(os.environ.get("TW_BEHIND_HTTPS", ""))


def set_family_access_cookies(response, *, token: str, max_age_sec: int, request: Request) -> None:
    secure = cookie_secure_flag(request)
    response.set_cookie(
        key=FAMILY_ACCESS_COOKIE,
        value=token,
        max_age=max_age_sec,
        path="/",
        httponly=True,
        samesite="lax",
        secure=secure,
    )


def clear_family_access_cookie(response, request: Request) -> None:
    secure = cookie_secure_flag(request)
    response.set_cookie(
        key=FAMILY_ACCESS_COOKIE,
        value="",
        max_age=0,
        path="/",
        httponly=True,
        samesite="lax",
        secure=secure,
    )


def find_person_by_public_uuid(db: Session, u: str) -> Person | None:
    s = (u or "").strip()
    if not s:
        return None
    return db.query(Person).filter(Person.public_uuid == s).first()


def get_valid_family_access_session(db: Session, raw_cookie: str | None) -> FamilyAccessSession | None:
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


def revoke_session_token(db: Session, raw_cookie: str | None) -> bool:
    t = (raw_cookie or "").strip()
    if not t:
        return False
    h = _token_hash(t)
    now = datetime.now(timezone.utc)
    row = (
        db.query(FamilyAccessSession)
        .filter(
            FamilyAccessSession.session_token_hash == h,
            FamilyAccessSession.revoked_at.is_(None),
        )
        .first()
    )
    if not row:
        return False
    row.revoked_at = now
    db.commit()
    return True


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


def clear_backup_codes(db: Session, person_id: int) -> None:
    db.query(PersonAccessBackupCode).filter(PersonAccessBackupCode.person_id == person_id).delete()
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
# (removed stray patch marker)
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
MAX_BODY_BYTES = 10_000

_pepper: str = os.environ.get("TW_FAMILY_ACCESS_PEPPER", "")
_fernet: Fernet | None = None

# Simple in-process rate limit: (ip, public_uuid) -> timestamps of attempts
_rate_windows: dict[Tuple[str, str], Deque[float]] = defaultdict(lambda: deque(maxlen=64))
_RATE_WINDOW_SEC = 15 * 60
_RATE_MAX = 20


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
    return pyotp.totp.TOTP(secret_b32).provisioning_uri(name=person_label, issuer_name=issuer)


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


def cookie_secure_flag(request: Request) -> bool:
    if os.environ.get("TW_COOKIE_SECURE", "1") == "0":
        return False
    if request is not None and request.url.scheme == "https":
        return True
    return bool(os.environ.get("TW_BEHIND_HTTPS", ""))


def set_family_access_cookies(response, *, token: str, max_age_sec: int, request: Request) -> None:
    secure = cookie_secure_flag(request)
    response.set_cookie(
        key=FAMILY_ACCESS_COOKIE,
        value=token,
        max_age=max_age_sec,
        path="/",
        httponly=True,
        samesite="lax",
        secure=secure,
    )


def clear_family_access_cookie(response, request: Request) -> None:
    secure = cookie_secure_flag(request)
    response.set_cookie(
        key=FAMILY_ACCESS_COOKIE,
        value="",
        max_age=0,
        path="/",
        httponly=True,
        samesite="lax",
        secure=secure,
    )


def find_person_by_public_uuid(db: Session, u: str) -> Person | None:
    s = (u or "").strip()
    if not s:
        return None
    return db.query(Person).filter(Person.public_uuid == s).first()


def get_valid_family_access_session(db: Session, raw_cookie: str | None) -> FamilyAccessSession | None:
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


def revoke_session_token(db: Session, raw_cookie: str | None) -> bool:
    t = (raw_cookie or "").strip()
    if not t:
        return False
    h = _token_hash(t)
    now = datetime.now(timezone.utc)
    row = (
        db.query(FamilyAccessSession)
        .filter(
            FamilyAccessSession.session_token_hash == h,
            FamilyAccessSession.revoked_at.is_(None),
        )
        .first()
    )
    if not row:
        return False
    row.revoked_at = now
    db.commit()
    return True


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


def clear_backup_codes(db: Session, person_id: int) -> None:
    db.query(PersonAccessBackupCode).filter(PersonAccessBackupCode.person_id == person_id).delete()
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

# from __future__ import annotations

"""
Minimal compatibility shim for `app/api/routes/admin.py`.

This repo checkout is missing the full family-access layer (sessions, backup codes tables,
public_uuid routes). The only goal here is: allow importing `admin.py` without failing
on `from app.services.family_access_service import (...)`.
"""

import base64
import os
import secrets

import pyotp


def _get_fernet():
    try:
        from cryptography.fernet import Fernet  # type: ignore

        raw = (os.getenv("TW_FAMILY_FERNET_KEY") or "").strip()
        if not raw:
            return None
        return Fernet(raw.encode("utf-8"))
    except Exception:
        return None


def generate_backup_code_plain() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(10))


def new_totp_provisioning_uri(secret: str, label: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=label, issuer_name="TimeWoven")


def verify_totp_code(secret: str, code: str) -> bool:
    raw = (code or "").strip()
    if not raw or not raw.isdigit():
        return False
    try:
        return bool(pyotp.TOTP(secret).verify(raw, valid_window=1))
    except Exception:
        return False


def encrypt_totp_secret(secret: str) -> str:
    s = (secret or "").strip()
    if not s:
        return ""
    f = _get_fernet()
    if f is not None:
        return f.encrypt(s.encode("utf-8")).decode("utf-8")
    return "b64:" + base64.b64encode(s.encode("utf-8")).decode("ascii")


def decrypt_totp_secret(encrypted: str) -> str:
    raw = (encrypted or "").strip()
    if not raw:
        return ""
    if raw.startswith("b64:"):
        try:
            return base64.b64decode(raw[4:].encode("ascii")).decode("utf-8")
        except Exception:
            return ""
    f = _get_fernet()
    if f is None:
        return ""
    try:
        return f.decrypt(raw.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


def find_person_by_public_uuid(db, public_uuid: str):
    # Schema/model may not support public_uuid in this checkout.
    try:
        import app.models as models

        Person = getattr(models, "Person", None)
        if Person is None or not hasattr(Person, "public_uuid"):
            return None
        return db.query(Person).filter(Person.public_uuid == str(public_uuid).strip()).first()
    except Exception:
        return None


def person_family_access_permitted(person) -> bool:
    try:
        return bool(getattr(person, "family_access_enabled", False)) and not getattr(
            person, "family_access_revoked_at", None
        )
    except Exception:
        return False


def clear_backup_codes(db, person_id: int) -> None:
    return None


def store_backup_codes(db, person_id: int, codes: list[str]) -> None:
    return None


def revoke_all_sessions_for_person(db, person_id: int) -> None:
    return None

# from __future__ import annotations

import base64
import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pyotp

try:
    from cryptography.fernet import Fernet, InvalidToken  # type: ignore
except Exception:  # pragma: no cover
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore

try:
    from sqlalchemy.orm import Session
except Exception:  # pragma: no cover
    Session = object  # type: ignore


# Minimal, defensive compatibility shim for `app/api/routes/admin.py`.
# Goal: provide all imported symbols and allow imports without crashing.


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _fernet() -> Fernet | None:  # type: ignore[name-defined]
    if Fernet is None:
        return None
    raw = (os.getenv("TW_FAMILY_FERNET_KEY") or "").strip()
    if not raw:
        return None
    try:
        return Fernet(raw.encode("utf-8"))
    except Exception:
        return None


def cookie_secure_flag(request) -> bool:
    try:
        proto = (request.headers.get("x-forwarded-proto") or "").strip().lower()
        if proto:
            return proto == "https"
        return str(getattr(request.url, "scheme", "")).lower() == "https"
    except Exception:
        return False


def generate_backup_code_plain() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(10))


def new_totp_provisioning_uri(secret: str, label: str) -> str:
    issuer = "TimeWoven"
    return pyotp.TOTP(secret).provisioning_uri(name=label, issuer_name=issuer)


def verify_totp_code(secret: str, code: str) -> bool:
    raw = (code or "").strip()
    if not raw or not raw.isdigit():
        return False
    try:
        return bool(pyotp.TOTP(secret).verify(raw, valid_window=1))
    except Exception:
        return False


def encrypt_totp_secret(secret: str) -> str:
    s = (secret or "").strip()
    if not s:
        return ""
    f = _fernet()
    if f is not None:
        return f.encrypt(s.encode("utf-8")).decode("utf-8")
    return "b64:" + base64.b64encode(s.encode("utf-8")).decode("ascii")


def decrypt_totp_secret(encrypted: str) -> str:
    raw = (encrypted or "").strip()
    if not raw:
        return ""
    if raw.startswith("b64:"):
        try:
            return base64.b64decode(raw[4:].encode("ascii")).decode("utf-8")
        except Exception:
            return ""
    f = _fernet()
    if f is None:
        return ""
    try:
        return f.decrypt(raw.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""
    except Exception:
        return ""


def _get_model(name: str):
    try:
        import app.models as models

        return getattr(models, name, None)
    except Exception:
        return None


def find_person_by_public_uuid(db: Session, public_uuid: str):
    Person = _get_model("Person")
    if Person is None or not hasattr(Person, "public_uuid"):
        return None
    u = (public_uuid or "").strip()
    if not u:
        return None
    try:
        return db.query(Person).filter(Person.public_uuid == u).first()  # type: ignore[attr-defined]
    except Exception:
        return None


def person_family_access_permitted(person) -> bool:
    try:
        enabled = bool(getattr(person, "family_access_enabled", False))
        revoked_at = getattr(person, "family_access_revoked_at", None)
        return enabled and not revoked_at
    except Exception:
        return False


def clear_backup_codes(db: Session, person_id: int) -> None:
    return None


def store_backup_codes(db: Session, person_id: int, codes: list[str]) -> None:
    return None


def revoke_all_sessions_for_person(db: Session, person_id: int) -> None:
    FamilyAccessSession = _get_model("FamilyAccessSession")
    if FamilyAccessSession is None:
        return None
    if not hasattr(FamilyAccessSession, "person_id") or not hasattr(FamilyAccessSession, "revoked_at"):
        return None
    try:
        now = _utc_now()
        db.query(FamilyAccessSession).filter(  # type: ignore[arg-type]
            FamilyAccessSession.person_id == person_id,  # type: ignore[attr-defined]
            FamilyAccessSession.revoked_at.is_(None),  # type: ignore[attr-defined]
        ).update({"revoked_at": now})
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


@dataclass
class FamilyAccessCookie:
    token: str
    public_uuid: str
    expires_at: datetime


def create_family_access_session(db: Session, *, person_id: int, public_uuid: str, max_age_seconds: int) -> str:
    token = secrets.token_urlsafe(24)
    FamilyAccessSession = _get_model("FamilyAccessSession")
    if FamilyAccessSession is None:
        return token
    try:
        now = _utc_now()
        expires_at = now + timedelta(seconds=int(max_age_seconds))
        row = FamilyAccessSession(  # type: ignore[call-arg]
            person_id=person_id,
            public_uuid=str(public_uuid),
            token_sha256=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            issued_at=now,
            expires_at=expires_at,
            revoked_at=None,
        )
        db.add(row)
        db.commit()
        return token
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return token


def get_valid_family_access_session(db: Session, token: str):
    FamilyAccessSession = _get_model("FamilyAccessSession")
    if FamilyAccessSession is None or not hasattr(FamilyAccessSession, "token_sha256"):
        return None
    try:
        now = _utc_now()
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        row = (
            db.query(FamilyAccessSession)
            .filter(
                FamilyAccessSession.token_sha256 == token_hash,  # type: ignore[attr-defined]
                FamilyAccessSession.revoked_at.is_(None),  # type: ignore[attr-defined]
            )
            .first()
        )
        if not row:
            return None
        expires_at = getattr(row, "expires_at", None)
        if isinstance(expires_at, datetime) and expires_at.replace(tzinfo=timezone.utc) < now:
            return None
        return row
    except Exception:
        return None


def set_family_access_cookies(response, cookie_value: str, *, max_age_seconds: int) -> None:
    try:
        response.set_cookie(
            "tw_family_access",
            value=cookie_value,
            max_age=max_age_seconds,
            path="/",
            httponly=True,
            samesite="lax",
        )
    except Exception:
        pass


def clear_family_access_cookie(response) -> None:
    try:
        response.delete_cookie("tw_family_access", path="/")
    except Exception:
        pass


def set_totp_last_used(db: Session, person_id: int) -> None:
    Person = _get_model("Person")
    if Person is None or not hasattr(Person, "totp_last_used_at"):
        return None
    try:
        db.query(Person).filter(Person.person_id == person_id).update(  # type: ignore[attr-defined]
            {"totp_last_used_at": _utc_now()}
        )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

# from __future__ import annotations

import base64
import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pyotp

try:
    from cryptography.fernet import Fernet, InvalidToken  # type: ignore
except Exception:  # pragma: no cover
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore

try:
    from sqlalchemy.orm import Session
except Exception:  # pragma: no cover
    Session = object  # type: ignore


# Minimal, defensive compatibility shim for `app/api/routes/admin.py`.
# The full family-access layer (sessions, backup codes, public_uuid routes, theme) is not
# currently present in this checkout. This module only guarantees import safety.


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _fernet() -> Fernet | None:  # type: ignore[name-defined]
    if Fernet is None:
        return None
    raw = (os.getenv("TW_FAMILY_FERNET_KEY") or "").strip()
    if not raw:
        return None
    try:
        return Fernet(raw.encode("utf-8"))
    except Exception:
        return None


def cookie_secure_flag(request) -> bool:
    try:
        proto = (request.headers.get("x-forwarded-proto") or "").strip().lower()
        if proto:
            return proto == "https"
        return str(getattr(request.url, "scheme", "")).lower() == "https"
    except Exception:
        return False


def generate_backup_code_plain() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(10))


def new_totp_provisioning_uri(secret: str, label: str) -> str:
    issuer = "TimeWoven"
    return pyotp.TOTP(secret).provisioning_uri(name=label, issuer_name=issuer)


def verify_totp_code(secret: str, code: str) -> bool:
    raw = (code or "").strip()
    if not raw or not raw.isdigit():
        return False
    try:
        return bool(pyotp.TOTP(secret).verify(raw, valid_window=1))
    except Exception:
        return False


def encrypt_totp_secret(secret: str) -> str:
    s = (secret or "").strip()
    if not s:
        return ""
    f = _fernet()
    if f is not None:
        return f.encrypt(s.encode("utf-8")).decode("utf-8")
    return "b64:" + base64.b64encode(s.encode("utf-8")).decode("ascii")


def decrypt_totp_secret(encrypted: str) -> str:
    raw = (encrypted or "").strip()
    if not raw:
        return ""
    if raw.startswith("b64:"):
        try:
            return base64.b64decode(raw[4:].encode("ascii")).decode("utf-8")
        except Exception:
            return ""
    f = _fernet()
    if f is None:
        return ""
    try:
        return f.decrypt(raw.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""
    except Exception:
        return ""


def _get_model(name: str):
    try:
        import app.models as models

        return getattr(models, name, None)
    except Exception:
        return None


def find_person_by_public_uuid(db: Session, public_uuid: str):
    Person = _get_model("Person")
    if Person is None or not hasattr(Person, "public_uuid"):
        return None
    u = (public_uuid or "").strip()
    if not u:
        return None
    try:
        return db.query(Person).filter(Person.public_uuid == u).first()  # type: ignore[attr-defined]
    except Exception:
        return None


def person_family_access_permitted(person) -> bool:
    try:
        enabled = bool(getattr(person, "family_access_enabled", False))
        revoked_at = getattr(person, "family_access_revoked_at", None)
        return enabled and not revoked_at
    except Exception:
        return False


def clear_backup_codes(db: Session, person_id: int) -> None:
    # Stub: backup codes table/model not available in current checkout.
    return None


def store_backup_codes(db: Session, person_id: int, codes: list[str]) -> None:
    # Stub: backup codes table/model not available in current checkout.
    return None


def revoke_all_sessions_for_person(db: Session, person_id: int) -> None:
    FamilyAccessSession = _get_model("FamilyAccessSession")
    if FamilyAccessSession is None:
        return None
    if not hasattr(FamilyAccessSession, "person_id") or not hasattr(FamilyAccessSession, "revoked_at"):
        return None
    try:
        now = _utc_now()
        db.query(FamilyAccessSession).filter(  # type: ignore[arg-type]
            FamilyAccessSession.person_id == person_id,  # type: ignore[attr-defined]
            FamilyAccessSession.revoked_at.is_(None),  # type: ignore[attr-defined]
        ).update({"revoked_at": now})
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


@dataclass
class FamilyAccessCookie:
    token: str
    public_uuid: str
    expires_at: datetime


def create_family_access_session(db: Session, *, person_id: int, public_uuid: str, max_age_seconds: int) -> str:
    # Best-effort persistence only if model exists; otherwise return opaque token.
    token = secrets.token_urlsafe(24)
    FamilyAccessSession = _get_model("FamilyAccessSession")
    if FamilyAccessSession is None:
        return token
    try:
        now = _utc_now()
        expires_at = now + timedelta(seconds=int(max_age_seconds))
        row = FamilyAccessSession(  # type: ignore[call-arg]
            person_id=person_id,
            public_uuid=str(public_uuid),
            token_sha256=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            issued_at=now,
            expires_at=expires_at,
            revoked_at=None,
        )
        db.add(row)
        db.commit()
        return token
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return token


def get_valid_family_access_session(db: Session, token: str):
    FamilyAccessSession = _get_model("FamilyAccessSession")
    if FamilyAccessSession is None or not hasattr(FamilyAccessSession, "token_sha256"):
        return None
    try:
        now = _utc_now()
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        row = (
            db.query(FamilyAccessSession)
            .filter(
                FamilyAccessSession.token_sha256 == token_hash,  # type: ignore[attr-defined]
                FamilyAccessSession.revoked_at.is_(None),  # type: ignore[attr-defined]
            )
            .first()
        )
        if not row:
            return None
        expires_at = getattr(row, "expires_at", None)
        if isinstance(expires_at, datetime) and expires_at.replace(tzinfo=timezone.utc) < now:
            return None
        return row
    except Exception:
        return None


def set_family_access_cookies(response, cookie_value: str, *, max_age_seconds: int) -> None:
    try:
        response.set_cookie(
            "tw_family_access",
            value=cookie_value,
            max_age=max_age_seconds,
            path="/",
            httponly=True,
            samesite="lax",
        )
    except Exception:
        pass


def clear_family_access_cookie(response) -> None:
    try:
        response.delete_cookie("tw_family_access", path="/")
    except Exception:
        pass


def set_totp_last_used(db: Session, person_id: int) -> None:
    Person = _get_model("Person")
    if Person is None or not hasattr(Person, "totp_last_used_at"):
        return None
    try:
        db.query(Person).filter(Person.person_id == person_id).update(  # type: ignore[attr-defined]
            {"totp_last_used_at": _utc_now()}
        )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

# from __future__ import annotations

import base64
import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import pyotp

try:
    # cryptography is present in requirements.txt in some deployments.
    from cryptography.fernet import Fernet, InvalidToken  # type: ignore
except Exception:  # pragma: no cover
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore

try:
    # Not always present in the repo's current state; keep imports optional.
    from sqlalchemy.orm import Session
except Exception:  # pragma: no cover
    Session = object  # type: ignore


# NOTE:
# This module is intentionally minimal and defensive. Its goal is to allow
# importing `app/api/routes/admin.py` without crashing even when the full
# "family access" layer is not present in the current checkout.


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _fernet() -> Fernet | None:  # type: ignore[name-defined]
    if Fernet is None:
        return None
    raw = (os.getenv("TW_FAMILY_FERNET_KEY") or "").strip()
    if not raw:
        return None
    try:
        return Fernet(raw.encode("utf-8"))
    except Exception:
        return None


def cookie_secure_flag(request) -> bool:
    """
    Best-effort secure-cookie flag: True when request indicates HTTPS.
    """
    try:
        proto = (request.headers.get("x-forwarded-proto") or "").strip().lower()
        if proto:
            return proto == "https"
        return str(getattr(request.url, "scheme", "")).lower() == "https"
    except Exception:
        return False


def generate_backup_code_plain() -> str:
    # 10 chars, uppercase + digits, readable.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(10))


def new_totp_provisioning_uri(secret: str, label: str) -> str:
    issuer = "TimeWoven"
    return pyotp.TOTP(secret).provisioning_uri(name=label, issuer_name=issuer)


def verify_totp_code(secret: str, code: str) -> bool:
    raw = (code or "").strip()
    if not raw or not raw.isdigit():
        return False
    try:
        return bool(pyotp.TOTP(secret).verify(raw, valid_window=1))
    except Exception:
        return False


def encrypt_totp_secret(secret: str) -> str:
    """
    Encrypt TOTP secret using Fernet if configured; otherwise return a deterministic obfuscated string.
    (This fallback is NOT meant as strong crypto; it's a compatibility shim.)
    """
    s = (secret or "").strip()
    if not s:
        return ""
    f = _fernet()
    if f is not None:
        token = f.encrypt(s.encode("utf-8"))
        return token.decode("utf-8")
    # Fallback: prefix + base64; reversible but avoids plaintext in DB in emergencies.
    return "b64:" + base64.b64encode(s.encode("utf-8")).decode("ascii")


def decrypt_totp_secret(encrypted: str) -> str:
    raw = (encrypted or "").strip()
    if not raw:
        return ""
    if raw.startswith("b64:"):
        try:
            return base64.b64decode(raw[4:].encode("ascii")).decode("utf-8")
        except Exception:
            return ""
    f = _fernet()
    if f is None:
        return ""
    try:
        return f.decrypt(raw.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""
    except Exception:
        return ""


def _get_model(name: str):
    try:
        import app.models as models  # local import to avoid startup coupling

        return getattr(models, name, None)
    except Exception:
        return None


def find_person_by_public_uuid(db: Session, public_uuid: str):
    """
    Best-effort lookup by `Person.public_uuid` if that column exists.
    Returns None when schema/model doesn't support it.
    """
    Person = _get_model("Person")
    if Person is None:
        return None
    if not hasattr(Person, "public_uuid"):
        return None
    u = (public_uuid or "").strip()
    if not u:
        return None
    try:
        return db.query(Person).filter(Person.public_uuid == u).first()  # type: ignore[attr-defined]
    except Exception:
        return None


def person_family_access_permitted(person) -> bool:
    """
    Access permitted when family access is enabled and not revoked.
    """
    try:
        enabled = bool(getattr(person, "family_access_enabled", False))
        revoked_at = getattr(person, "family_access_revoked_at", None)
        return enabled and not revoked_at
    except Exception:
        return False


def clear_backup_codes(db: Session, person_id: int) -> None:
    """
    No-op shim: backup codes storage isn't available in current checkout.
    """
    return None


def store_backup_codes(db: Session, person_id: int, codes: list[str]) -> None:
    """
    No-op shim: backup codes storage isn't available in current checkout.
    """
    return None


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def revoke_all_sessions_for_person(db: Session, person_id: int) -> None:
    """
    If FamilyAccessSession model exists, mark sessions revoked; otherwise no-op.
    """
    FamilyAccessSession = _get_model("FamilyAccessSession")
    if FamilyAccessSession is None:
        return None
    if not hasattr(FamilyAccessSession, "person_id") or not hasattr(FamilyAccessSession, "revoked_at"):
        return None
    try:
        now = _utc_now()
        db.query(FamilyAccessSession).filter(  # type: ignore[arg-type]
            FamilyAccessSession.person_id == person_id,  # type: ignore[attr-defined]
            FamilyAccessSession.revoked_at.is_(None),  # type: ignore[attr-defined]
        ).update({"revoked_at": now})
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


@dataclass
class FamilyAccessCookie:
    token: str
    public_uuid: str
    expires_at: datetime


def set_family_access_cookies(response, cookie_value: str, *, max_age_seconds: int) -> None:
    """
    Helper used by some family-access flows in newer branches.
    Kept here so imports won't fail if referenced.
    """
    try:
        response.set_cookie(
            "tw_family_access",
            value=cookie_value,
            max_age=max_age_seconds,
            path="/",
            httponly=True,
            samesite="lax",
        )
    except Exception:
        pass


def clear_family_access_cookie(response) -> None:
    try:
        response.delete_cookie("tw_family_access", path="/")
    except Exception:
        pass


def create_family_access_session(db: Session, *, person_id: int, public_uuid: str, max_age_seconds: int) -> str:
    """
    If FamilyAccessSession exists: create a new session row with a hashed token.
    Otherwise: return an opaque token string (not persisted).
    """
    token = secrets.token_urlsafe(24)
    FamilyAccessSession = _get_model("FamilyAccessSession")
    if FamilyAccessSession is None:
        return token
    try:
        now = _utc_now()
        expires_at = now + timedelta(seconds=int(max_age_seconds))
        row = FamilyAccessSession(  # type: ignore[call-arg]
            person_id=person_id,
            public_uuid=str(public_uuid),
            token_sha256=_hash_token(token),
            issued_at=now,
            expires_at=expires_at,
            revoked_at=None,
        )
        db.add(row)
        db.commit()
        return token
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return token


def get_valid_family_access_session(db: Session, token: str):
    """
    Best-effort validation if FamilyAccessSession exists; otherwise return None.
    """
    FamilyAccessSession = _get_model("FamilyAccessSession")
    if FamilyAccessSession is None:
        return None
    if not hasattr(FamilyAccessSession, "token_sha256"):
        return None
    try:
        now = _utc_now()
        token_hash = _hash_token(token)
        q = db.query(FamilyAccessSession).filter(  # type: ignore[arg-type]
            FamilyAccessSession.token_sha256 == token_hash,  # type: ignore[attr-defined]
            FamilyAccessSession.revoked_at.is_(None),  # type: ignore[attr-defined]
        )
        row = q.first()
        if not row:
            return None
        expires_at = getattr(row, "expires_at", None)
        if expires_at and isinstance(expires_at, datetime) and expires_at.replace(tzinfo=timezone.utc) < now:
            return None
        return row
    except Exception:
        return None


def set_totp_last_used(db: Session, person_id: int) -> None:
    Person = _get_model("Person")
    if Person is None or not hasattr(Person, "totp_last_used_at"):
        return None
    try:
        db.query(Person).filter(Person.person_id == person_id).update(  # type: ignore[attr-defined]
            {"totp_last_used_at": _utc_now()}
        )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


"""
Family TOTP + opaque session: encryption, TOTP, backup codes, rate limiting.
"""
# from __future__ import annotations

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

try:
    from app.models import FamilyAccessSession, Person, PersonAccessBackupCode  # type: ignore
except Exception:  # pragma: no cover
    FamilyAccessSession = None  # type: ignore
    Person = None  # type: ignore
    PersonAccessBackupCode = None  # type: ignore

FAMILY_ACCESS_COOKIE = "tw_family_access"
FAMILY_ACCESS_LEGACY_COOKIE = "family_member_id"

DEFAULT_SESSION_TTL = timedelta(days=7)
MAX_BODY_BYTES = 10_000

_pepper: str = os.environ.get("TW_FAMILY_ACCESS_PEPPER", "")
_fernet: Fernet | None = None

# Simple in-process rate limit: (ip, public_uuid) -> timestamps of attempts
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
        # Dev fallback — в проде обязателен TW_FAMILY_FERNET_KEY (Fernet 44-char urlsafe base64)
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
    return pyotp.totp.TOTP(secret_b32).provisioning_uri(name=person_label, issuer_name=issuer)


def verify_totp_code(secret_b32: str, code: str) -> bool:
    c = (code or "").strip().replace(" ", "")
    if not c.isdigit() or len(c) != 6:
        return False
    return bool(pyotp.TOTP(secret_b32).verify(c, valid_window=1))


def check_rate_limit(client_ip: str, public_uuid: str) -> bool:
    """Return True if request allowed, False if throttled."""
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


def cookie_secure_flag(request: Request) -> bool:
    if os.environ.get("TW_COOKIE_SECURE", "1") == "0":
        return False
    if request is not None and request.url.scheme == "https":
        return True
    return bool(os.environ.get("TW_BEHIND_HTTPS", ""))


def set_family_access_cookies(
    response, *, token: str, max_age_sec: int, request: Request
) -> None:
    secure = cookie_secure_flag(request)
    response.set_cookie(
        key=FAMILY_ACCESS_COOKIE,
        value=token,
        max_age=max_age_sec,
        path="/",
        httponly=True,
        samesite="lax",
        secure=secure,
    )


def clear_family_access_cookie(response, request: Request) -> None:
    secure = cookie_secure_flag(request)
    response.set_cookie(
        key=FAMILY_ACCESS_COOKIE,
        value="",
        max_age=0,
        path="/",
        httponly=True,
        samesite="lax",
        secure=secure,
    )


def find_person_by_public_uuid(db: Session, u: str) -> Person | None:
    s = (u or "").strip()
    if not s:
        return None
    return (
        db.query(Person)
        .filter(Person.public_uuid == s)
        .first()
    )


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


def revoke_session_token(db: Session, raw_cookie: str | None) -> bool:
    t = (raw_cookie or "").strip()
    if not t:
        return False
    h = _token_hash(t)
    now = datetime.now(timezone.utc)
    q = (
        db.query(FamilyAccessSession)
        .filter(
            FamilyAccessSession.session_token_hash == h,
            FamilyAccessSession.revoked_at.is_(None),
        )
    )
    row = q.first()
    if not row:
        return False
    row.revoked_at = now
    db.commit()
    return True


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
    # 4 блока по 4 hex = 19 символов с разделителем, без путаницы с O/0: только hex
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
