from pathlib import Path
import sys

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env", override=True)

from app.db.session import SessionLocal
from app.models import Person, PersonI18n
from app.services.ai_analyzer import MemoryAnalyzer


TEST_TEXT = "В августе 1998 года мы с тетей Леной переехали жить в Москву"


def main() -> None:
    analyzer = MemoryAnalyzer()
    entities = analyzer.extract_entities(TEST_TEXT)

    print("Extracted entities:")
    print(entities)

    db = SessionLocal()
    try:
        person = (
            db.query(Person)
            .join(PersonI18n, PersonI18n.person_id == Person.person_id)
            .filter(PersonI18n.first_name == "Алексей")
            .first()
        )

        if person is None:
            print("Person lookup result: Алексей not found")
            return

        print(f"Person lookup result: person_id={person.person_id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
