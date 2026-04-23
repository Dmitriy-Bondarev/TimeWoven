-- Allow Max and None values in People.preferred_ch

DO $$
DECLARE con RECORD;
BEGIN
  FOR con IN
    SELECT conname
    FROM pg_constraint
    WHERE conrelid = '"People"'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) ILIKE '%preferred_ch%'
  LOOP
    EXECUTE format('ALTER TABLE "People" DROP CONSTRAINT %I', con.conname);
  END LOOP;
END $$;

ALTER TABLE "People"
ADD CONSTRAINT people_preferred_ch_check
CHECK (preferred_ch IN ('Max', 'TG', 'Email', 'Push', 'None'));
