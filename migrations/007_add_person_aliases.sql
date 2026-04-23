-- Migration 007: Add personaliases table
-- Date: 2026-04-23
-- Task: T20 — Person aliases (conversational names and kinship forms)
-- Rollback: DROP TABLE IF EXISTS personaliases;

CREATE TABLE IF NOT EXISTS personaliases (
    id SERIAL PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES "People"(person_id) ON DELETE CASCADE,
    alias_text VARCHAR NOT NULL,
    alias_kind VARCHAR NOT NULL CHECK (alias_kind IN (
        'kinship_term',
        'nickname',
        'diminutive',
        'formal_with_patronymic',
        'other'
    )),
    used_by_generation VARCHAR NULL CHECK (used_by_generation IN (
        'parents', 'siblings', 'children', 'grandchildren', 'other'
    )),
    note TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_personaliases_person
ON personaliases(person_id);
