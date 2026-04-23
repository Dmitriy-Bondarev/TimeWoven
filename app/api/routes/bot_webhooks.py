import os
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
import httpx

from app.bot.max_messenger import MaxMessengerBot
from app.db.session import SessionLocal
from app.models import MaxContactEvent, Memory, Person, PersonI18n
from app.services.ai_analyzer import analyze_memory_text
from app.services.memory_store import attach_analysis_to_memory, create_memory_from_max


router = APIRouter(prefix="/webhooks/maxbot", tags=["MaxBot Webhooks"])
MAX_WEBHOOK_SECRET = os.getenv("MAX_WEBHOOK_SECRET", "").strip()
logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parents[2]
RAW_AUDIO_DIR = BASE_DIR / "web" / "static" / "audio" / "raw"


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
    RAW_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    safe_attachment_id = _sanitize_identifier(attachment_id, fallback="attachment")
    extension = _guess_audio_extension(audio_url)
    filename = f"max_{safe_attachment_id}_{timestamp}{extension}"
    target_path = RAW_AUDIO_DIR / filename

    try:
        with httpx.stream("GET", audio_url, timeout=30.0, follow_redirects=True) as response:
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

    return f"/static/audio/raw/{filename}"


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
        raw_id = payload.get("max_id") or payload.get("user_id") or payload.get("from_id")
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


def _save_max_contact_event(db, sender_max_user_id: str, contact_item: dict[str, str], raw_payload: dict) -> MaxContactEvent:
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


def _save_pending_audio_memory(
    db,
    max_id: str,
    person_id: int | None,
    audio_url: str,
    attachment_id: str,
    local_audio_path: str | None = None,
    download_error: str | None = None,
) -> Memory:
    metadata: dict[str, str] = {
        "attachment_id": attachment_id,
        "audio_url": audio_url,
        "max_user_id": max_id,
    }
    if local_audio_path:
        metadata["local_audio_path"] = local_audio_path
    if download_error:
        metadata["audio_download_error"] = download_error

    memory_json = json.dumps(metadata, ensure_ascii=False)

    memory = Memory(
        author_id=person_id,
        created_by=person_id,
        content_text="",
        audio_url=audio_url,
        transcript_verbatim=memory_json,
        source_type="max_audio_attachment",
        transcription_status="pending_manual_text",
        created_at=datetime.utcnow().isoformat(),
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


def _find_recent_pending_manual_text_memory(db, max_id: str, person_id: int | None) -> Memory | None:
    threshold = datetime.utcnow() - timedelta(minutes=3)
    query = db.query(Memory).filter(Memory.transcription_status == "pending_manual_text")
    if person_id is not None:
        query = query.filter(Memory.author_id == person_id)

    candidates = query.order_by(Memory.id.desc()).limit(20).all()
    for candidate in candidates:
        created_at = candidate.created_at or ""
        try:
            created_dt = datetime.fromisoformat(created_at)
        except ValueError:
            continue

        if created_dt < threshold:
            continue

        metadata = {}
        if candidate.transcript_verbatim:
            try:
                metadata = json.loads(candidate.transcript_verbatim)
            except json.JSONDecodeError:
                metadata = {}

        metadata_user_id = str(metadata.get("max_user_id", "")).strip()
        if metadata_user_id == max_id:
            return candidate

    return None


def _link_pending_manual_text(memory: Memory, text: str) -> None:
    memory.content_text = text
    memory.transcript_readable = text
    memory.transcription_status = "published"


@router.post("/incoming")
async def incoming_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        logger.warning("MAX webhook rejected: invalid JSON payload")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    message_payload = payload.get("message") if isinstance(payload.get("message"), dict) else {}
    message_body = message_payload.get("body") if isinstance(message_payload.get("body"), dict) else {}
    media_fragments = {
        "voice": payload.get("voice"),
        "audio": payload.get("audio"),
        "attachment": payload.get("attachment"),
        "message.attachment": message_payload.get("attachment"),
        "message.body.attachments": message_body.get("attachments"),
    }
    if any(value is not None for value in media_fragments.values()):
        logger.info("MAX webhook: media fragments detected")

    incoming_secret = request.headers.get("X-Max-Bot-Api-Secret", "").strip()
    if not MAX_WEBHOOK_SECRET or incoming_secret != MAX_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    bot = MaxMessengerBot()
    max_id = _extract_max_id(payload)
    message_text = _extract_message_text(payload)
    audio_attachment = _extract_audio_attachment(payload)
    contact_items = _extract_contact_items(payload)

    if not max_id:
        raise HTTPException(status_code=400, detail="Missing max_id or user_id/from_id in payload")
    if not message_text and not audio_attachment and not contact_items:
        raise HTTPException(status_code=400, detail="Missing text in payload")

    db = SessionLocal()
    try:
        person = _autobind_dmitry(db, max_id)
        if hasattr(Person, "max_id"):
            person = person or db.query(Person).filter_by(max_id=max_id).first()
        if not person:
            person = db.query(Person).filter_by(messenger_max_id=max_id).first()

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

        if audio_attachment and not message_text:
            local_audio_path = _download_audio_to_raw(
                audio_url=audio_attachment["audio_url"],
                attachment_id=audio_attachment["attachment_id"],
            )

            saved_memory = _save_pending_audio_memory(
                db=db,
                max_id=max_id,
                person_id=person.person_id if person else None,
                audio_url=audio_attachment["audio_url"],
                attachment_id=audio_attachment["attachment_id"],
                local_audio_path=local_audio_path,
                download_error=None if local_audio_path else "download_failed",
            )
            logger.info(
                "Saved pending audio memory %s for max_id=%s attachment_id=%s local_audio=%s",
                saved_memory.id,
                max_id,
                audio_attachment["attachment_id"],
                bool(local_audio_path),
            )
            prompt_text = "Аудио получено. Пришлите следом текст, и я привяжу его к записи."
            await bot.send_message(user_id=max_id, text=prompt_text)
            return {
                "status": "ok",
                "identified": bool(person),
                "person_id": person.person_id if person else None,
                "response_text": prompt_text,
                "memory_id": saved_memory.id,
            }

        if message_text:
            pending_memory = _find_recent_pending_manual_text_memory(
                db=db,
                max_id=max_id,
                person_id=person.person_id if person else None,
            )
            if pending_memory:
                _link_pending_manual_text(pending_memory, message_text)
                db.commit()
                confirmation_text = "Воспоминание сохранено и текст привязан к аудио!"
                await bot.send_message(user_id=max_id, text=confirmation_text)
                return {
                    "status": "ok",
                    "identified": bool(person),
                    "person_id": person.person_id if person else None,
                    "response_text": confirmation_text,
                    "memory_id": pending_memory.id,
                }

            save_result = create_memory_from_max(
                user_id=max_id,
                text=message_text,
                raw_payload=payload,
            )
            if not save_result.get("saved"):
                logger.error(
                    "MAX webhook save failed for user_id=%s: %s",
                    max_id,
                    save_result.get("error"),
                )
                raise HTTPException(status_code=500, detail="Failed to save memory")

            memory_id = save_result.get("memory_id")
            if save_result.get("transcription_status") == "archived":
                response_text = "Служебное сообщение получено и отправлено в архив."
                await bot.send_message(user_id=max_id, text=response_text)
                return {
                    "status": "ok",
                    "identified": bool(person),
                    "person_id": save_result.get("person_id"),
                    "memory_id": memory_id,
                    "analysis_status": "skipped_archived_marker",
                    "analysis_provider": "none",
                    "response_text": response_text,
                }

            analysis_result = analyze_memory_text(message_text)
            analysis_status = str(analysis_result.get("status", "unknown"))
            analysis_provider = str(analysis_result.get("raw_provider", "unknown"))

            if isinstance(memory_id, int):
                persist_analysis_result = attach_analysis_to_memory(memory_id, analysis_result)
                if not persist_analysis_result.get("saved"):
                    logger.warning(
                        "MAX webhook analysis metadata save skipped for memory_id=%s: %s",
                        memory_id,
                        persist_analysis_result.get("error"),
                    )

            logger.info(
                "MAX webhook analysis completed user_id=%s memory_id=%s provider=%s status=%s",
                max_id,
                memory_id,
                analysis_provider,
                analysis_status,
            )

            response_text = "Спасибо, я сохранил эту историю в семейный архив."
            await bot.send_message(user_id=max_id, text=response_text)
            return {
                "status": "ok",
                "identified": bool(person),
                "person_id": save_result.get("person_id"),
                "memory_id": save_result.get("memory_id"),
                "analysis_status": analysis_status,
                "analysis_provider": analysis_provider,
                "response_text": response_text,
            }

        onboarding_question = "Как мне вас называть?"
        await bot.send_message(user_id=max_id, text=onboarding_question)
        return {
            "status": "ok",
            "identified": False,
            "response_text": onboarding_question,
        }
    finally:
        db.close()
