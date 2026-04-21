import os
import logging
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func

from app.bot.max_messenger import MaxMessengerBot
from app.db.session import SessionLocal
from app.models import Memory, Person, PersonI18n


router = APIRouter(prefix="/webhooks/maxbot", tags=["MaxBot Webhooks"])
MAX_WEBHOOK_SECRET = os.getenv("MAX_WEBHOOK_SECRET", "").strip()
logger = logging.getLogger(__name__)


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
        if contact_user_id is None or not first_name:
            continue

        contacts.append(
            {
                "user_id": str(contact_user_id).strip(),
                "first_name": str(first_name).strip(),
            }
        )

    return contacts


def _link_or_create_person_by_contact(db, user_id: str, first_name: str) -> Person:
    person = db.query(Person).filter(Person.messenger_max_id == user_id).first()
    if person:
        return person

    next_person_id = (db.query(func.max(Person.person_id)).scalar() or 0) + 1

    person = Person(
        person_id=next_person_id,
        is_alive=1,
        role="member",
        messenger_max_id=user_id,
        default_lang="ru",
        is_user=1,
    )
    db.add(person)
    db.flush()

    person_i18n = PersonI18n(
        person_id=person.person_id,
        lang_code="ru",
        first_name=first_name,
        last_name="",
    )
    db.add(person_i18n)
    db.commit()
    db.refresh(person)
    return person


def _save_pending_audio_memory(db, max_id: str, person_id: int | None, audio_url: str, attachment_id: str) -> Memory:
    memory = Memory(
        author_id=person_id,
        created_by=person_id,
        content_text="",
        audio_url=audio_url,
        transcript_verbatim=json.dumps(
            {
                "attachment_id": attachment_id,
                "audio_url": audio_url,
                "max_user_id": max_id,
            },
            ensure_ascii=False,
        ),
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
    raw_body = await request.body()
    with open("webhook_test.log", "a") as f:
        f.write(f"Received raw body: {raw_body.decode('utf-8', errors='replace')}\n")

    try:
        payload = await request.json()
    except Exception as error:
        error_message = f"Error processing webhook: {error}"
        logger.exception(error_message)
        with open("webhook_test.log", "a") as f:
            f.write(f"{error_message}\n")
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
        with open("webhook_test.log", "a") as f:
            f.write("MEDIA_DETECTED: ")
            f.write(json.dumps(media_fragments, ensure_ascii=False))
            f.write("\n")

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

    db = SessionLocal()
    try:
        person = _autobind_dmitry(db, max_id)
        if hasattr(Person, "max_id"):
            person = person or db.query(Person).filter_by(max_id=max_id).first()
        if not person:
            person = db.query(Person).filter_by(messenger_max_id=max_id).first()

        if contact_items:
            for contact in contact_items:
                linked_person = _link_or_create_person_by_contact(
                    db=db,
                    user_id=contact["user_id"],
                    first_name=contact["first_name"],
                )
                logger.info(
                    "PERSON_LINKED: %s ID: %s (person_id=%s)",
                    contact["first_name"],
                    contact["user_id"],
                    linked_person.person_id,
                )
                with open("webhook_test.log", "a") as f:
                    f.write(
                        f"PERSON_LINKED: {contact['first_name']} ID: {contact['user_id']} "
                        f"(person_id={linked_person.person_id})\n"
                    )

        if audio_attachment:
            saved_memory = _save_pending_audio_memory(
                db=db,
                max_id=max_id,
                person_id=person.person_id if person else None,
                audio_url=audio_attachment["audio_url"],
                attachment_id=audio_attachment["attachment_id"],
            )
            logger.info(
                "Saved pending audio memory %s for max_id=%s attachment_id=%s",
                saved_memory.id,
                max_id,
                audio_attachment["attachment_id"],
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

        if person:
            person_name = _resolve_person_name(db, person)
            logger.info("User %s identified. Text: %s", person_name, message_text)
            greeting = f"Привет, {person_name}! Я тебя узнал."
            await bot.send_message(user_id=max_id, text=greeting)
            return {
                "status": "ok",
                "identified": True,
                "person_id": person.person_id,
                "response_text": greeting,
            }

        logger.info("Unknown user with max_id: %s. Text: %s", max_id, message_text)
        onboarding_question = "Как мне вас называть?"
        await bot.send_message(user_id=max_id, text=onboarding_question)
        return {
            "status": "ok",
            "identified": False,
            "response_text": onboarding_question,
        }
    finally:
        db.close()
