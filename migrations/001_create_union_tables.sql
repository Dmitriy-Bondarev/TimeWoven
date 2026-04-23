-- Миграция для создания таблиц Unions и UnionChildren в схеме, соответствующей текущей БД.
-- В существующей БД уже есть таблицы Unions и UnionChildren с полями partner1_id/partner2_id и child_id.

-- ============ Таблица Unions ============
CREATE TABLE IF NOT EXISTS "Unions" (
    id SERIAL PRIMARY KEY,
    partner1_id INTEGER REFERENCES "People"(person_id) ON DELETE SET NULL,
    partner2_id INTEGER REFERENCES "People"(person_id) ON DELETE SET NULL,
    start_date VARCHAR(10),
    end_date VARCHAR(10)
);

-- ============ Таблица UnionChildren ============
CREATE TABLE IF NOT EXISTS "UnionChildren" (
    id SERIAL PRIMARY KEY,
    union_id INTEGER NOT NULL REFERENCES "Unions"(id) ON DELETE CASCADE,
    child_id INTEGER NOT NULL REFERENCES "People"(person_id) ON DELETE CASCADE,
    UNIQUE(union_id, child_id)
);

-- ============ Индексы для производительности ============
CREATE INDEX IF NOT EXISTS idx_unions_partner1_id ON "Unions"(partner1_id);
CREATE INDEX IF NOT EXISTS idx_unions_partner2_id ON "Unions"(partner2_id);
CREATE INDEX IF NOT EXISTS idx_union_children_union_id ON "UnionChildren"(union_id);
CREATE INDEX IF NOT EXISTS idx_union_children_child_id ON "UnionChildren"(child_id);

-- ============ Комментарии ============
COMMENT ON TABLE "Unions" IS 'Представляет браки, партнёрства, союзы между людьми';
COMMENT ON TABLE "UnionChildren" IS 'Связь между Union и Person (дети)';
COMMENT ON COLUMN "Unions".union_type IS 'Тип союза: legal, civil, partnership и т.п.';
COMMENT ON COLUMN "Unions".start_date IS 'Дата начала союза (YYYY-MM-DD)';
COMMENT ON COLUMN "Unions".end_date IS 'Дата конца союза (YYYY-MM-DD)';
COMMENT ON COLUMN "UnionChildren".child_id IS 'Person.person_id ребёнка';
