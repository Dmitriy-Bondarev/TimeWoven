from sqlalchemy import Column, Integer, String, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from .db import Base


class Person(Base):
    __tablename__ = "People"

    person_id = Column(Integer, primary_key=True, index=True)
    maiden_name = Column(String)
    gender = Column(String)
    birth_date = Column(String)
    birth_date_prec = Column(String)
    death_date = Column(String)
    death_date_prec = Column(String)
    is_alive = Column(Integer)
    is_user = Column(Integer)
    role = Column(String)
    successor_id = Column(Integer, ForeignKey("People.person_id"))
    default_lang = Column(String)
    phone = Column(String)
    preferred_ch = Column(String)
    avatar_url = Column(String)
    pin = Column(String)

    translations = relationship("PersonI18n", back_populates="person")
    quotes = relationship("Quote", back_populates="author")
    memories_authored = relationship("Memory", foreign_keys="Memory.author_id", back_populates="author")
    memories_created = relationship("Memory", foreign_keys="Memory.created_by", back_populates="creator")


class PersonI18n(Base):
    __tablename__ = "People_I18n"

    person_id = Column(Integer, ForeignKey("People.person_id"), primary_key=True)
    lang_code = Column(String, primary_key=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String)
    patronymic = Column(String)
    biography = Column(Text)

    person = relationship("Person", back_populates="translations")


class Memory(Base):
    __tablename__ = "Memories"

    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("People.person_id"))
    event_id = Column(Integer, nullable=True)
    parent_memory_id = Column(Integer, ForeignKey("Memories.id"), nullable=True)
    content_text = Column(Text)
    audio_url = Column(String)
    transcript_verbatim = Column(Text)
    transcript_readable = Column(Text)
    emotional_tone = Column(String)
    intimacy_level = Column(Integer)
    sensitivity_flag = Column(Integer)
    confidence_score = Column(Float)
    created_at = Column(String)
    created_by = Column(Integer, ForeignKey("People.person_id"))
    source_type = Column(String)

    author = relationship("Person", foreign_keys=[author_id], back_populates="memories_authored")
    creator = relationship("Person", foreign_keys=[created_by], back_populates="memories_created")
    quotes = relationship("Quote", back_populates="memory")


class Quote(Base):
    __tablename__ = "Quotes"

    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("People.person_id"), nullable=False)
    content_text = Column(Text, nullable=False)
    source_memory_id = Column(Integer, ForeignKey("Memories.id"))
    created_at = Column(String)

    author = relationship("Person", back_populates="quotes")
    memory = relationship("Memory", back_populates="quotes")


class AvatarHistory(Base):
    __tablename__ = "AvatarHistory"

    avatar_id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("People.person_id"), nullable=False)
    storage_path = Column(String, nullable=False)
    target_year = Column(Integer)
    is_current = Column(Integer, default=0)
    source_type = Column(String, nullable=False)
    created_at = Column(String)


class Event(Base):
    __tablename__ = "Events"

    event_id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("People.person_id"))
    location_id = Column(Integer)
    event_type = Column(String, nullable=False)
    date_start = Column(String)
    date_start_prec = Column(String)
    date_end = Column(String)
    date_end_prec = Column(String)
    is_private = Column(Integer, default=0)
    cover_asset_id = Column(Integer)
