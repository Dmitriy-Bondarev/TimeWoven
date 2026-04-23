import logging
import os
import re
import tempfile
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import and_

from app.db.session import SessionLocal
from app.models import BotSession, Person, PersonI18n
from app.services.ai_analyzer import MemoryAnalyzer
from app.services.daily_impulses import get_random_impulse
from app.services.memory_store import save_raw_memory
from app.services.transcription import TranscriptionService


logger = logging.getLogger(__name__)


class MaxMessengerBot:
    """Minimal async scaffold for Max Messenger webhook integration."""

    def __init__(self) -> None:
        self.bot_id = os.getenv("MAX_BOT_ID", "unknown")
        self.integration_status = os.getenv("MAX_BOT_STATUS", "planned")
        self.api_token = os.getenv("MAX_BOT_TOKEN", "").strip()
        self.send_url = os.getenv("MAX_API_SEND_URL", "https://platform-api.max.ru/messages").strip()
        self.analyzer = MemoryAnalyzer()
        self.transcriber = TranscriptionService()

        logger.info(
            "MaxMessengerBot scaffold initialized: bot_id=%s, status=%s",
            self.bot_id,
            self.integration_status,
        )

    async def send_message(self, user_id: str, text: str) -> dict[str, Any]:
        """Send outgoing message to MAX Messenger API."""
        if not self.api_token:
            logger.warning("MAX_BOT_TOKEN is not set; outgoing message was skipped")
            return {"sent": False, "reason": "MAX_BOT_TOKEN is not set"}

        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            return {"sent": False, "reason": "user_id is required"}

        send_url = self.send_url
        headers = {
            "Authorization": self.api_token,
            "Content-Type": "application/json",
        }
        payload = {
            "chat_id": normalized_user_id,
            "text": text,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(send_url, json=payload, headers=headers)
                logger.info("MAX API Response: %s %s", response.status_code, response.text)
                if response.is_success:
                    try:
                        body = response.json()
                    except ValueError:
                        body = {"raw": response.text}
                    return {
                        "sent": True,
                        "status_code": response.status_code,
                        "response": body,
                        "payload": payload,
                        "url": send_url,
                    }

                return {
                    "sent": False,
                    "status_code": response.status_code,
                    "reason": response.text,
                    "payload": payload,
                    "url": send_url,
                }
        except httpx.HTTPError as exc:
            logger.error("MAX send_message failed: %s", exc)
            return {"sent": False, "reason": str(exc)}

    async def send_daily_impulse(self, person_id: int) -> dict[str, Any]:
        """Send one daily impulse question to a person by mapped MAX id."""
        db = SessionLocal()
        try:
            person = db.query(Person).filter(Person.person_id == person_id).first()
            if not person:
                return {"sent": False, "reason": "Person not found", "person_id": person_id}
            if not person.messenger_max_id:
                return {
                    "sent": False,
                    "reason": "Person has no messenger_max_id",
                    "person_id": person_id,
                }

            impulse = get_random_impulse()
            message_text = f"Импульс дня:\n{impulse}"
            delivery = await self.send_message(user_id=person.messenger_max_id, text=message_text)

            return {
                "sent": bool(delivery.get("sent")),
                "person_id": person_id,
                "user_id": person.messenger_max_id,
                "impulse": impulse,
                "delivery": delivery,
            }
        finally:
            db.close()

    def _get_bot_session(self, user_id: str) -> BotSession | None:
        db = SessionLocal()
        try:
            return db.query(BotSession).filter(BotSession.user_id == user_id).first()
        finally:
            db.close()

    def _set_bot_session(self, user_id: str, current_step: str, data_json: str = "{}") -> None:
        db = SessionLocal()
        try:
            session = db.query(BotSession).filter(BotSession.user_id == user_id).first()
            if session:
                session.current_step = current_step
                session.data_json = data_json
            else:
                session = BotSession(user_id=user_id, current_step=current_step, data_json=data_json)
                db.add(session)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _clear_bot_session(self, user_id: str) -> None:
        db = SessionLocal()
        try:
            session = db.query(BotSession).filter(BotSession.user_id == user_id).first()
            if session:
                db.delete(session)
                db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _parse_fio_dob(self, user_text: str) -> tuple[str, str, str | None, str] | None:
        if "," not in user_text:
            return None
        fio_part, dob_part = [p.strip() for p in user_text.split(",", 1)]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", dob_part):
            return None

        fio_tokens = [p for p in fio_part.split() if p]
        if len(fio_tokens) < 2:
            return None

        last_name = fio_tokens[0]
        first_name = fio_tokens[1]
        patronymic = " ".join(fio_tokens[2:]) if len(fio_tokens) > 2 else None
        return first_name, last_name, patronymic, dob_part

    def _create_person_profile(self, user_id: str, first_name: str, last_name: str, patronymic: str | None, birth_date: str) -> dict[str, Any]:
        db = SessionLocal()
        try:
            person = Person(
                birth_date=birth_date,
                messenger_max_id=user_id,
                is_alive=1,
                role="family_member",
                default_lang="ru",
            )
            db.add(person)
            db.flush()

            person_i18n = PersonI18n(
                person_id=person.person_id,
                lang_code="ru",
                first_name=first_name,
                last_name=last_name,
                patronymic=patronymic,
            )
            db.add(person_i18n)
            db.commit()

            return {
                "person_id": person.person_id,
                "first_name": first_name,
                "full_name": " ".join([p for p in (first_name, last_name) if p]).strip(),
            }
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def _handle_registration_step(self, user_id: str, user_text: str) -> dict[str, Any]:
        parsed = self._parse_fio_dob(user_text.strip())
        if not parsed:
            response_text = (
                "Не удалось распознать формат. Пожалуйста, отправьте данные так: "
                "Иванов Иван Иванович, 1980-01-01"
            )
            delivery = await self.send_message(user_id, response_text)
            return {
                "registered": False,
                "status": "invalid_registration_payload",
                "response_text": response_text,
                "delivery": delivery,
            }

        first_name, last_name, patronymic, birth_date = parsed
        person = self._create_person_profile(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            patronymic=patronymic,
            birth_date=birth_date,
        )
        self._clear_bot_session(user_id)

        response_text = (
            f"Профиль создан! Добро пожаловать в TimeWoven, {person['first_name']}! "
            "Теперь вы можете рассказывать свои истории."
        )
        delivery = await self.send_message(user_id, response_text)
        return {
            "registered": True,
            "status": "profile_created",
            "person": person,
            "response_text": response_text,
            "delivery": delivery,
        }

    def _find_person_by_max_id(self, user_id: str) -> dict[str, Any] | None:
        db = SessionLocal()
        try:
            person = db.query(Person).filter(Person.messenger_max_id == user_id).first()
            if not person:
                return None

            i18n = (
                db.query(PersonI18n)
                .filter(
                    PersonI18n.person_id == person.person_id,
                    PersonI18n.lang_code == "ru",
                )
                .first()
            )
            first_name = i18n.first_name if i18n and i18n.first_name else f"Персона #{person.person_id}"
            full_name = " ".join([p for p in (i18n.first_name if i18n else None, i18n.last_name if i18n else None) if p]).strip()
            if not full_name:
                full_name = first_name

            return {
                "person_id": person.person_id,
                "first_name": first_name,
                "full_name": full_name,
            }
        finally:
            db.close()

    def _get_unlinked_people(self) -> list[dict[str, Any]]:
        db = SessionLocal()
        try:
            people = db.query(Person).filter(Person.messenger_max_id.is_(None)).order_by(Person.person_id).all()
            result: list[dict[str, Any]] = []
            for person in people:
                i18n = (
                    db.query(PersonI18n)
                    .filter(
                        PersonI18n.person_id == person.person_id,
                        PersonI18n.lang_code == "ru",
                    )
                    .first()
                )
                full_name = " ".join(
                    [p for p in (i18n.first_name if i18n else None, i18n.last_name if i18n else None) if p]
                ).strip()
                if not full_name:
                    full_name = f"Персона #{person.person_id}"
                result.append({
                    "person_id": person.person_id,
                    "full_name": full_name,
                    "first_name": i18n.first_name if i18n and i18n.first_name else full_name,
                })
            return result
        finally:
            db.close()

    def _bind_user_to_person(self, user_id: str, person_id: int) -> dict[str, Any] | None:
        db = SessionLocal()
        try:
            person = (
                db.query(Person)
                .filter(
                    and_(
                        Person.person_id == person_id,
                        Person.messenger_max_id.is_(None),
                    )
                )
                .first()
            )
            if not person:
                return None

            person.messenger_max_id = user_id
            db.commit()
            db.refresh(person)

            i18n = (
                db.query(PersonI18n)
                .filter(
                    PersonI18n.person_id == person.person_id,
                    PersonI18n.lang_code == "ru",
                )
                .first()
            )
            first_name = i18n.first_name if i18n and i18n.first_name else f"Персона #{person.person_id}"
            full_name = " ".join([p for p in (i18n.first_name if i18n else None, i18n.last_name if i18n else None) if p]).strip()
            if not full_name:
                full_name = first_name
            return {
                "person_id": person.person_id,
                "first_name": first_name,
                "full_name": full_name,
            }
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def _run_identification_flow(self, user_id: str, user_text: str) -> dict[str, Any]:
        normalized = user_text.strip().lower()
        unlinked = self._get_unlinked_people()

        if normalized == "новый":
            self._set_bot_session(user_id=user_id, current_step="AWAITING_FIO_DOB", data_json="{}")
            response_text = "Понял! Давайте создадим ваш профиль. Пожалуйста, напишите ваше полное ФИО и дату рождения (ГГГГ-ММ-ДД)."
            delivery = await self.send_message(user_id, response_text)
            return {
                "identified": False,
                "status": "new_profile_todo",
                "response_text": response_text,
                "delivery": delivery,
            }

        if normalized.isdigit():
            idx = int(normalized)
            if 1 <= idx <= len(unlinked):
                selected = unlinked[idx - 1]
                bound = self._bind_user_to_person(user_id=user_id, person_id=selected["person_id"])
                if bound:
                    response_text = (
                        f"Приятно познакомиться, {bound['first_name']}! "
                        "Теперь все ваши истории будут автоматически сохраняться в ваш профиль."
                    )
                    delivery = await self.send_message(user_id, response_text)
                    return {
                        "identified": True,
                        "status": "bound",
                        "person": bound,
                        "response_text": response_text,
                        "delivery": delivery,
                    }

        greeting = (
            "Здравствуйте! Я — ваш семейный архивариус TimeWoven. "
            "Я вас пока не узнаю. Посмотрите, пожалуйста, есть ли вы в этом списке родственников?"
        )
        await self.send_message(user_id, greeting)

        if unlinked:
            lines = [f"{i}. {person['full_name']}" for i, person in enumerate(unlinked, start=1)]
            list_text = "\n".join(lines)
        else:
            list_text = "Список пока пуст."

        prompt = f"{list_text}\n\nОтправьте мне номер из списка или напишите 'Новый', если вас там нет."
        delivery = await self.send_message(user_id, prompt)

        return {
            "identified": False,
            "status": "awaiting_selection",
            "response_text": prompt,
            "delivery": delivery,
            "candidates_count": len(unlinked),
        }

    async def process_incoming_text(self, user_id: str, user_text: str, audio_url: str = None) -> dict[str, Any]:
        """Process incoming message text, then send response to MAX."""
        session = self._get_bot_session(user_id)
        if session and session.current_step == "AWAITING_FIO_DOB":
            registration = await self._handle_registration_step(user_id=user_id, user_text=user_text)
            return {
                "bot_id": self.bot_id,
                "status": self.integration_status,
                "user_id": user_id,
                "input_text": user_text,
                "audio_url": audio_url,
                "registration": registration,
            }

        person = self._find_person_by_max_id(user_id)
        if not person:
            identification = await self._run_identification_flow(user_id=user_id, user_text=user_text)
            return {
                "bot_id": self.bot_id,
                "status": self.integration_status,
                "user_id": user_id,
                "input_text": user_text,
                "audio_url": audio_url,
                "identification": identification,
            }

        entities = self.analyzer.extract_entities(user_text)
        persistence = await save_raw_memory(
            user_id=user_id,
            text=user_text,
            audio_url=audio_url,
            person_id=person["person_id"],
        )
        response_text = "Дмитрий, ваша история сохранена в семейный архив TimeWoven! 📖"

        delivery = await self.send_message(user_id=user_id, text=response_text)
        return {
            "bot_id": self.bot_id,
            "status": self.integration_status,
            "user_id": user_id,
            "person": person,
            "input_text": user_text,
            "audio_url": audio_url,
            "entities": entities,
            "persistence": persistence,
            "response_text": response_text,
            "delivery": delivery,
        }

    async def process_incoming_audio(self, user_id: str, audio_url: str) -> dict[str, Any]:
        """Download incoming audio, transcribe it, then process as text."""
        await self.send_message(user_id, "Получил ваше голосовое сообщение. Начинаю расшифровку... 🎙️")

        parsed = urlparse(audio_url)
        _, ext = os.path.splitext(parsed.path)
        suffix = ext if ext else ".ogg"
        temp_path = ""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(audio_url)
                response.raise_for_status()

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(response.content)
                temp_path = tmp.name

            transcribed_text = self.transcriber.transcribe_file(temp_path)
            if not transcribed_text:
                fallback_text = "Не удалось распознать голосовое сообщение. Попробуйте отправить текстом."
                delivery = await self.send_message(user_id, fallback_text)
                return {
                    "bot_id": self.bot_id,
                    "status": self.integration_status,
                    "user_id": user_id,
                    "audio_url": audio_url,
                    "transcribed_text": "",
                    "response_text": fallback_text,
                    "delivery": delivery,
                }

            return await self.process_incoming_text(
                user_id=user_id,
                user_text=transcribed_text,
                audio_url=audio_url,
            )
        except httpx.HTTPError as exc:
            logger.error("Failed to download audio from MAX payload: %s", exc)
            error_text = "Не удалось загрузить голосовое сообщение. Попробуйте отправить его еще раз."
            delivery = await self.send_message(user_id, error_text)
            return {
                "bot_id": self.bot_id,
                "status": self.integration_status,
                "user_id": user_id,
                "audio_url": audio_url,
                "transcribed_text": "",
                "response_text": error_text,
                "delivery": delivery,
            }
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)


async def max_messenger_webhook(user_id: str, user_text: str) -> dict[str, Any]:
    """Webhook handler for MAX Messenger events."""
    bot = MaxMessengerBot()
    return await bot.process_incoming_text(user_id=user_id, user_text=user_text)
