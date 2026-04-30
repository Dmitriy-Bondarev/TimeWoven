from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.db.base import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String)
    description = Column(String)

    date = Column(DateTime, default=datetime.utcnow)

    family_id = Column(Integer, ForeignKey("families.id"))
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True)
