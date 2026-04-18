#!/usr/bin/env python3
"""
watcher.py — TimeWoven Audio Watcher (Mac)
Следит за папкой с аудио, отправляет файлы на сервер для транскрипции.
Запуск: python3 watcher.py
"""

import os
import time
import hashlib
import requests
import json
from pathlib import Path
from datetime import datetime

# ── Настройки ────────────────────────────────────────────────────────────────
WATCH_DIR = Path.home() / "Desktop" / "timewoven_audio"   # папка на Маке
SERVER_URL = "https://app.timewoven.ru"                    # продакшн сервер
UPLOAD_ENDPOINT = f"{SERVER_URL}/api/audio/upload"
STATUS_ENDPOINT = f"{SERVER_URL}/api/transcription/result"
ADMIN_TOKEN = os.environ.get("TW_ADMIN_TOKEN", "")         # из env
POLL_INTERVAL = 10                                          # секунды
PROCESSED_LOG = Path.home() / ".timewoven_watcher_log.json"
SUPPORTED_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".mp4"}


# ── Утилиты ───────────────────────────────────────────────────────────────────
def file_hash(path: Path) -> str:
    """SHA256 первых 64KB для быстрой идентификации."""
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
    print(f"[{ts}] {msg}")


# ── Основная логика ───────────────────────────────────────────────────────────
def upload_file(path: Path) -> dict | None:
    """Загружает файл на сервер, возвращает JSON-ответ или None."""
    headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    try:
        with open(path, "rb") as f:
            resp = requests.post(
                UPLOAD_ENDPOINT,
                headers=headers,
                files={"file": (path.name, f, "audio/mpeg")},
                timeout=60
            )
        if resp.status_code == 200:
            return resp.json()
        else:
            log(f"  Ошибка загрузки {path.name}: HTTP {resp.status_code} — {resp.text[:200]}")
            return None
    except requests.exceptions.ConnectionError:
        log(f"  Нет соединения с сервером. Повтор через {POLL_INTERVAL}с.")
        return None
    except Exception as e:
        log(f"  Исключение при загрузке: {e}")
        return None


def check_new_files(watch_dir: Path, processed: dict) -> list:
    """Возвращает список новых (ещё не обработанных) аудиофайлов."""
    new_files = []
    for path in sorted(watch_dir.iterdir()):
        if path.suffix.lower() not in SUPPORTED_EXT:
            continue
        fhash = file_hash(path)
        if fhash not in processed:
            new_files.append((path, fhash))
    return new_files


def run():
    # Создаём папку если не существует
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
                            "server_response": result
                        }
                        save_log(processed)
                        log(f"  Успешно: {path.name}")
                    else:
                        log(f"  Пропускаю {path.name} до следующей попытки.")

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            log("Watcher остановлен пользователем.")
            break
        except Exception as e:
            log(f"Критическая ошибка: {e}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
