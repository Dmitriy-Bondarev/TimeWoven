CREATE TABLE AvatarHistory (
    avatar_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id    INTEGER NOT NULL,
    storage_path TEXT NOT NULL,
    target_year  INTEGER,
    is_current   INTEGER NOT NULL DEFAULT 0,
    source_type  TEXT NOT NULL,
    created_at   TEXT,
    metadata     TEXT,
    FOREIGN KEY (person_id) REFERENCES People(person_id)
);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE EventParticipants (
    event_id        INTEGER NOT NULL,
    person_id       INTEGER NOT NULL,
    participant_role TEXT NOT NULL,
    is_featured     INTEGER DEFAULT 0,
    added_at        TEXT,
    PRIMARY KEY (event_id, person_id, participant_role),
    FOREIGN KEY (event_id)  REFERENCES Events(event_id),
    FOREIGN KEY (person_id) REFERENCES People(person_id)
);
CREATE TABLE Events (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id       INTEGER,
    location_id     INTEGER,
    event_type      TEXT NOT NULL,
    date_start      TEXT,
    date_start_prec TEXT,
    date_end        TEXT,
    date_end_prec   TEXT,
    is_private      INTEGER NOT NULL DEFAULT 0,
    cover_asset_id  INTEGER,
    FOREIGN KEY (author_id)   REFERENCES People(person_id),
    FOREIGN KEY (location_id) REFERENCES Places(place_id)
);
CREATE TABLE Memories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  author_id INTEGER,
  event_id INTEGER,
  content_text TEXT,
  audio_url TEXT,
  transcript_verbatim TEXT,
  transcript_readable TEXT,
  emotional_tone TEXT,
  intimacy_level INTEGER DEFAULT 1,
  sensitivity_flag INTEGER DEFAULT 0,
  confidence_score REAL,
  created_at TEXT DEFAULT (datetime('now')),
  created_by INTEGER,
  source_type TEXT, parent_memory_id INTEGER REFERENCES Memories(id),
  FOREIGN KEY (author_id) REFERENCES People(person_id),
  FOREIGN KEY (event_id) REFERENCES Events(event_id),
  FOREIGN KEY (created_by) REFERENCES People(person_id)
);
CREATE TABLE MemoryPeople (
  memory_id INTEGER NOT NULL,
  person_id INTEGER NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('author', 'mentioned', 'addressee', 'subject')),
  PRIMARY KEY (memory_id, person_id, role),
  FOREIGN KEY (memory_id) REFERENCES Memories(id),
  FOREIGN KEY (person_id) REFERENCES People(person_id)
);
CREATE TABLE People (
    person_id INTEGER PRIMARY KEY AUTOINCREMENT,
    maiden_name TEXT,
    gender TEXT CHECK (gender IN ('M', 'F', 'Unknown')),
    birth_date TEXT,
    birth_date_prec TEXT CHECK (birth_date_prec IN ('EXACT', 'ABOUT', 'YEARONLY', 'DECADE')),
    death_date TEXT,
    death_date_prec TEXT CHECK (death_date_prec IN ('EXACT', 'ABOUT', 'YEARONLY', 'DECADE')),
    is_alive INTEGER NOT NULL DEFAULT 1 CHECK (is_alive IN (0, 1)),
    is_user INTEGER NOT NULL DEFAULT 0 CHECK (is_user IN (0, 1)),
    role TEXT NOT NULL DEFAULT 'placeholder' CHECK (role IN ('admin', 'author', 'relative', 'placeholder')),
    successor_id INTEGER,
    default_lang TEXT NOT NULL DEFAULT 'ru',
    phone TEXT,
    preferred_ch TEXT CHECK (preferred_ch IN ('TG', 'Email', 'Push')),
    avatar_url TEXT, pin TEXT,
    FOREIGN KEY (successor_id) REFERENCES People(person_id)
);
CREATE TABLE People_I18n (
    person_id   INTEGER NOT NULL,
    lang_code   TEXT    NOT NULL,
    first_name  TEXT    NOT NULL,
    last_name   TEXT,
    patronymic  TEXT,
    biography   TEXT,
    PRIMARY KEY (person_id, lang_code),
    FOREIGN KEY (person_id) REFERENCES People(person_id)
);
CREATE TABLE PersonRelationship (
    rel_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    person_from_id     INTEGER NOT NULL,
    person_to_id       INTEGER NOT NULL,
    relationship_type_id INTEGER NOT NULL,
    is_primary         INTEGER NOT NULL DEFAULT 1,
    valid_from         TEXT,
    valid_to           TEXT,
    comment            TEXT,
    FOREIGN KEY (person_from_id) REFERENCES People(person_id),
    FOREIGN KEY (person_to_id)   REFERENCES People(person_id),
    FOREIGN KEY (relationship_type_id) REFERENCES RelationshipType(id)
);
CREATE TABLE Places (
    place_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    country     TEXT,
    region      TEXT,
    city        TEXT,
    coordinates TEXT,
    address_raw TEXT,
    metadata    TEXT
);
CREATE TABLE Quotes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  author_id INTEGER NOT NULL,
  content_text TEXT NOT NULL,
  source_memory_id INTEGER,
  created_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (author_id) REFERENCES People(person_id),
  FOREIGN KEY (source_memory_id) REFERENCES Memories(id)
);
CREATE TABLE RelationshipType (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    code           TEXT NOT NULL,
    symmetry_type  TEXT NOT NULL,
    category       TEXT NOT NULL,
    inverse_type_id INTEGER,
    FOREIGN KEY (inverse_type_id) REFERENCES RelationshipType(id)
);
