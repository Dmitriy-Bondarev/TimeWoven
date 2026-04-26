-- Краткое резюме воспоминания (ручной ввод на /family/memory/{id}/edit)
ALTER TABLE "Memories" ADD COLUMN IF NOT EXISTS essence_text TEXT;
