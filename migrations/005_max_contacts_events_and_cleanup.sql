-- T16: Max contacts event storage + cleanup of test duplicates/memories

-- 1) New table for non-destructive contact ingestion events.
CREATE TABLE IF NOT EXISTS "MaxContactEvents" (
    id                  SERIAL PRIMARY KEY,
    created_at          VARCHAR NOT NULL,
    sender_max_user_id  VARCHAR NOT NULL,
    contact_max_user_id VARCHAR,
    contact_name        VARCHAR,
    contact_first_name  VARCHAR,
    contact_last_name   VARCHAR,
    raw_payload         TEXT NOT NULL,
    matched_person_id   INTEGER REFERENCES "People"(person_id),
    status              VARCHAR NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'matched', 'merged', 'archived'))
);

CREATE INDEX IF NOT EXISTS idx_max_contact_events_sender ON "MaxContactEvents" (sender_max_user_id);
CREATE INDEX IF NOT EXISTS idx_max_contact_events_contact ON "MaxContactEvents" (contact_max_user_id);
CREATE INDEX IF NOT EXISTS idx_max_contact_events_status ON "MaxContactEvents" (status);

-- 2) Cleanup existing People test duplicates created from contact tests.
UPDATE "People"
SET record_status = 'test_archived'
WHERE person_id IN (35, 36, 37, 38, 39);

-- 3) Cleanup existing and future TEST CONTACT marker memories.
UPDATE "Memories"
SET
    is_archived = true,
    transcription_status = 'archived',
    source_type = 'max_contact_test_marker'
WHERE
    id IN (20, 21, 22, 23, 24)
    OR (
        source_type = 'max_messenger'
        AND (
            COALESCE(content_text, '') ILIKE '%TEST CONTACT%'
            OR COALESCE(transcript_readable, '') ILIKE '%TEST CONTACT%'
        )
    );
