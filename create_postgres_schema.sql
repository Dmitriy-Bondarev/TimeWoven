-- TimeWoven PostgreSQL Schema v1.3

CREATE TABLE IF NOT EXISTS "People" (
    person_id       SERIAL PRIMARY KEY,
    maiden_name     VARCHAR,
    gender          VARCHAR CHECK (gender IN ('M', 'F', 'Unknown')),
    birth_date      VARCHAR,
    birth_date_prec VARCHAR CHECK (birth_date_prec IN ('EXACT', 'ABOUT', 'YEARONLY', 'DECADE')),
    death_date      VARCHAR,
    death_date_prec VARCHAR CHECK (death_date_prec IN ('EXACT', 'ABOUT', 'YEARONLY', 'DECADE')),
    is_alive        INTEGER NOT NULL DEFAULT 1,
    is_user         INTEGER NOT NULL DEFAULT 0,
    role            VARCHAR NOT NULL DEFAULT 'placeholder',
    successor_id    INTEGER REFERENCES "People"(person_id),
    default_lang    VARCHAR NOT NULL DEFAULT 'ru',
    phone           VARCHAR,
    preferred_ch    VARCHAR CHECK (preferred_ch IN ('Max', 'TG', 'Email', 'Push', 'None')),
    messenger_max_id VARCHAR UNIQUE,
    messenger_tg_id VARCHAR UNIQUE,
    contact_email   VARCHAR,
    avatar_url      VARCHAR,
    pin             VARCHAR
);

CREATE TABLE IF NOT EXISTS "People_I18n" (
    person_id   INTEGER NOT NULL REFERENCES "People"(person_id),
    lang_code   VARCHAR NOT NULL,
    first_name  VARCHAR NOT NULL,
    last_name   VARCHAR,
    patronymic  VARCHAR,
    biography   TEXT,
    PRIMARY KEY (person_id, lang_code)
);

CREATE TABLE IF NOT EXISTS "Places" (
    place_id     SERIAL PRIMARY KEY,
    country      VARCHAR,
    region       VARCHAR,
    city         VARCHAR,
    coordinates  VARCHAR,
    address_raw  VARCHAR,
    metadata     TEXT
);

CREATE TABLE IF NOT EXISTS "Events" (
    event_id        SERIAL PRIMARY KEY,
    author_id       INTEGER REFERENCES "People"(person_id),
    location_id     INTEGER REFERENCES "Places"(place_id),
    event_type      VARCHAR NOT NULL,
    date_start      VARCHAR,
    date_start_prec VARCHAR,
    date_end        VARCHAR,
    date_end_prec   VARCHAR,
    is_private      INTEGER NOT NULL DEFAULT 0,
    cover_asset_id  INTEGER
);

CREATE TABLE IF NOT EXISTS "EventParticipants" (
    event_id         INTEGER NOT NULL REFERENCES "Events"(event_id),
    person_id        INTEGER NOT NULL REFERENCES "People"(person_id),
    participant_role VARCHAR NOT NULL,
    is_featured      INTEGER DEFAULT 0,
    added_at         VARCHAR,
    PRIMARY KEY (event_id, person_id, participant_role)
);

CREATE TABLE IF NOT EXISTS "Memories" (
    id                  SERIAL PRIMARY KEY,
    author_id           INTEGER REFERENCES "People"(person_id),
    event_id            INTEGER REFERENCES "Events"(event_id),
    parent_memory_id    INTEGER REFERENCES "Memories"(id),
    content_text        TEXT,
    audio_url           VARCHAR,
    transcript_verbatim TEXT,
    transcript_readable TEXT,
    emotional_tone      VARCHAR,
    intimacy_level      INTEGER DEFAULT 1,
    sensitivity_flag    INTEGER DEFAULT 0,
    confidence_score    FLOAT,
    created_at          VARCHAR DEFAULT (to_char(now(), 'YYYY-MM-DD HH24:MI:SS')),
    created_by          INTEGER REFERENCES "People"(person_id),
    source_type         VARCHAR
);

CREATE TABLE IF NOT EXISTS "MemoryPeople" (
    memory_id INTEGER NOT NULL REFERENCES "Memories"(id),
    person_id INTEGER NOT NULL REFERENCES "People"(person_id),
    role      VARCHAR NOT NULL CHECK (role IN ('author', 'mentioned', 'addressee', 'subject')),
    PRIMARY KEY (memory_id, person_id, role)
);

CREATE TABLE IF NOT EXISTS "Quotes" (
    id               SERIAL PRIMARY KEY,
    author_id        INTEGER NOT NULL REFERENCES "People"(person_id),
    content_text     TEXT NOT NULL,
    source_memory_id INTEGER REFERENCES "Memories"(id),
    created_at       VARCHAR DEFAULT (to_char(now(), 'YYYY-MM-DD HH24:MI:SS'))
);

CREATE TABLE IF NOT EXISTS "AvatarHistory" (
    avatar_id    SERIAL PRIMARY KEY,
    person_id    INTEGER NOT NULL REFERENCES "People"(person_id),
    storage_path VARCHAR NOT NULL,
    target_year  INTEGER,
    is_current   INTEGER NOT NULL DEFAULT 0,
    source_type  VARCHAR NOT NULL,
    created_at   VARCHAR,
    metadata     TEXT
);

CREATE TABLE IF NOT EXISTS "RelationshipType" (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR NOT NULL,
    symmetry_type   VARCHAR NOT NULL,
    category        VARCHAR NOT NULL,
    inverse_type_id INTEGER REFERENCES "RelationshipType"(id)
);

CREATE TABLE IF NOT EXISTS "PersonRelationship" (
    rel_id               SERIAL PRIMARY KEY,
    person_from_id       INTEGER NOT NULL REFERENCES "People"(person_id),
    person_to_id         INTEGER NOT NULL REFERENCES "People"(person_id),
    relationship_type_id INTEGER NOT NULL REFERENCES "RelationshipType"(id),
    is_primary           INTEGER NOT NULL DEFAULT 1,
    valid_from           VARCHAR,
    valid_to             VARCHAR,
    comment              VARCHAR
);
