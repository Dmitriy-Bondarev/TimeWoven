import os
import shutil
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime

# === КОНФИГУРАЦИЯ СЕРВЕРА ===
# На сервере используем localhost, так как БД находится тут же
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "timewoven"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD"),
    "port": os.getenv("DB_PORT", "5432"),
}

STORAGE_DIR = "storage/memories"
RAW_DIR = "raw"
PROCESSED_DIR = "processed"
DEFAULT_AUTHOR_ID = 1

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def ensure_directories():
    for d in [RAW_DIR, PROCESSED_DIR, STORAGE_DIR]:
        if not os.path.exists(d):
            os.makedirs(d, exist_ok=True)

def already_processed(cursor, audio_url):
    cursor.execute("SELECT id FROM memories WHERE audio_url = %s LIMIT 1", (audio_url,))
    return cursor.fetchone() is not None

def insert_memory_record(cursor, author_id, text, audio_url):
    """Вставка записи без Whisper (чисто метаданные)"""
    now = datetime.now()
    query = """
        INSERT INTO memories (
            author_id, content_text, transcript_verbatim, transcript_readable,
            audio_url, emotional_tone, intimacy_level, sensitivity_flag,
            confidence_score, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(query, (
        author_id, text, text, text, audio_url, 
        "обработано_локально", 1, False, 1.0, now, now
    ))

def process_server_files():
    """
    Этот скрипт на сервере теперь только проверяет наличие файлов 
    и синхронизирует их с базой, если транскрибация уже готова.
    """
    ensure_directories()
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        print("Подключено к локальной БД PostgreSQL")

        # Здесь могла бы быть логика сервера, но так как Whisper на Маке,
        # серверный процессор в основном будет простаивать.
        print("Серверный процессор готов. Whisper отключен (используется Hybrid Mode).")

    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    process_server_files()