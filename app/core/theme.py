import json

from sqlalchemy.orm import Session

from app.models import BotSession


THEME_PRESETS: tuple[str, ...] = ("current_dark", "voice_premium")
DEFAULT_THEME_PRESET = "current_dark"

# Sentinel row in bot_sessions used as a tiny app-settings store
# (avoids a dedicated app_settings table / schema change).
_SETTINGS_ROW_ID = "__app_settings__"
_SETTINGS_JSON_KEY = "active_theme_preset"


def normalize_theme_preset(value: object) -> str:
    v = str(value or "").strip()
    if v in THEME_PRESETS:
        return v
    return DEFAULT_THEME_PRESET


def get_active_theme_preset(db: Session) -> str:
    row = (
        db.query(BotSession)
        .filter(BotSession.user_id == _SETTINGS_ROW_ID)
        .first()
    )
    if not row or not (row.data_json or "").strip():
        return DEFAULT_THEME_PRESET
    try:
        payload = json.loads(row.data_json)
    except Exception:
        return DEFAULT_THEME_PRESET
    if not isinstance(payload, dict):
        return DEFAULT_THEME_PRESET
    return normalize_theme_preset(payload.get(_SETTINGS_JSON_KEY))


def set_active_theme_preset(db: Session, preset: str) -> str:
    normalized = normalize_theme_preset(preset)
    row = (
        db.query(BotSession)
        .filter(BotSession.user_id == _SETTINGS_ROW_ID)
        .first()
    )
    payload: dict = {}
    if row and (row.data_json or "").strip():
        try:
            cand = json.loads(row.data_json)
            if isinstance(cand, dict):
                payload = cand
        except Exception:
            payload = {}
    payload[_SETTINGS_JSON_KEY] = normalized
    if not row:
        row = BotSession(
            user_id=_SETTINGS_ROW_ID,
            current_step="app_settings",
            data_json=json.dumps(payload),
        )
        db.add(row)
    else:
        row.current_step = "app_settings"
        row.data_json = json.dumps(payload)
    db.commit()
    return normalized