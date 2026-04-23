"""Controlled reply layer for Max session flow (T19).

This module builds short user-facing acknowledgements for key Max session steps.
It prefers hard templates for safety and can optionally use llama_local to
slightly vary phrasing. Any AI failure falls back to deterministic templates.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from app.services.ai_analyzer import analyze_memory_text

logger = logging.getLogger(__name__)

MAX_REPLY_LEN = 240


def _cap_reply(text: str, limit: int = MAX_REPLY_LEN) -> str:
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def _ai_enabled_for_replies() -> bool:
    provider = (os.getenv("AI_PROVIDER", "disabled") or "").strip().lower()
    return provider == "llama_local"


def _ai_variation_or_none(prompt: str) -> str | None:
    if not _ai_enabled_for_replies():
        return None

    try:
        result = analyze_memory_text(prompt)
    except Exception as exc:  # pragma: no cover - safety guard
        logger.info("bot_reply fallback: analyze_memory_text exception: %s", exc)
        return None

    if str(result.get("status", "")) != "ok":
        logger.info("bot_reply fallback: AI status=%s", result.get("status"))
        return None

    candidate = str(result.get("summary", "") or "").strip()
    if not candidate:
        logger.info("bot_reply fallback: empty AI summary")
        return None

    return _cap_reply(candidate)


def build_ack_for_new_session(text: str, session: Any = None, analysis: dict | None = None) -> str:
    """Ack for first text in a new/open session."""
    fallback = "Я записываю эту историю. Можете продолжать, а когда закончите — напишите 'Готово'."

    prompt = (
        "Сформулируй короткий дружелюбный ответ для автора семейной истории. "
        "Смысл должен быть: история записывается, можно продолжать, для завершения написать 'Готово'. "
        "Ограничение: до 240 символов, без JSON, одним предложением. "
        f"Текст автора: {text or ''}"
    )
    ai = _ai_variation_or_none(prompt)
    return ai or fallback


def build_ack_for_audio(session: Any = None, audio_item: dict | None = None, transcription_result: dict | None = None) -> str:
    """Ack after incoming audio.

    Success means audio was downloaded and saved locally; transcription may still be empty.
    """
    audio_item = audio_item or {}
    local_path = audio_item.get("local_path")
    transcription_status = str(audio_item.get("transcription_status") or "")

    if not local_path:
        return "Кажется, у меня проблемы с этим голосовым. Попробуйте, пожалуйста, ещё раз или отправьте текстом."

    fallback = "Голос получил и сохранил. Можете добавить ещё или написать 'Готово'."

    # We only vary wording for successful storage path; semantics must stay fixed.
    prompt = (
        "Сформулируй короткий ответ для подтверждения, что голосовое получено и сохранено. "
        "Смысл: можно добавить ещё или написать 'Готово'. "
        "Ограничение: до 240 символов, без JSON, одним предложением. "
        f"Статус транскрипции: {transcription_status}"
    )
    ai = _ai_variation_or_none(prompt)
    return ai or fallback


def build_ack_for_finalize(memory: Any, session: Any = None, analysis: dict | None = None) -> str:
    """Ack after successful finalize_session -> Memory created."""
    fallback = "Спасибо. Я сохранил эту историю как черновик семейного архива."

    draft_text = ""
    if memory is not None:
        draft_text = str(getattr(memory, "content_text", "") or "")

    prompt = (
        "Сформулируй короткое благодарственное сообщение после сохранения семейной истории в черновик. "
        "Смысл должен быть: история сохранена как черновик семейного архива. "
        "Ограничение: до 240 символов, без JSON, одним-двумя предложениями. "
        f"Текст истории: {draft_text[:500]}"
    )
    ai = _ai_variation_or_none(prompt)
    return ai or fallback
