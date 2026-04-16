import os
import shutil
import sqlite3
from datetime import datetime

import whisper

# === КОНФИГУРАЦИЯ ===
DB_PATH = "family.db"
RAW_DIR = "raw"
PROCESSED_DIR = "processed"
MODEL_SIZE = "small"   # для русского обычно разумный компромисс
DEFAULT_AUTHOR_ID = 1
SUPPORTED_EXTENSIONS = (".mp3", ".wav", ".m4a", ".mp4", ".mpeg", ".mpga", ".webm")

print("Загрузка модели Whisper... Это может занять время.")
model = whisper.load_model(MODEL_SIZE)


def ensure_directories():
    if not os.path.exists(RAW_DIR):
        os.makedirs(RAW_DIR)
        print(f"Создана папка: {RAW_DIR}")
    if not os.path.exists(PROCESSED_DIR):
        os.makedirs(PROCESSED_DIR)
        print(f"Создана папка: {PROCESSED_DIR}")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def list_raw_files():
    files = []
    for name in os.listdir(RAW_DIR):
        full_path = os.path.join(RAW_DIR, name)
        if os.path.isfile(full_path) and name.lower().endswith(SUPPORTED_EXTENSIONS):
            files.append(name)
    return sorted(files)


def already_processed(cursor, processed_audio_url):
    cursor.execute(
        "SELECT id FROM Memories WHERE audio_url = ? LIMIT 1",
        (processed_audio_url,)
    )
    row = cursor.fetchone()
    return row is not None


def clean_transcript(text: str) -> str:
    if not text:
        return ""
    text = " ".join(text.split())
    return text.strip()


def transcribe_file(raw_path: str) -> dict:
    result = model.transcribe(
        raw_path,
        language="ru",
        verbose=False
    )
    return result


def insert_memory(cursor, author_id: int, transcript_text: str, audio_url: str):
    now = datetime.now().isoformat(timespec="seconds")

    cursor.execute(
        """
        INSERT INTO Memories (
            author_id,
            content_text,
            transcript_verbatim,
            transcript_readable,
            audio_url,
            emotional_tone,
            intimacy_level,
            sensitivity_flag,
            confidence_score,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            author_id,
            transcript_text,
            transcript_text,
            transcript_text,
            audio_url,
            "неопределённый",
            1,
            0,
            0.95,
            now,
        ),
    )


def process_family_audio():
    ensure_directories()

    files = list_raw_files()
    if not files:
        print("Новых аудиофайлов в папке raw/ не найдено.")
        return

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        for filename in files:
            raw_path = os.path.join(RAW_DIR, filename)
            processed_path = os.path.join(PROCESSED_DIR, filename)
            processed_audio_url = f"{PROCESSED_DIR}/{filename}"

            print(f"\n--- Обработка: {filename} ---")

            if already_processed(cursor, processed_audio_url):
                print(f"Пропуск: файл уже есть в Memories как {processed_audio_url}")
                continue

            try:
                result = transcribe_file(raw_path)
                raw_text = result.get("text", "").strip()
                transcript_text = clean_transcript(raw_text)

                if not transcript_text:
                    print("Whisper не вернул текст. Файл пропущен.")
                    continue

                print(f"Распознано: {transcript_text[:120]}...")

                insert_memory(
                    cursor=cursor,
                    author_id=DEFAULT_AUTHOR_ID,
                    transcript_text=transcript_text,
                    audio_url=processed_audio_url
                )

                conn.commit()
                shutil.move(raw_path, processed_path)
                print(f"Файл успешно обработан и перемещён в {processed_path}")

            except Exception as file_error:
                conn.rollback()
                print(f"Ошибка при обработке файла {filename}: {file_error}")

    except Exception as db_error:
        print(f"Критическая ошибка работы с БД: {db_error}")

    finally:
        if conn is not None:
            conn.close()
            print("\nСоединение с базой закрыто.")

    print("Обработка завершена.")


if __name__ == "__main__":
    process_family_audio()
    
