import json
import logging
import os
import re
from typing import Any

import httpx

try:
    import anthropic
except Exception:  # pragma: no cover - optional dependency runtime guard
    anthropic = None


logger = logging.getLogger(__name__)
LOCAL_STUB_TIMEOUT_SECONDS = 15.0


SYSTEM_PROMPT = (
    "Ты лингвистический анализатор семейных воспоминаний. "
    "Верни СТРОГО валидный JSON формата: "
    "{\"summary\": \"\", \"dates\": [], \"persons\": [], \"locations\": []}. "
    "summary: короткое резюме в 1-2 предложениях. "
    "Не пиши ничего, кроме JSON. Никаких markdown-бэктиков."
)


def _empty_analysis(status: str = "ok", raw_provider: Any = "disabled") -> dict[str, Any]:
    return {
        "summary": "",
        "persons": [],
        "dates": [],
        "locations": [],
        "raw_provider": raw_provider,
        "status": status,
    }


class BaseAnalyzerProvider:
    provider_name = "base"

    def analyze(self, text: str) -> dict[str, Any]:
        raise NotImplementedError()


class DisabledAnalyzerProvider(BaseAnalyzerProvider):
    provider_name = "disabled"

    def analyze(self, text: str) -> dict[str, Any]:
        return _empty_analysis(status="disabled", raw_provider=self.provider_name)


class MockAnalyzerProvider(BaseAnalyzerProvider):
    provider_name = "mock"

    def analyze(self, text: str) -> dict[str, Any]:
        normalized = (text or "").strip()
        result = _empty_analysis(status="ok", raw_provider=self.provider_name)
        if not normalized:
            return result

        # Lightweight deterministic extraction for local smoke tests.
        result["summary"] = normalized[:180]
        date_candidates = re.findall(r"\b\d{4}\b|\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", normalized)
        result["dates"] = sorted(set(date_candidates))[:10]
        capitalized_words = re.findall(r"\b[А-ЯЁ][а-яё]+\b", normalized)
        result["persons"] = sorted(set(capitalized_words))[:10]
        return result


class LocalStubAnalyzerProvider(BaseAnalyzerProvider):
    provider_name = "local_stub"

    def __init__(self) -> None:
        self.url = os.getenv("AI_LOCAL_STUB_URL", "").strip()

    def _error_result(self, error_message: str, status_code: int | None = None) -> dict[str, Any]:
        raw_provider = {
            "provider": self.provider_name,
            "endpoint": self.url,
            "error": error_message,
        }
        if status_code is not None:
            raw_provider["status_code"] = status_code

        return _empty_analysis(status="error", raw_provider=raw_provider)

    def _normalize_list(self, value: Any) -> list[Any]:
        return value if isinstance(value, list) else []

    def analyze(self, text: str) -> dict[str, Any]:
        normalized = (text or "").strip()
        if not normalized:
            return _empty_analysis(
                status="ok",
                raw_provider={"provider": self.provider_name, "endpoint": self.url},
            )

        if not self.url:
            return self._error_result("missing AI_LOCAL_STUB_URL")

        try:
            response = httpx.post(
                self.url,
                json={"text": normalized},
                timeout=LOCAL_STUB_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            logger.warning("Local stub request failed endpoint=%s: %s", self.url, exc)
            return self._error_result(str(exc))

        if response.status_code != 200:
            logger.warning(
                "Local stub returned non-200 endpoint=%s status_code=%s",
                self.url,
                response.status_code,
            )
            return self._error_result(
                f"unexpected status code: {response.status_code}",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            logger.warning("Local stub returned invalid JSON endpoint=%s: %s", self.url, exc)
            return self._error_result("invalid JSON response", status_code=response.status_code)

        if not isinstance(payload, dict):
            logger.warning("Local stub returned non-object JSON endpoint=%s", self.url)
            return self._error_result("response JSON is not an object", status_code=response.status_code)

        return {
            "summary": str(payload.get("summary", "") or "").strip(),
            "persons": self._normalize_list(payload.get("people")),
            "dates": self._normalize_list(payload.get("dates")),
            "locations": [],
            "raw_provider": {
                "provider": self.provider_name,
                "endpoint": self.url,
                "status_code": response.status_code,
            },
            "status": "ok",
        }


LLAMA_LOCAL_TIMEOUT_SECONDS = 30.0


class LlamaLocalAnalyzerProvider(BaseAnalyzerProvider):
    """Provider for a locally-hosted LLaMA-compatible HTTP server.

    Expects AI_LLAMA_LOCAL_URL to point at an endpoint accepting
    POST {"text": str} and returning {"summary", "people", "events", "dates"}.
    Network errors and invalid responses are caught and returned as status="error".
    """

    provider_name = "llama_local"

    def __init__(self) -> None:
        self.url = os.getenv("AI_LLAMA_LOCAL_URL", "").strip()

    def _error_result(self, error_message: str, status_code: int | None = None) -> dict[str, Any]:
        raw_provider: dict[str, Any] = {
            "provider": self.provider_name,
            "endpoint": self.url,
            "error": error_message,
        }
        if status_code is not None:
            raw_provider["status_code"] = status_code
        return _empty_analysis(status="error", raw_provider=raw_provider)

    def _normalize_list(self, value: Any) -> list[Any]:
        return value if isinstance(value, list) else []

    def analyze(self, text: str) -> dict[str, Any]:
        normalized = (text or "").strip()
        if not normalized:
            return _empty_analysis(
                status="ok",
                raw_provider={"provider": self.provider_name, "endpoint": self.url},
            )

        if not self.url:
            return self._error_result("missing AI_LLAMA_LOCAL_URL")

        try:
            response = httpx.post(
                self.url,
                json={"text": normalized},
                timeout=LLAMA_LOCAL_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            logger.warning("llama_local request failed endpoint=%s: %s", self.url, exc)
            return self._error_result(str(exc))

        if response.status_code != 200:
            logger.warning(
                "llama_local returned non-200 endpoint=%s status_code=%s",
                self.url,
                response.status_code,
            )
            return self._error_result(
                f"unexpected status code: {response.status_code}",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            logger.warning("llama_local returned invalid JSON endpoint=%s: %s", self.url, exc)
            return self._error_result("invalid JSON response", status_code=response.status_code)

        if not isinstance(payload, dict):
            logger.warning("llama_local returned non-object JSON endpoint=%s", self.url)
            return self._error_result("response JSON is not an object", status_code=response.status_code)

        return {
            "summary": str(payload.get("summary", "") or "").strip(),
            "persons": self._normalize_list(payload.get("people")),
            "dates": self._normalize_list(payload.get("dates")),
            "locations": [],
            "events": self._normalize_list(payload.get("events")),
            "raw_provider": {
                "provider": self.provider_name,
                "endpoint": self.url,
                "status_code": response.status_code,
            },
            "status": "ok",
        }


class AnthropicAnalyzerProvider(BaseAnalyzerProvider):
    provider_name = "anthropic"

    def __init__(self) -> None:
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.primary_model = os.getenv("ANTHROPIC_PRIMARY_MODEL", "claude-3-5-sonnet-latest").strip()
        self.fallback_model = os.getenv("ANTHROPIC_FALLBACK_MODEL", "claude-3-haiku-latest").strip()
        if anthropic is None:
            self.client = None
            logger.warning("anthropic package is not installed; anthropic provider unavailable")
            return

        self.client = anthropic.Anthropic(api_key=self.api_key) if self.api_key else None

        if not self.client:
            logger.warning("ANTHROPIC_API_KEY is not set; anthropic provider unavailable")

    def _extract_text(self, response: Any) -> str:
        chunks: list[str] = []
        for block in getattr(response, "content", []):
            if getattr(block, "type", None) == "text":
                chunks.append(getattr(block, "text", ""))
        return "".join(chunks).strip()

    def _parse_json(self, raw_text: str) -> dict[str, Any]:
        payload = json.loads(raw_text)
        if not isinstance(payload, dict):
            raise ValueError("AI response is not a JSON object")

        result = _empty_analysis(status="ok", raw_provider=self.provider_name)
        result["summary"] = str(payload.get("summary", "") or "").strip()
        for key in ("dates", "persons", "locations"):
            value = payload.get(key, [])
            if isinstance(value, list):
                result[key] = [str(item) for item in value if item is not None]
        return result

    def _request_model(self, model_name: str, text: str) -> dict[str, Any]:
        if not self.client:
            raise RuntimeError("ANTHROPIC_API_KEY is not set; cannot initialize anthropic client")

        response = self.client.messages.create(
            model=model_name,
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        raw_text = self._extract_text(response)
        return self._parse_json(raw_text)

    def analyze(self, text: str) -> dict[str, Any]:
        normalized = (text or "").strip()
        if not normalized:
            return _empty_analysis(status="ok", raw_provider=self.provider_name)

        try:
            return self._request_model(self.primary_model, normalized)
        except Exception as primary_exc:
            logger.warning(
                "Anthropic primary model failed (%s): %s",
                self.primary_model,
                primary_exc,
            )
            try:
                return self._request_model(self.fallback_model, normalized)
            except Exception as fallback_exc:
                logger.error(
                    "Anthropic fallback model failed (%s): %s",
                    self.fallback_model,
                    fallback_exc,
                )
                return _empty_analysis(status="error", raw_provider=self.provider_name)


class ProviderAgnosticAnalyzer:
    def __init__(self, provider_name: str | None = None) -> None:
        self.provider_name = (provider_name or os.getenv("AI_PROVIDER", "disabled")).strip().lower()
        self.provider = self._build_provider(self.provider_name)
        logger.info("AI analyzer initialized with provider=%s", self.provider_name)

    def _build_provider(self, provider_name: str) -> BaseAnalyzerProvider:
        if provider_name == "disabled":
            return DisabledAnalyzerProvider()
        if provider_name == "mock":
            return MockAnalyzerProvider()
        if provider_name == "local_stub":
            return LocalStubAnalyzerProvider()
        if provider_name == "llama_local":
            return LlamaLocalAnalyzerProvider()
        if provider_name == "anthropic":
            return AnthropicAnalyzerProvider()

        logger.warning("Unknown AI_PROVIDER=%s; falling back to disabled", provider_name)
        self.provider_name = "disabled"
        return DisabledAnalyzerProvider()

    def analyze_memory_text(self, text: str) -> dict[str, Any]:
        try:
            return self.provider.analyze(text)
        except Exception as exc:
            logger.error("AI analyzer provider failure (%s): %s", self.provider_name, exc)
            return _empty_analysis(status="error", raw_provider=self.provider_name)


class MemoryAnalyzer:
    """Backward-compatible adapter for existing max bot flow."""

    def __init__(self) -> None:
        self.adapter = ProviderAgnosticAnalyzer()

    def extract_entities(self, text: str) -> dict:
        result = self.adapter.analyze_memory_text(text)
        return {
            "dates": result.get("dates", []),
            "persons": result.get("persons", []),
            "locations": result.get("locations", []),
        }


def analyze_memory_text(text: str) -> dict[str, Any]:
    analyzer = ProviderAgnosticAnalyzer()
    return analyzer.analyze_memory_text(text)
