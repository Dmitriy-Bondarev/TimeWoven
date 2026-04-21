-- Add archive flag for timeline filtering.
ALTER TABLE "Memories"
ADD COLUMN IF NOT EXISTS is_archived BOOLEAN NOT NULL DEFAULT FALSE;
