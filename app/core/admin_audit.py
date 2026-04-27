from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

_LOG_DIR = Path(os.getenv("TW_LOG_DIR", "logs"))
_LOG_FILE = _LOG_DIR / "admin_audit.log"


def log_login_attempt(
    ip: str,
    username: str,
    result: Literal["success", "fail", "rate_limited"],
) -> None:
    """Append one JSON record to admin audit log. Never raises."""
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "admin_login_attempt",
            "ip": ip or "unknown",
            "username": (username or "")[:64],
            "result": result,
        }
        with _LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass

