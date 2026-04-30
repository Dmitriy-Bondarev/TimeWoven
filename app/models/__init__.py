from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


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
    messenger_max_id = Column(String, unique=True, nullable=True)
    messenger_tg_id = Column(String, unique=True, nullable=True)
    contact_email = Column(String, nullable=True)
    avatar_url = Column(String)
    pin = Column(String)
    record_status = Column(
        String, nullable=False, default="active", server_default=text("'active'")
    )
    public_uuid = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    family_access_enabled = Column(
        Boolean, nullable=False, server_default=text("false")
    )
    totp_secret_encrypted = Column(Text, nullable=True)
    totp_enabled_at = Column(DateTime(timezone=True), nullable=True)
    totp_last_used_at = Column(DateTime(timezone=True), nullable=True)
    family_access_revoked_at = Column(DateTime(timezone=True), nullable=True)

    translations = relationship("PersonI18n", back_populates="person")
    aliases = relationship(
        "PersonAlias",
        back_populates="person",
        foreign_keys="PersonAlias.person_id",
        cascade="all, delete-orphan",
    )
    quotes = relationship("Quote", back_populates="author")
    memories_authored = relationship(
        "Memory", foreign_keys="Memory.author_id", back_populates="author"
    )
    memories_created = relationship(
        "Memory", foreign_keys="Memory.created_by", back_populates="creator"
    )


class PersonAlias(Base):
    """Соответствует продовой таблице `personaliases` (v2, без legacy alias_text/alias_kind)."""

    __tablename__ = "personaliases"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    person_id = Column(
        Integer,
        ForeignKey("People.person_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label = Column(String, nullable=False)
    alias_type = Column(String, nullable=False)
    used_by_generation = Column(String, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    spoken_by_person_id = Column(
        Integer, ForeignKey("People.person_id"), nullable=True, index=True
    )
    source = Column(String, nullable=False, server_default=text("'manual'"))
    status = Column(String, nullable=False, server_default=text("'active'"))
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    person = relationship(
        "Person",
        back_populates="aliases",
        foreign_keys=[person_id],
    )
    spoken_by_person = relationship(
        "Person",
        foreign_keys=[spoken_by_person_id],
    )


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
    essence_text = Column(Text)
    emotional_tone = Column(String)
    intimacy_level = Column(Integer)
    sensitivity_flag = Column(Integer)
    confidence_score = Column(Float)
    created_at = Column(String)
    created_by = Column(Integer, ForeignKey("People.person_id"))
    source_type = Column(String)
    transcription_status = Column(String, default="pending")
    is_archived = Column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )

    author = relationship(
        "Person", foreign_keys=[author_id], back_populates="memories_authored"
    )
    creator = relationship(
        "Person", foreign_keys=[created_by], back_populates="memories_created"
    )
    quotes = relationship("Quote", back_populates="memory")


class Quote(Base):
    __tablename__ = "Quotes"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
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


class Union(Base):
    """Союз/брак/партнёрство между людьми с общими детьми."""

    __tablename__ = "Unions"

    id = Column(Integer, primary_key=True, index=True)
    partner1_id = Column(Integer, ForeignKey("People.person_id"), nullable=True)
    partner2_id = Column(Integer, ForeignKey("People.person_id"), nullable=True)
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)

    partner1 = relationship("Person", foreign_keys=[partner1_id])
    partner2 = relationship("Person", foreign_keys=[partner2_id])
    children = relationship(
        "UnionChild",
        back_populates="union",
        cascade="all, delete-orphan",
    )


class UnionChild(Base):
    """Связь между Union и Person (ребёнок)."""

    __tablename__ = "UnionChildren"

    id = Column(Integer, primary_key=True, index=True)
    union_id = Column(Integer, ForeignKey("Unions.id"), nullable=False)
    child_id = Column(Integer, ForeignKey("People.person_id"), nullable=False)

    union = relationship("Union", back_populates="children")
    child = relationship("Person", foreign_keys=[child_id])


class BotSession(Base):
    __tablename__ = "bot_sessions"

    user_id = Column(String, primary_key=True)
    current_step = Column(String)
    data_json = Column(Text)


class MaxContactEvent(Base):
    __tablename__ = "MaxContactEvents"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    created_at = Column(String, nullable=False)
    sender_max_user_id = Column(String, nullable=False, index=True)
    contact_max_user_id = Column(String, nullable=True, index=True)
    contact_name = Column(String, nullable=True)
    contact_first_name = Column(String, nullable=True)
    contact_last_name = Column(String, nullable=True)
    raw_payload = Column(Text, nullable=False)
    matched_person_id = Column(Integer, ForeignKey("People.person_id"), nullable=True)
    status = Column(
        String, nullable=False, default="new", server_default=text("'new'"), index=True
    )


class MaxChatSession(Base):
    """Session grouping incoming Max messages into a draft until the user sends a finalize command."""

    __tablename__ = "max_chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    max_user_id = Column(String, nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("People.person_id"), nullable=True)
    status = Column(
        String, nullable=False, default="open", server_default=text("'open'")
    )
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
    finalized_at = Column(String, nullable=True)
    draft_text = Column(Text, nullable=True)  # concatenated text items
    draft_items = Column(Text, nullable=True)  # JSON array of {type, ...}
    message_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    audio_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    memory_id = Column(Integer, ForeignKey("Memories.id"), nullable=True)
    analysis_status = Column(String, nullable=True)

    person = relationship("Person", foreign_keys=[person_id])
    memory = relationship("Memory", foreign_keys=[memory_id])


class EarlyAccessRequest(Base):
    __tablename__ = "EarlyAccessRequests"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=True)
    preferred_channel = Column(String, nullable=False)
    contact_value = Column(String, nullable=False)
    about = Column(Text, nullable=True)
    source = Column(String, nullable=False)
    status = Column(String, nullable=False)


class FamilyAccessSession(Base):
    __tablename__ = "family_access_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    person_id = Column(
        Integer, ForeignKey("People.person_id"), nullable=False, index=True
    )
    session_token_hash = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    revoked_at = Column(DateTime, nullable=True, index=True)
    created_ip = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)


class PersonAccessBackupCode(Base):
    __tablename__ = "person_access_backup_codes"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    person_id = Column(
        Integer, ForeignKey("People.person_id"), nullable=False, index=True
    )
    code_hash = Column(String, nullable=False, index=True)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)


class DemoTable(Base):
    __tablename__ = "demo_table"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    note = Column(String(255), nullable=True)
