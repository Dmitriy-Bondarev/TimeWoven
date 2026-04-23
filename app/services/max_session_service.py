"""Service layer for Max chat session management (T18.B).

A session groups messages from one max_user_id into a draft until
the user sends a finalize command.  On finalize the draft is assembled
into a Memory (transcription_status='draft') and optionally analyzed
by the configured AI provider.  If AI is unavailable the Memory is
still created — the service never raises outward exceptions.
"""

import json
import logging
from datetime import datetime
from typing import Any

from app.models import MaxChatSession, Memory
from app.services.ai_analyzer import analyze_memory_text

logger = logging.getLogger(__name__)

# Commands (case-insensitive) that trigger session finalization
FINALIZE_COMMANDS: frozenset[str] = frozenset(
    {
        "готово",
        "завершить",
        "это всё",
        "это все",
        "закончить",
        "стоп",
        "end",
        "done",
        "finish",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_finalize_command(text: str) -> bool:
    """Return True if *text* is a recognized session-finalize command."""
    return (text or "").strip().lower() in FINALIZE_COMMANDS


def _load_items(session: MaxChatSession) -> list[dict]:
    if not session.draft_items:
        return []
    try:
        items = json.loads(session.draft_items)
        return items if isinstance(items, list) else []
    except (json.JSONDecodeError, ValueError):
        return []


def _rebuild_draft_text(items: list[dict]) -> str | None:
    """Concatenate text + transcribed voice fragments into one draft string."""
    parts: list[str] = []
    for item in items:
        if item.get("type") == "text" and item.get("text"):
            parts.append(str(item["text"]))
            continue

        # Include successful voice transcripts in the aggregated draft.
        if item.get("type") == "audio":
            voice_text = str(item.get("transcription_text") or "").strip()
            status = str(item.get("transcription_status") or "")
            if voice_text and status == "ok":
                parts.append(f"[voice] {voice_text}")

    return "\n".join(parts) if parts else None


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

def get_open_session(db, max_user_id: str) -> MaxChatSession | None:
    """Return the most-recent open session for *max_user_id*, or None."""
    return (
        db.query(MaxChatSession)
        .filter(
            MaxChatSession.max_user_id == max_user_id,
            MaxChatSession.status == "open",
        )
        .order_by(MaxChatSession.id.desc())
        .first()
    )


def create_session(db, max_user_id: str, person_id: int | None) -> MaxChatSession:
    """Create and persist a new open session."""
    now = datetime.utcnow().isoformat()
    session = MaxChatSession(
        max_user_id=max_user_id,
        person_id=person_id,
        status="open",
        created_at=now,
        updated_at=now,
        draft_text=None,
        draft_items=json.dumps([]),
        message_count=0,
        audio_count=0,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info("Created max_chat_session id=%s for max_user_id=%s", session.id, max_user_id)
    return session


def get_or_create_open_session(
    db, max_user_id: str, person_id: int | None
) -> MaxChatSession:
    """Return existing open session or create a fresh one.

    If an existing session has no person_id but one is now known, backfill it.
    """
    session = get_open_session(db, max_user_id)
    if session is None:
        return create_session(db, max_user_id, person_id)
    if person_id is not None and session.person_id is None:
        session.person_id = person_id
        session.updated_at = datetime.utcnow().isoformat()
        db.commit()
        db.refresh(session)
    return session


# ---------------------------------------------------------------------------
# Draft item writers
# ---------------------------------------------------------------------------

def add_text_item(db, session: MaxChatSession, text: str, raw_payload: dict) -> None:
    """Append a text message to the session draft."""
    items = _load_items(session)
    items.append(
        {
            "type": "text",
            "text": text,
            "ts": datetime.utcnow().isoformat(),
            "raw_payload": raw_payload,
        }
    )
    session.draft_text = _rebuild_draft_text(items)
    session.message_count = (session.message_count or 0) + 1
    session.draft_items = json.dumps(items, ensure_ascii=False)
    session.updated_at = datetime.utcnow().isoformat()
    db.commit()
    db.refresh(session)
    logger.info(
        "Text item added to session id=%s message_count=%s",
        session.id,
        session.message_count,
    )


def add_audio_item(
    db,
    session: MaxChatSession,
    audio_url: str,
    local_path: str | None,
    attachment_id: str,
    raw_payload: dict,
    transcription_text: str | None = None,
    transcription_status: str = "pending",
    transcribed_at: str | None = None,
    transcription_error: str | None = None,
) -> None:
    """Append an audio attachment record to the session draft.

    Both the original CDN URL and the local filesystem path are stored so
    the audio remains accessible even if the CDN URL expires.
    """
    items = _load_items(session)
    voice_text = str(transcription_text or "").strip() if transcription_text else None
    transcribed_at_value = transcribed_at or datetime.utcnow().isoformat()
    items.append(
        {
            "type": "audio",
            "audio_url": audio_url,
            "local_path": local_path,
            "attachment_id": attachment_id,
            "transcription_text": voice_text,
            "transcription_status": transcription_status,
            "transcribed_at": transcribed_at_value,
            "transcription_error": transcription_error,
            "ts": datetime.utcnow().isoformat(),
            "raw_payload": raw_payload,
        }
    )
    session.audio_count = (session.audio_count or 0) + 1
    session.draft_text = _rebuild_draft_text(items)
    session.draft_items = json.dumps(items, ensure_ascii=False)
    session.updated_at = datetime.utcnow().isoformat()
    db.commit()
    db.refresh(session)
    logger.info(
        "Audio item added to session id=%s attachment_id=%s local_path=%s audio_count=%s",
        session.id,
        attachment_id,
        local_path,
        session.audio_count,
    )


# ---------------------------------------------------------------------------
# Finalize
# ---------------------------------------------------------------------------

def finalize_session(db, session: MaxChatSession) -> Memory | None:
    """Finalize an open session: create a draft Memory, run AI analysis, return Memory.

    Guarantees:
    - Always creates the Memory even if AI analysis fails.
    - Never raises an outward exception.
    - Sets session.status = 'finalized' and links session.memory_id.
    """
    if session.status != "open":
        logger.warning(
            "finalize_session called on non-open session id=%s status=%s",
            session.id,
            session.status,
        )
        return None

    items = _load_items(session)
    draft_text = session.draft_text or ""

    # Collect first audio URL + local path from items
    first_audio_url: str | None = None
    first_local_path: str | None = None
    for item in items:
        if item.get("type") == "audio":
            first_audio_url = item.get("audio_url") or None
            first_local_path = item.get("local_path") or None
            break

    now = datetime.utcnow().isoformat()

    metadata: dict[str, Any] = {
        "source": "max_session",
        "session_id": session.id,
        "max_user_id": session.max_user_id,
        "message_count": session.message_count,
        "audio_count": session.audio_count,
        "finalized_at": now,
        "draft_items_count": len(items),
        "draft_items": items,
    }
    if first_audio_url:
        metadata["audio_url"] = first_audio_url
    if first_local_path:
        metadata["local_audio_path"] = first_local_path

    # AI analysis with fallback — never let it crash finalization
    analysis_status = "skipped"
    if draft_text.strip():
        try:
            analysis = analyze_memory_text(draft_text)
            analysis_status = str(analysis.get("status", "unknown"))
            metadata["analysis"] = analysis
        except Exception as exc:
            logger.error(
                "AI analysis failed during finalize session_id=%s: %s",
                session.id,
                exc,
            )
            analysis_status = "error"
            metadata["analysis"] = {"status": "error", "error": str(exc)}
    else:
        metadata["analysis"] = {"status": "skipped", "reason": "no_text_draft"}

    metadata_json = json.dumps(metadata, ensure_ascii=False)

    try:
        memory = Memory(
            author_id=session.person_id,
            created_by=session.person_id,
            content_text=draft_text,
            audio_url=first_audio_url,
            transcript_verbatim=metadata_json,
            transcript_readable=draft_text,
            source_type="max_session",
            transcription_status="draft",
            is_archived=False,
            created_at=now,
        )
        db.add(memory)
        db.flush()  # assign memory.id without committing yet

        session.status = "finalized"
        session.finalized_at = now
        session.updated_at = now
        session.memory_id = memory.id
        session.analysis_status = analysis_status
        db.commit()
        db.refresh(memory)
        db.refresh(session)

        logger.info(
            "Finalized session id=%s memory_id=%s analysis_status=%s",
            session.id,
            memory.id,
            analysis_status,
        )
        return memory

    except Exception as exc:
        db.rollback()
        logger.error("Failed to persist finalized session id=%s: %s", session.id, exc)
        return None
