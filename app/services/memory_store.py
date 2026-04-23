from datetime import datetime
import json

from sqlalchemy import or_

from app.db.session import SessionLocal
from app.models import Memory, Person


def _is_test_contact_marker(text: str) -> bool:
    return "test contact" in (text or "").strip().lower()


def _resolve_person_id_by_messenger(db, user_id: str) -> int | None:
    person = (
        db.query(Person)
        .filter(
            or_(
                Person.messenger_max_id == user_id,
                Person.messenger_tg_id == user_id,
            )
        )
        .first()
    )
    return person.person_id if person else None


def create_memory_from_max(user_id: str, text: str, raw_payload: dict | None = None) -> dict:
    """Save one incoming MAX text message as a Memory row.

    This is a minimal transport+persistence function for webhook ingestion.
    """
    normalized_user_id = str(user_id or "").strip()
    normalized_text = str(text or "").strip()
    is_contact_marker = _is_test_contact_marker(normalized_text)
    if not normalized_user_id:
        return {"saved": False, "error": "user_id is required"}
    if not normalized_text:
        return {"saved": False, "error": "text is required"}

    db = SessionLocal()
    try:
        resolved_person_id = _resolve_person_id_by_messenger(db, normalized_user_id)
        message_id = None
        if isinstance(raw_payload, dict):
            message = raw_payload.get("message")
            if isinstance(message, dict):
                message_id = message.get("id") or message.get("message_id")

        external_id = str(message_id).strip() if message_id is not None else normalized_user_id
        metadata = {
            "transport": "max_messenger",
            "external_id": external_id,
            "max_user_id": normalized_user_id,
            "raw_payload": raw_payload if isinstance(raw_payload, dict) else {},
        }
        memory_json = json.dumps(metadata, ensure_ascii=False)

        memory_source_type = "max_contact_test_marker" if is_contact_marker else "max_messenger"
        memory_status = "archived" if is_contact_marker else "published"

        memory = Memory(
            author_id=resolved_person_id,
            content_text=normalized_text,
            transcript_verbatim=memory_json,
            transcript_readable=normalized_text,
            source_type=memory_source_type,
            transcription_status=memory_status,
            is_archived=is_contact_marker,
            created_at=datetime.utcnow().isoformat(),
        )

        db.add(memory)
        db.commit()
        db.refresh(memory)

        return {
            "saved": True,
            "memory_id": memory.id,
            "person_id": resolved_person_id,
            "external_id": external_id,
            "source": memory_source_type,
            "transcription_status": memory_status,
            "is_archived": bool(memory.is_archived),
        }
    except Exception as exc:
        db.rollback()
        return {
            "saved": False,
            "error": str(exc),
        }
    finally:
        db.close()


def attach_analysis_to_memory(memory_id: int, analysis_result: dict | None) -> dict:
    """Persist AI analysis into transcript metadata for an existing memory."""
    if not memory_id:
        return {"saved": False, "error": "memory_id is required"}

    db = SessionLocal()
    try:
        memory = db.query(Memory).filter(Memory.id == memory_id).first()
        if not memory:
            return {"saved": False, "error": "memory not found"}

        metadata = {}
        if memory.transcript_verbatim:
            try:
                decoded = json.loads(memory.transcript_verbatim)
                if isinstance(decoded, dict):
                    metadata = decoded
            except json.JSONDecodeError:
                metadata = {"raw_transcript_verbatim": memory.transcript_verbatim}

        metadata["analysis"] = analysis_result if isinstance(analysis_result, dict) else {}
        memory.transcript_verbatim = json.dumps(metadata, ensure_ascii=False)
        db.commit()

        return {"saved": True, "memory_id": memory.id}
    except Exception as exc:
        db.rollback()
        return {"saved": False, "error": str(exc)}
    finally:
        db.close()


async def save_raw_memory(user_id: str, text: str, audio_url: str = None, person_id: int | None = None) -> dict:
    """Persist incoming memory text (and optional audio url) into Memories."""
    db = SessionLocal()
    try:
        resolved_person_id = person_id
        if resolved_person_id is None:
            resolved_person_id = _resolve_person_id_by_messenger(db, user_id)

        # TODO: when "new profile" onboarding step is implemented, use created person_id here.

        normalized_text = str(text or "").strip()
        is_contact_marker = _is_test_contact_marker(normalized_text)

        memory = Memory(
            author_id=resolved_person_id,
            content_text=normalized_text,
            audio_url=audio_url,
            transcript_verbatim=normalized_text,
            transcript_readable=normalized_text,
            source_type="max_contact_test_marker" if is_contact_marker else "max_bot",
            transcription_status="archived" if is_contact_marker else "published",
            is_archived=is_contact_marker,
            created_at=datetime.utcnow().isoformat(),
        )

        db.add(memory)
        db.commit()
        db.refresh(memory)

        return {
            "saved": True,
            "memory_id": memory.id,
            "person_id": resolved_person_id,
            "transcription_status": memory.transcription_status,
            "is_archived": bool(memory.is_archived),
        }
    except Exception as exc:
        db.rollback()
        return {
            "saved": False,
            "error": str(exc),
        }
    finally:
        db.close()


def has_memory_today(person_id: int) -> bool:
    """Check whether a person has at least one memory created today."""
    db = SessionLocal()
    try:
        today_prefix = datetime.utcnow().date().isoformat()
        memory = (
            db.query(Memory)
            .filter(
                Memory.author_id == person_id,
                Memory.created_at.like(f"{today_prefix}%"),
            )
            .first()
        )
        return memory is not None
    finally:
        db.close()
