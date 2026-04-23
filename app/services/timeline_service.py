from sqlalchemy.orm import Session
from app.models.event import Event
from datetime import datetime


def get_timeline(db: Session, family_id: int):
    return (
        db.query(Event)
        .filter(Event.family_id == family_id)
        .order_by(Event.date.asc())
        .all()
    )


def create_event(db: Session, data: dict):
    event = Event(
        title=data.get("title"),
        description=data.get("description"),
        date=data.get("date", datetime.utcnow()),
        family_id=data.get("family_id"),
        person_id=data.get("person_id"),
        type=data.get("type", "custom"),
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return event


def delete_event(db: Session, event_id: int):
    event = db.query(Event).get(event_id)

    if not event:
        return None

    db.delete(event)
    db.commit()

    return True
    