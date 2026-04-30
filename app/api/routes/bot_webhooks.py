import json
import logging
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.bot.max_messenger import MaxMessengerBot
from app.core.media_urls import default_family_slug, family_data_path_for_slug
from app.db.session import SessionLocal
from app.models import MaxContactEvent, Person, PersonI18n
from app.services import bot_reply, max_session_service
from app.services.transcription import TranscriptionService

router = APIRouter(prefix="/webhooks/maxbot", tags=["MaxBot Webhooks"])
MAX_WEBHOOK_SECRET = os.getenv("MAX_WEBHOOK_SECRET", "").strip()
logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parents[2]


def _raw_audio_dir() -> Path:
    slug = default_family_slug()
    data_path = Path(family_data_path_for_slug(slug))
    return data_path / "media" / "audio" / "raw"


def _sanitize_identifier(raw_value: str, fallback: str = "audio") -> str:
    cleaned = "".join(ch for ch in str(raw_value) if ch.isalnum() or ch in ("-", "_"))
    return cleaned[:80] if cleaned else fallback


def _guess_audio_extension(audio_url: str) -> str:
    try:
        parsed = urlparse(audio_url)
        suffix = Path(parsed.path).suffix.lower()
    except Exception:
        suffix = ""
    if suffix and len(suffix) <= 8:
        return suffix
    return ".ogg"


def _download_audio_to_raw(audio_url: str, attachment_id: str) -> str | None:
    raw_dir = _raw_audio_dir()
    raw_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_attachment_id = _sanitize_identifier(attachment_id, fallback="attachment")
    extension = _guess_audio_extension(audio_url)
    filename = f"max_{safe_attachment_id}_{timestamp}{extension}"
    target_path = raw_dir / filename

    try:
        with httpx.stream(
            "GET", audio_url, timeout=30.0, follow_redirects=True
        ) as response:
            response.raise_for_status()
            with target_path.open("wb") as file_handle:
                for chunk in response.iter_bytes(chunk_size=8192):
                    if chunk:
                        file_handle.write(chunk)
    except Exception as exc:
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        logger.warning(
            "Failed to download MAX audio attachment_id=%s from url=%s: %s",
            attachment_id,
            audio_url,
            exc,
        )
        return None

    slug = default_family_slug()
    return f"/media/{slug}/audio/raw/{filename}"


def _extract_max_id(payload: dict) -> str:
    raw_id = None

    message = payload.get("message")
    if isinstance(message, dict):
        sender_data = message.get("sender")
        if isinstance(sender_data, dict):
            raw_id = sender_data.get("user_id")

        if raw_id is None:
            from_data = message.get("from")
            if isinstance(from_data, dict):
                raw_id = from_data.get("id")

    if raw_id is None:
        bot_started = payload.get("bot_started")
        if isinstance(bot_started, dict):
            from_data = bot_started.get("from")
            if isinstance(from_data, dict):
                raw_id = from_data.get("id")

    if raw_id is None:
        raw_id = (
            payload.get("max_id") or payload.get("user_id") or payload.get("from_id")
        )
    if raw_id is None and isinstance(payload.get("from"), dict):
        raw_id = payload["from"].get("id")
    return str(raw_id).strip() if raw_id is not None else ""


def _extract_message_text(payload: dict) -> str:
    message = payload.get("message")
    if not isinstance(message, dict):
        return ""

    body = message.get("body")
    if isinstance(body, dict):
        text = body.get("text")
        if isinstance(text, str):
            return text.strip()

    text = message.get("text")
    if isinstance(text, str):
        return text.strip()

    return ""


def _autobind_dmitry(db, max_id: str):
    if max_id != "4471252":
        return None

    person = (
        db.query(Person)
        .join(PersonI18n, PersonI18n.person_id == Person.person_id)
        .filter(
            PersonI18n.lang_code == "ru",
            PersonI18n.first_name.ilike("дмитрий"),
            PersonI18n.last_name.ilike("бондарев"),
        )
        .first()
    )
    if not person:
        person = (
            db.query(Person)
            .join(PersonI18n, PersonI18n.person_id == Person.person_id)
            .filter(
                PersonI18n.lang_code == "ru",
                PersonI18n.first_name.ilike("дмитрий"),
            )
            .first()
        )

    if not person:
        return None

    if not person.messenger_max_id:
        person.messenger_max_id = max_id
        db.commit()
        db.refresh(person)

    return person


def _resolve_person_name(db, person: Person) -> str:
    i18n = (
        db.query(PersonI18n)
        .filter(
            PersonI18n.person_id == person.person_id,
            PersonI18n.lang_code == "ru",
        )
        .first()
    )
    if i18n and i18n.first_name:
        return i18n.first_name
    return f"Персона #{person.person_id}"


def _extract_audio_url(payload: dict) -> str:
    voice = payload.get("voice")
    if isinstance(voice, str) and voice.strip():
        return voice.strip()
    if isinstance(voice, dict):
        for key in ("url", "audio_url", "file_url"):
            value = voice.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    audio = payload.get("audio")
    if isinstance(audio, str) and audio.strip():
        return audio.strip()
    if isinstance(audio, dict):
        for key in ("url", "audio_url", "file_url"):
            value = audio.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    attachment = payload.get("attachment")
    attachments = attachment if isinstance(attachment, list) else [attachment]
    for item in attachments:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type", "")).lower()
        if item_type != "audio":
            continue
        for key in ("url", "audio_url", "file_url"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return ""


def _extract_audio_attachment(payload: dict) -> dict[str, str] | None:
    message = payload.get("message")
    if not isinstance(message, dict):
        return None

    body = message.get("body")
    if not isinstance(body, dict):
        return None

    attachments = body.get("attachments")
    if not isinstance(attachments, list):
        return None

    for item in attachments:
        if not isinstance(item, dict):
            continue
        if str(item.get("type", "")).lower() != "audio":
            continue

        payload_data = item.get("payload")
        if not isinstance(payload_data, dict):
            continue

        audio_url = payload_data.get("url")
        attachment_id = payload_data.get("id")
        if not audio_url or attachment_id is None:
            continue

        return {
            "audio_url": str(audio_url).strip(),
            "attachment_id": str(attachment_id).strip(),
        }

    return None


def _extract_contact_items(payload: dict) -> list[dict[str, str]]:
    message = payload.get("message")
    if not isinstance(message, dict):
        return []

    body = message.get("body")
    if not isinstance(body, dict):
        return []

    attachments = body.get("attachments")
    if not isinstance(attachments, list):
        return []

    contacts: list[dict[str, str]] = []
    for item in attachments:
        if not isinstance(item, dict):
            continue
        if str(item.get("type", "")).lower() != "contact":
            continue

        payload_data = item.get("payload")
        if not isinstance(payload_data, dict):
            continue
        max_info = payload_data.get("max_info")
        if not isinstance(max_info, dict):
            continue

        contact_user_id = max_info.get("user_id")
        first_name = max_info.get("first_name")
        if contact_user_id is None:
            continue

        contacts.append(
            {
                "user_id": str(contact_user_id).strip(),
                "first_name": str(first_name).strip() if first_name is not None else "",
                "last_name": str(max_info.get("last_name") or "").strip(),
                "name": str(max_info.get("name") or "").strip(),
            }
        )

    return contacts


def _save_max_contact_event(
    db, sender_max_user_id: str, contact_item: dict[str, str], raw_payload: dict
) -> MaxContactEvent:
    event = MaxContactEvent(
        created_at=datetime.utcnow().isoformat(),
        sender_max_user_id=sender_max_user_id,
        contact_max_user_id=contact_item.get("user_id") or None,
        contact_name=contact_item.get("name") or None,
        contact_first_name=contact_item.get("first_name") or None,
        contact_last_name=contact_item.get("last_name") or None,
        raw_payload=json.dumps(raw_payload, ensure_ascii=False, separators=(",", ":")),
        status="new",
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _to_filesystem_audio_path(local_static_path: str) -> str:
    """
    Legacy helper.

    Kept for backward-compat: convert previously stored static raw-audio links to
    an absolute filesystem path inside the repo. New flow writes to /media/.
    """
    normalized = local_static_path.strip()
    return str(BASE_DIR / "web" / normalized.lstrip("/"))


@router.post("/incoming")
async def incoming_webhook(request: Request):
    # --- Parse ---
    try:
        payload = await request.json()
    except Exception:
        logger.warning("MAX webhook rejected: invalid JSON payload")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # --- Auth ---
    incoming_secret = request.headers.get("X-Max-Bot-Api-Secret", "").strip()
    if not MAX_WEBHOOK_SECRET or incoming_secret != MAX_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    bot = MaxMessengerBot()
    transcriber = TranscriptionService()
    max_id = _extract_max_id(payload)
    message_text = _extract_message_text(payload)
    audio_attachment = _extract_audio_attachment(payload)
    contact_items = _extract_contact_items(payload)

    if not max_id:
        raise HTTPException(
            status_code=400, detail="Missing max_id or user_id/from_id in payload"
        )
    if not message_text and not audio_attachment and not contact_items:
        raise HTTPException(status_code=400, detail="No processable content in payload")

    db = SessionLocal()
    try:
        # Resolve person
        person = _autobind_dmitry(db, max_id)
        if not person:
            person = db.query(Person).filter_by(messenger_max_id=max_id).first()
        person_id = person.person_id if person else None

        # --- Contacts: save MaxContactEvent (unchanged from T16) ---
        if contact_items:
            for contact in contact_items:
                event = _save_max_contact_event(
                    db=db,
                    sender_max_user_id=max_id,
                    contact_item=contact,
                    raw_payload=payload,
                )
                logger.info(
                    "MAX contact event stored sender=%s contact=%s event_id=%s",
                    max_id,
                    contact["user_id"],
                    event.id,
                )
            # If contacts-only (no text/audio) — ACK and return
            if not message_text and not audio_attachment:
                response_text = "Контакт получен."
                await bot.send_message(user_id=max_id, text=response_text)
                return {
                    "status": "ok",
                    "identified": bool(person),
                    "response_text": response_text,
                }

        # --- Finalize command ---
        if message_text and max_session_service.is_finalize_command(message_text):
            session = max_session_service.get_open_session(db, max_id)
            if not session or (not session.draft_text and not session.audio_count):
                response_text = "Нет активной записи для завершения."
                await bot.send_message(user_id=max_id, text=response_text)
                return {
                    "status": "ok",
                    "identified": bool(person),
                    "response_text": response_text,
                }

            memory = max_session_service.finalize_session(db, session)
            if memory:
                response_text = bot_reply.build_ack_for_finalize(
                    memory=memory,
                    session=session,
                    analysis=None,
                )
            else:
                response_text = (
                    "Сессия завершена (ошибка сохранения, обратитесь к администратору)."
                )

            await bot.send_message(user_id=max_id, text=response_text)
            return {
                "status": "ok",
                "identified": bool(person),
                "session_id": session.id,
                "memory_id": memory.id if memory else None,
                "analysis_status": session.analysis_status,
                "response_text": response_text,
            }

        # --- Audio: guaranteed local download + optional auto-transcription ---
        if audio_attachment:
            local_audio_path = _download_audio_to_raw(
                audio_url=audio_attachment["audio_url"],
                attachment_id=audio_attachment["attachment_id"],
            )

            transcription_text: str | None = None
            transcription_status = "pending"
            transcription_error: str | None = None
            transcribed_at = datetime.utcnow().isoformat()

            if local_audio_path:
                fs_audio_path = _to_filesystem_audio_path(local_audio_path)
                try:
                    transcription_text = transcriber.transcribe_file(fs_audio_path)
                    if transcription_text:
                        transcription_status = "ok"
                    else:
                        transcription_status = "error"
                        transcription_error = "empty transcription result"
                except Exception as exc:
                    transcription_status = "error"
                    transcription_error = str(exc)
                    logger.warning(
                        "MAX transcription failed max_id=%s attachment_id=%s: %s",
                        max_id,
                        audio_attachment["attachment_id"],
                        exc,
                    )
            else:
                transcription_status = "error"
                transcription_error = "audio_download_failed"
                logger.warning(
                    "MAX audio download failed for max_id=%s attachment_id=%s — CDN URL stored only",
                    max_id,
                    audio_attachment["attachment_id"],
                )

            session = max_session_service.get_or_create_open_session(
                db, max_id, person_id
            )
            max_session_service.add_audio_item(
                db=db,
                session=session,
                audio_url=audio_attachment["audio_url"],
                local_path=local_audio_path,
                attachment_id=audio_attachment["attachment_id"],
                raw_payload=payload,
                transcription_text=transcription_text,
                transcription_status=transcription_status,
                transcribed_at=transcribed_at,
                transcription_error=transcription_error,
            )

            # If the audio message also carries text, add it to the same session
            if message_text:
                max_session_service.add_text_item(
                    db=db, session=session, text=message_text, raw_payload=payload
                )

            audio_item = {
                "audio_url": audio_attachment["audio_url"],
                "local_path": local_audio_path,
                "transcription_text": transcription_text,
                "transcription_status": transcription_status,
                "transcribed_at": transcribed_at,
                "transcription_error": transcription_error,
            }
            response_text = bot_reply.build_ack_for_audio(
                session=session,
                audio_item=audio_item,
                transcription_result={
                    "status": transcription_status,
                    "text": transcription_text,
                    "error": transcription_error,
                },
            )

            await bot.send_message(user_id=max_id, text=response_text)
            return {
                "status": "ok",
                "identified": bool(person),
                "session_id": session.id,
                "audio_local": bool(local_audio_path),
                "audio_count": session.audio_count,
                "transcription_status": transcription_status,
                "transcription_error": transcription_error,
                "transcription_text": transcription_text,
                "response_text": response_text,
            }

        # --- Text message: add to session draft ---
        if message_text:
            session = max_session_service.get_or_create_open_session(
                db, max_id, person_id
            )
            max_session_service.add_text_item(
                db=db, session=session, text=message_text, raw_payload=payload
            )
            logger.info(
                "MAX text added to session id=%s max_id=%s message_count=%s",
                session.id,
                max_id,
                session.message_count,
            )
            if (session.message_count or 0) == 1:
                response_text = bot_reply.build_ack_for_new_session(
                    text=message_text,
                    session=session,
                    analysis=None,
                )
            else:
                response_text = (
                    "Принято. Продолжайте или напишите «Готово» для сохранения."
                )
            await bot.send_message(user_id=max_id, text=response_text)
            return {
                "status": "ok",
                "identified": bool(person),
                "session_id": session.id,
                "message_count": session.message_count,
                "response_text": response_text,
            }

        # Should not reach here given the guards above
        raise HTTPException(status_code=400, detail="No processable content in payload")
    finally:
        db.close()
