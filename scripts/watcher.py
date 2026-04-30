#!/usr/bin/env python3
"""
watcher.py — TimeWoven Audio Watcher (Mac)
Следит за папкой с аудио, отправляет файлы на сервер для транскрипции.
Запуск: python3 watcher.py
"""

import hashlib
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ── Настройки ────────────────────────────────────────────────────────────────
WATCH_DIR = Path.home() / "Desktop" / "timewoven_audio"
SERVER_URL = "https://app.timewoven.ru"
UPLOAD_ENDPOINT = f"{SERVER_URL}/api/audio/upload"
ADMIN_TOKEN = os.environ.get("TW_ADMIN_TOKEN", "")
POLL_INTERVAL = 10
PROCESSED_LOG = Path.home() / ".timewoven_watcher_log.json"
SUPPORTED_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".mp4"}


# ── Утилиты ───────────────────────────────────────────────────────────────────
def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read(65536))
    return h.hexdigest()


def load_log() -> dict:
    if PROCESSED_LOG.exists():
        with open(PROCESSED_LOG) as f:
            return json.load(f)
    return {}


def save_log(log_data: dict):
    with open(PROCESSED_LOG, "w") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def build_multipart(path: Path, boundary: str) -> bytes:
    """Build multipart/form-data body using only stdlib."""
    with open(path, "rb") as f:
        file_data = f.read()
    body = (
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            f"Content-Type: audio/mpeg\r\n"
            f"\r\n"
        ).encode("utf-8")
        + file_data
        + f"\r\n--{boundary}--\r\n".encode("utf-8")
    )
    return body


def upload_file(path: Path) -> dict | None:
    boundary = uuid.uuid4().hex
    body = build_multipart(path, boundary)
    token_ascii = ADMIN_TOKEN.encode("ascii", errors="ignore").decode("ascii")
    headers = {
        "Authorization": f"Bearer {token_ascii}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
    }
    try:
        req = Request(UPLOAD_ENDPOINT, data=body, headers=headers, method="POST")
        with urlopen(req, timeout=60) as resp:
            resp_body = resp.read().decode("utf-8")
            return json.loads(resp_body)
    except HTTPError as e:
        log(
            f"  Ошибка HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}"
        )
        return None
    except URLError as e:
        log(f"  Нет соединения: {e.reason}")
        return None
    except Exception as e:
        log(f"  Исключение: {e}")
        return None


def check_new_files(watch_dir: Path, processed: dict) -> list:
    new_files = []
    for path in sorted(watch_dir.iterdir()):
        if path.suffix.lower() not in SUPPORTED_EXT:
            continue
        fhash = file_hash(path)
        if fhash not in processed:
            new_files.append((path, fhash))
    return new_files


def run():
    WATCH_DIR.mkdir(parents=True, exist_ok=True)
    log(f"Watcher запущен. Слежу за: {WATCH_DIR}")
    log(f"Сервер: {SERVER_URL}")
    log(f"Интервал: {POLL_INTERVAL}с | Ctrl+C для остановки")
    print()

    processed = load_log()

    while True:
        try:
            new_files = check_new_files(WATCH_DIR, processed)

            if new_files:
                log(f"Найдено новых файлов: {len(new_files)}")
                for path, fhash in new_files:
                    log(f"  Загружаю: {path.name}")
                    result = upload_file(path)
                    if result:
                        processed[fhash] = {
                            "filename": path.name,
                            "uploaded_at": datetime.now().isoformat(),
                            "server_response": result,
                        }
                        save_log(processed)
                        log(f"  Успешно: {path.name}")
                    else:
                        log(f"  Пропускаю {path.name} до следующей попытки.")

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            log("Стоп.")
            break
        except Exception as e:
            log(f"Ошибка: {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
