from __future__ import annotations

import json
import os
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env", override=True)

from app.services.ai_analyzer import analyze_memory_text


TEST_TEXT = "В 1976 году бабушка Анна переехала в Томск."


@contextmanager
def temporary_env(**updates: str | None) -> Iterator[None]:
    previous_values = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class LocalStubHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/analyze":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        payload = json.loads(body.decode("utf-8") or "{}")

        response = {
            "summary": f"stub-summary: {payload.get('text', '')[:24]}",
            "people": [
                {"name": "Анна", "role": "бабушка", "confidence": 0.98},
            ],
            "events": [
                {
                    "type": "migration",
                    "title": "Переезд в Томск",
                    "year": 1976,
                    "place": "Томск",
                    "confidence": 0.93,
                }
            ],
            "dates": [
                {"year": 1976, "description": "Переезд", "confidence": 0.91},
            ],
            "ignored_extra_field": True,
        }
        response_bytes = json.dumps(response, ensure_ascii=False).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def log_message(self, format: str, *args: object) -> None:
        return


@contextmanager
def run_local_stub_server() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), LocalStubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}/analyze"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_disabled_provider() -> None:
    with temporary_env(AI_PROVIDER="disabled"):
        result = analyze_memory_text(TEST_TEXT)
    assert result["status"] == "disabled", result
    assert result["raw_provider"] == "disabled", result


def test_local_stub_missing_url() -> None:
    with temporary_env(AI_PROVIDER="local_stub", AI_LOCAL_STUB_URL=""):
        result = analyze_memory_text(TEST_TEXT)
    assert result["status"] == "error", result
    assert result["raw_provider"]["error"] == "missing AI_LOCAL_STUB_URL", result


def test_local_stub_broken_url() -> None:
    with temporary_env(AI_PROVIDER="local_stub", AI_LOCAL_STUB_URL="http://127.0.0.1:1/analyze"):
        result = analyze_memory_text(TEST_TEXT)
    assert result["status"] == "error", result
    assert result["raw_provider"]["provider"] == "local_stub", result


def test_local_stub_success() -> None:
    with run_local_stub_server() as stub_url:
        with temporary_env(AI_PROVIDER="local_stub", AI_LOCAL_STUB_URL=stub_url):
            result = analyze_memory_text(TEST_TEXT)

    assert result["status"] == "ok", result
    assert result["summary"].startswith("stub-summary:"), result
    assert result["persons"][0]["name"] == "Анна", result
    assert result["dates"][0]["year"] == 1976, result
    assert result["locations"] == [], result
    assert result["raw_provider"]["endpoint"] == stub_url, result
    assert result["raw_provider"]["status_code"] == 200, result


def main() -> None:
    test_disabled_provider()
    test_local_stub_missing_url()
    test_local_stub_broken_url()
    test_local_stub_success()
    print("AI local_stub smoke tests: OK")


if __name__ == "__main__":
    main()