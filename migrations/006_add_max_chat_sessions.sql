-- Migration 006: Add max_chat_sessions table
-- Date: 2026-04-23
-- Task: T18.B — Max chat sessions + draft aggregation
-- Rollback: DROP TABLE max_chat_sessions;

CREATE TABLE IF NOT EXISTS max_chat_sessions (
    id            SERIAL        PRIMARY KEY,
    max_user_id   VARCHAR       NOT NULL,
    person_id     INTEGER       REFERENCES "People"(person_id) ON DELETE SET NULL,
    status        VARCHAR       NOT NULL DEFAULT 'open',    -- open | finalized | abandoned
    created_at    VARCHAR       NOT NULL,
    updated_at    VARCHAR       NOT NULL,
    finalized_at  VARCHAR,
    draft_text    TEXT,                                     -- concatenated text items
    draft_items   TEXT,                                     -- JSON array of {type,text/audio_url,local_path,...}
    message_count INTEGER       NOT NULL DEFAULT 0,
    audio_count   INTEGER       NOT NULL DEFAULT 0,
    memory_id     INTEGER       REFERENCES "Memories"(id) ON DELETE SET NULL,  -- set on finalize
    analysis_status VARCHAR                                 -- ok | error | skipped | null
);

CREATE INDEX IF NOT EXISTS idx_mcs_user_status ON max_chat_sessions (max_user_id, status);
