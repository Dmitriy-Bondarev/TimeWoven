from sqlalchemy import text

from app.db.session import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        db.execute(
            text(
                'ALTER TABLE "Memories" '
                'ADD COLUMN IF NOT EXISTS is_archived BOOLEAN NOT NULL DEFAULT FALSE'
            )
        )
        db.execute(
            text(
                'ALTER TABLE "Memories" '
                'ALTER COLUMN is_archived SET DEFAULT FALSE'
            )
        )
        db.execute(
            text(
                'UPDATE "Memories" SET is_archived = FALSE WHERE is_archived IS NULL'
            )
        )
        db.commit()
        print("is_archived migration applied")
    finally:
        db.close()


if __name__ == "__main__":
    main()
