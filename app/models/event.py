from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.db.base import Base
from datetime import datetime


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String)
    description = Column(String)

    date = Column(DateTime, default=datetime.utcnow)

    family_id = Column(Integer, ForeignKey("families.id"))
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True)
    