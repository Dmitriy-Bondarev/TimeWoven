import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Whisper-compatible transcription client with graceful fallback."""

    def __init__(self) -> None:
        self.api_token = os.getenv("WHISPER_API_TOKEN", "").strip()
        self.api_url = os.getenv(
            "WHISPER_API_URL", "https://api.openai.com/v1/audio/transcriptions"
        ).strip()
        self.model = os.getenv("WHISPER_MODEL", "whisper-1").strip()
        self.provider = (os.getenv("WHISPER_PROVIDER", "") or "").strip().lower()
        self.local_url = (os.getenv("WHISPER_LOCAL_URL", "") or "").strip()

    def _should_use_local(self) -> bool:
        # Backward compatible: allow forcing local via explicit provider or URL.
        return bool(self.local_url) and (
            self.provider.startswith("local")
            or self.provider in {"whisper_local", "local_small", "local"}
        )

    def _transcribe_local(self, audio_path: str) -> str:
        path = Path(audio_path)
        if not self.local_url:
            logger.warning("WHISPER_LOCAL_URL is not set; local transcription skipped")
            return ""
        if not path.exists() or not path.is_file():
            logger.error("Audio file for transcription does not exist: %s", audio_path)
            return ""

        try:
            with path.open("rb") as audio_file:
                files = {
                    "file": (path.name, audio_file, "application/octet-stream"),
                }
                response = httpx.post(self.local_url, files=files, timeout=180.0)
            response.raise_for_status()
            payload = response.json()
            # ops/whisper_small returns {"status":"ok","text":"..."}.
            text = str(payload.get("text", "")).strip()
            return text
        except Exception as exc:
            logger.error(
                "Local whisper transcription failed url=%s: %s", self.local_url, exc
            )
            return ""

    def transcribe_file(self, audio_path: str) -> str:
        """Transcribe an audio file and return plain text."""
        if self._should_use_local():
            return self._transcribe_local(audio_path)

        if not self.api_token:
            logger.warning("WHISPER_API_TOKEN is not set; transcription skipped")
            return ""

        path = Path(audio_path)
        if not path.exists() or not path.is_file():
            logger.error("Audio file for transcription does not exist: %s", audio_path)
            return ""

        headers = {
            "Authorization": f"Bearer {self.api_token}",
        }
        data = {
            "model": self.model,
            "response_format": "json",
        }

        try:
            with path.open("rb") as audio_file:
                files = {
                    "file": (path.name, audio_file, "application/octet-stream"),
                }
                response = httpx.post(
                    self.api_url, headers=headers, data=data, files=files, timeout=120.0
                )
            response.raise_for_status()
            payload = response.json()
            text = str(payload.get("text", "")).strip()
            return text
        except Exception as exc:
            logger.error("Transcription failed: %s", exc)
            return ""
