-- Add lifecycle-like record status for People and mark known test records.
ALTER TABLE "People"
ADD COLUMN IF NOT EXISTS record_status VARCHAR NOT NULL DEFAULT 'active';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'people_record_status_check'
      AND conrelid = '"People"'::regclass
  ) THEN
    ALTER TABLE "People"
    ADD CONSTRAINT people_record_status_check
    CHECK (record_status IN ('active', 'archived', 'test_archived'));
  END IF;
END $$;

UPDATE "People"
SET record_status = 'active'
WHERE record_status IS NULL;

UPDATE "People"
SET record_status = 'test_archived'
WHERE person_id IN (20, 21, 22, 23);
