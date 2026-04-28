# 🗄 DB Changelog — TimeWoven

> Журнал всех изменений схемы и данных базы данных.  
> Каждая запись документирует **что** изменилось, **зачем** и **как откатить**.

## [1.8] — 2026-04-23 — T20: personaliases (разговорные имена и обращения)

**Тип:** Schema + Migration  
**Автор:** project owner  
**ADR:** —  
**Обратимость:** Reversible (`DROP TABLE IF EXISTS personaliases;`)

#### Описание

Добавлена отдельная таблица `personaliases` для хранения разговорных форм имён и обращений к персоне: родственные формы, уменьшительные, никнеймы и др. Таблица связана с `People.person_id` (FK, `ON DELETE CASCADE`), чтобы обеспечить чистку alias-ов при удалении персоны. Это подготавливает базу для более точного entity matching в AI-пайплайне.

#### Изменения

| Действие | Объект | Детали |
|----------|--------|--------|
| CREATE TABLE | `personaliases` | `id`, `person_id` FK, `alias_text`, `alias_kind`, `used_by_generation`, `note`, `created_at` |
| CREATE INDEX | `idx_personaliases_person` | ON `personaliases(person_id)` |

#### SQL

```sql
-- Forward (применение)
CREATE TABLE IF NOT EXISTS personaliases (
  id SERIAL PRIMARY KEY,
  person_id INTEGER NOT NULL REFERENCES "People"(person_id) ON DELETE CASCADE,
  alias_text VARCHAR NOT NULL,
  alias_kind VARCHAR NOT NULL CHECK (alias_kind IN (
    'kinship_term', 'nickname', 'diminutive', 'formal_with_patronymic', 'other'
  )),
  used_by_generation VARCHAR NULL CHECK (used_by_generation IN (
    'parents', 'siblings', 'children', 'grandchildren', 'other'
  )),
  note TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_personaliases_person
ON personaliases(person_id);

-- Rollback (откат)
DROP TABLE IF EXISTS personaliases;
```

#### Валидация

```sql
-- Проверка структуры
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'personaliases'
ORDER BY ordinal_position;

-- Проверка индекса
SELECT indexname
FROM pg_indexes
WHERE tablename = 'personaliases';
```

#### Затронутый код
- `migrations/007_add_person_aliases.sql` — новая миграция таблицы `PersonAliases`.
- `app/models/__init__.py` — `PersonAlias` model + relationship `Person.aliases`.
- `app/api/routes/admin.py` — API для add/delete alias + read-only alias list в `/admin/people`.
- `app/web/templates/admin/admin_people.html` — отображение alias-ов в таблице людей.

---

## [1.7] — 2026-04-23 — T18.B: Таблица max_chat_sessions

**Тип:** Schema + Migration  
**Автор:** project owner  
**ADR:** —  
**Обратимость:** Reversible (`DROP TABLE max_chat_sessions;`)

#### Описание

Добавлена таблица `max_chat_sessions` для session-слоя Max-бота (T18.B). Хранит черновики (draft_items JSON, draft_text) групп сообщений от одного max_user_id до команды финализации. При финализации создаётся `Memory(transcription_status='draft')` и запускается AI-анализ.

#### Изменения

| Действие | Объект | Детали |
|----------|--------|--------|
| CREATE TABLE | `max_chat_sessions` | id, max_user_id, person_id FK, status, created_at, updated_at, finalized_at, draft_text, draft_items (JSON), message_count, audio_count, memory_id FK, analysis_status |
| CREATE INDEX | `idx_mcs_user_status` | ON max_chat_sessions(max_user_id, status) |

---

## [1.6] — 2026-04-23 — T17: Soft-archive duplicate People 40 и 43

**Тип:** Data  
**Автор:** project owner  
**ADR:** —  
**Обратимость:** Reversible (UPDATE record_status = 'active' WHERE person_id IN (40, 43))

#### Описание

После T16 при ручной ревизии Max contact событий выявлены два дубля:
- `person_id=40` — дубль `person_id=2`; `messenger_max_id` уже вручную перенесён с 40 → 2 до начала задачи.
- `person_id=43` — дубль `person_id=8`; `messenger_max_id` уже вручную перенесён с 43 → 8 до начала задачи.

Диагностика FK показала нулевые ссылки на 40/43 во всех связанных таблицах (Memories, MemoryPeople, Quotes, PersonRelationship, Unions, UnionChildren, AvatarHistory, Events, EventParticipants, MaxContactEvents). Ребайнд не потребовался.

Записи `person_id IN (41, 42)` подтверждены как реальные новые люди: `role='relative'`, `record_status='active'`, наличие ru+en в `People_I18n`.

#### Изменения

| Действие | Объект | Детали |
|----------|--------|--------|
| UPDATE | `People.record_status` | person_id=40 → `test_archived` (дубль person_id=2) |
| UPDATE | `People.record_status` | person_id=43 → `test_archived` (дубль person_id=8) |

#### Валидация

- `live_duplicates_should_be_zero` = 0 ✅
- `active_relatives_41_42_should_be_two` = 2 ✅
- person_id=2: `messenger_max_id=40338535`, `record_status=active` ✅
- person_id=8: `messenger_max_id=82604752`, `record_status=active` ✅

---

## 2026-04-22 — Диагностика дат union (5F)

**Проблема:** API возвращал `start_date=null, end_date=null` для всех union-узлов.

**Причина 1 — устаревший процесс:** Сервис был запущен до того, как `family_graph.py` был обновлён в 5E (ModTime файла > StartTime сервиса). После перезапуска данные стали передаваться корректно.

**Причина 2 — неверный парсинг дат:** `extract_year()` в `family_graph.py` делал `split("-")[0]`, но даты хранятся как "DD.MM.YYYY". Итог: `int("06.11.1976")` → ValueError → `None` → все union всегда `is_active=True`. Исправлено: теперь функция проверяет наличие "." и делает `split(".")[-1]` для извлечения года.

**Фактические данные в БД:**
- union 1: partner1=4, partner2=3, start=06.11.1976, end=10.03.1983
- union 2: partner1=2, partner2=5, start=07.09.2007, end=31.12.2199

**Откат:** Не нужен (данные не изменялись, только логика чтения исправлена).

---

## Формат записи

```markdown
### [{VERSION}] — {YYYY-MM-DD} — {Краткое название}

**Тип:** {Schema | Data | Migration | Index | Seed}  
**Автор:** {имя}  
**ADR:** {ссылка на ADR или "—"}  
**Обратимость:** {Reversible | Irreversible | Partially reversible}

#### Описание
{Что было сделано и зачем, 2–4 предложения}

#### Изменения

| Действие   | Объект               | Детали                              |
|------------|----------------------|-------------------------------------|
| {ADD/ALTER/DROP/UPDATE} | `{table.column}` | {описание изменения}           |

#### SQL

```sql
-- Forward (применение)
{SQL-команды для применения изменений}

-- Rollback (откат)
{SQL-команды для отката}
```

#### Валидация

```sql
-- Проверка после применения
{SQL-запросы для проверки корректности}
```

#### Затронутый код
- `{file_path}` — {что изменено в коде}
```

---

## Записи

<!-- Новые записи добавляются СВЕРХУ -->

---

### [1.5] — 2026-04-23 — T16 Max contacts: event inbox + cleanup duplicate people/memories

**Тип:** Schema + Data
**Автор:** GitHub Copilot
**ADR:** —
**Обратимость:** Partially reversible

#### Описание

Отключено авто-создание `People` из входящих Max contact attachments: теперь контакты фиксируются в новой таблице `MaxContactEvents` как enrichment events. Выполнен cleanup тестовых дублей и служебных marker-memories без удаления данных.

#### Изменения

| Действие | Объект | Детали |
|----------|--------|--------|
| ADD | `MaxContactEvents` | Inbox таблица contact events (`new|matched|merged|archived`) |
| ADD | `idx_max_contact_events_*` | Индексы по `sender_max_user_id`, `contact_max_user_id`, `status` |
| UPDATE | `People.record_status` | `person_id IN (35,36,37,38,39) -> test_archived` |
| UPDATE | `Memories` | `id IN (20..24)` и future `TEST CONTACT` markers -> `is_archived=true`, `transcription_status='archived'`, `source_type='max_contact_test_marker'` |

#### SQL

```sql
-- Forward
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

UPDATE "People"
SET record_status = 'test_archived'
WHERE person_id IN (35, 36, 37, 38, 39);

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

-- Rollback (data rollback partial by design)
DROP INDEX IF EXISTS idx_max_contact_events_sender;
DROP INDEX IF EXISTS idx_max_contact_events_contact;
DROP INDEX IF EXISTS idx_max_contact_events_status;
DROP TABLE IF EXISTS "MaxContactEvents";

UPDATE "People"
SET record_status = 'active'
WHERE person_id IN (35, 36, 37, 38, 39);
```

#### Валидация

```sql
SELECT person_id, record_status
FROM "People"
WHERE person_id IN (35, 36, 37, 38, 39)
ORDER BY person_id;

SELECT id, is_archived, transcription_status, source_type
FROM "Memories"
WHERE id IN (20, 21, 22, 23, 24)
ORDER BY id;

SELECT count(*) FROM "MaxContactEvents";
```

#### Затронутый код
- `migrations/005_max_contacts_events_and_cleanup.sql`
- `app/api/routes/bot_webhooks.py`
- `app/services/memory_store.py`
- `app/models/__init__.py`
- `app/api/routes/tree.py`
- `app/services/family_graph.py`
- `create_postgres_schema.sql`
- `tech-docs/DATABASE_SCHEMA.md`

### [1.4] — 2026-04-23 — Person.record_status и скрытие test_archived в live UX

**Тип:** Schema + Data
**Автор:** GitHub Copilot
**ADR:** —
**Обратимость:** Reversible

#### Описание

В таблицу `People` добавлено поле `record_status` с дефолтным значением `active` и CHECK-ограничением на значения `active|archived|test_archived`. В рамках T14 выполнен data patch: персоны с `person_id IN (20,21,22,23)` переведены в `test_archived` для скрытия из live family UX при сохранении доступности в админке.

#### Изменения

| Действие | Объект | Детали |
|----------|--------|--------|
| ADD | `People.record_status` | `VARCHAR NOT NULL DEFAULT 'active'` |
| ALTER | `People` | Добавлен CHECK `people_record_status_check` |
| UPDATE | `People.record_status` | `person_id IN (20,21,22,23) -> 'test_archived'` |

#### SQL

```sql
-- Forward
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

-- Rollback
UPDATE "People"
SET record_status = 'active'
WHERE person_id IN (20, 21, 22, 23);

ALTER TABLE "People" DROP CONSTRAINT IF EXISTS people_record_status_check;
ALTER TABLE "People" DROP COLUMN IF EXISTS record_status;
```

#### Валидация

```sql
SELECT person_id, record_status
FROM "People"
WHERE person_id IN (20, 21, 22, 23)
ORDER BY person_id;

SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = '"People"'::regclass
  AND conname = 'people_record_status_check';
```

#### Затронутый код
- `migrations/004_add_record_status_to_people.sql` — schema + data migration.
- `app/models/__init__.py` — поле `Person.record_status`.
- `create_postgres_schema.sql` — синхронизация эталонного DDL.
- `tech-docs/DATABASE_SCHEMA.md` — синхронизация документации схемы.

### [1.3] — 2026-04-22 — Поддержка канала Max в People.preferred_ch

**Тип:** Schema
**Автор:** GitHub Copilot
**ADR:** —
**Обратимость:** Reversible

#### Описание

Для админ-формы создания персоны добавлена поддержка канала `Max` как значения `People.preferred_ch`, а также явное значение `None` для случая «канал не задан». Это необходимо, чтобы сохранение персоны с Max-контактом не нарушало CHECK-ограничение.

#### Изменения

| Действие | Объект | Детали |
|----------|--------|--------|
| ALTER | `People.preferred_ch` | CHECK обновлён на `('Max', 'TG', 'Email', 'Push', 'None')` |

#### SQL

```sql
-- Forward
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

-- Rollback
ALTER TABLE "People" DROP CONSTRAINT IF EXISTS people_preferred_ch_check;
ALTER TABLE "People"
ADD CONSTRAINT people_preferred_ch_check
CHECK (preferred_ch IN ('TG', 'Email', 'Push'));
```

#### Валидация

```sql
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = '"People"'::regclass
  AND pg_get_constraintdef(oid) ILIKE '%preferred_ch%';
```

#### Затронутый код
- `migrations/003_expand_preferred_channel_for_max.sql` — миграция CHECK для `preferred_ch`.
- `create_postgres_schema.sql` — синхронизирован эталон DDL.
- `docs/DATABASE_SCHEMA.md` — синхронизирована документация схемы.

### [1.2] — 2026-04-19 — Перенос на PostgreSQL v1.3 и фикс Quote.id

**Тип:** Schema + Data  
**Автор:** Дмитрий Бондарев  
**ADR:** —  
**Обратимость:** Reversible (через бэкап схемы и данных)

#### Описание

Фиксация состояния БД после перехода на PostgreSQL: устранена ошибка `IntegrityError` при сохранении ответов семьи из-за отсутствия автоинкремента на первичном ключе `Quote.id`, проверены связи `Memory.author_id → Person.person_id → PersonI18n`, зафиксированы фактические counts по ключевым таблицам. Цель — стабилизировать базу под продовый контур и гарантировать корректную работу семейных ответов. [cite:29]

#### Изменения

| Действие | Объект            | Детали                                                                 |
|----------|-------------------|------------------------------------------------------------------------|
| ALTER    | `Quotes.id`       | Установка `PRIMARY KEY` c автоинкрементом (sequence / IDENTITY)       |
| CHECK    | `Person`/`Memory` | Проверка связей `Memory.author_id → Person.person_id → PersonI18n`    |
| CHECK    | Counts            | Проверка текущих counts: `Person = 9`, `Memory = 9`                    |

#### SQL

> Ниже — концептуальная SQL-модель для PostgreSQL; фактическая реализация зависит от текущего определения `Quotes.id`.

```sql
-- 1. Создать sequence для Quotes.id, если её ещё нет
CREATE SEQUENCE IF NOT EXISTS quotes_id_seq OWNED BY "Quotes".id;

-- 2. Привязать sequence как DEFAULT для id
ALTER TABLE "Quotes"
    ALTER COLUMN id SET DEFAULT nextval('quotes_id_seq');

-- 3. Выставить sequence на максимальное существующее значение
SELECT setval('quotes_id_seq', COALESCE(MAX(id), 1)) FROM "Quotes";
```

```sql
-- Rollback (идейный)
-- Вариант отката только DEFAULT и sequence, без удаления данных:

-- 1. Убрать DEFAULT:
-- ALTER TABLE "Quotes" ALTER COLUMN id DROP DEFAULT;

-- 2. По необходимости удалить sequence:
-- DROP SEQUENCE IF EXISTS quotes_id_seq;

-- Первичный ключ на id обычно не откатывается, так как он логически необходим.
```

#### Валидация

```sql
-- 1) Проверка: новые INSERT в Quotes не падают по PK и DEFAULT срабатывает
BEGIN;
INSERT INTO "Quotes" (content, author_id, memory_id, created_at)
VALUES ('_db_changelog_test_', 1, 1, now());
ROLLBACK;

-- 2) Проверка counts по основным таблицам
SELECT COUNT(*) AS persons_count  FROM "Person";
SELECT COUNT(*) AS memories_count FROM "Memory";

-- 3) Проверка: все Memory.author_id указывают на существующий Person
SELECT COUNT(*) AS broken_author_refs
FROM "Memory" m
LEFT JOIN "Person" p ON m.author_id = p.person_id
WHERE m.author_id IS NOT NULL AND p.person_id IS NULL;
```

#### Затронутый код

- `app/models/__init__.py` — модель `Quote`: поле `id` с `primary_key=True, autoincrement=True`.  
- `app/api/routes/tree.py` — сохранение ответов семьи в таблицу `Quotes`. [cite:29]

---

### [1.1] — 2026-04-17 — Temporal normalization v1 (PersonRelationship)

**Тип:** Data  
**Автор:** Дмитрий Бондарев  
**ADR:** —  
**Обратимость:** Partially reversible

#### Описание

Нормализация временной модели связей в таблице `person_relationships` на продовом PostgreSQL: устранены `NULL` в `valid_to`, `valid_from` для родительско‑детских связей согласован с датой рождения ребёнка, браки обрезаны по дате смерти участников, если она известна. Цель — сделать модель связей временно консистентной и пригодной для запросов вида «состояние семьи на дату» через интервал `[valid_from, valid_to)`. [cite:31]

#### Изменения

| Действие | Объект                                  | Детали                                                                 |
|----------|-----------------------------------------|------------------------------------------------------------------------|
| UPDATE   | `person_relationships.valid_to`         | Заменить `NULL` на `'9999-12-31'` для всех связей                      |
| UPDATE   | `person_relationships.valid_from`       | Заполнить из `people.birth_date` для типов `bioparent` и `child`       |
| UPDATE   | `person_relationships.valid_to`         | Для `spouselegal` обрезать по дате смерти одного из супругов           |

#### SQL

> Ниже — концептуальные SQL-скрипты; в реальности операции выполнялись в несколько шагов с dry‑run‑проверками. [cite:31]

```sql
-- 1. Проставить открытый конец интервала для всех NULL
UPDATE person_relationships
SET valid_to = '9999-12-31'
WHERE valid_to IS NULL;

-- 2. Синхронизировать valid_from для bioparent (type 1)
UPDATE person_relationships pr
SET valid_from = p.birth_date
FROM people p
WHERE pr.relationship_type_id = 1          -- bioparent
  AND pr.person_to_id = p.id               -- ребёнок = person_to_id
  AND pr.valid_from IS NULL
  AND p.birth_date IS NOT NULL;

-- 3. Синхронизировать valid_from для child (type 2)
UPDATE person_relationships pr
SET valid_from = p.birth_date
FROM people p
WHERE pr.relationship_type_id = 2          -- child
  AND pr.person_from_id = p.id             -- ребёнок = person_from_id
  AND pr.valid_from IS NULL
  AND p.birth_date IS NOT NULL;

-- 4. Зафиксировать биологическое родство как "вечное" (9999-12-31)
UPDATE person_relationships
SET valid_to = '9999-12-31'
WHERE relationship_type_id IN (1, 2);      -- bioparent, child

-- 5. Нормализация браков по дате смерти (spouselegal)
UPDATE person_relationships pr
SET valid_to = new_new_valid_to::text
FROM (
    SELECT
        pr.id,
        LEAST(
            COALESCE(NULLIF(pr.valid_to, '')::date, DATE '9999-12-31'),
            COALESCE(pf.death_date, DATE '9999-12-31'),
            COALESCE(pt.death_date, DATE '9999-12-31')
        ) AS new_new_valid_to
    FROM person_relationships pr
    JOIN people pf ON pf.id = pr.person_from_id
    JOIN people pt ON pt.id = pr.person_to_id
    WHERE pr.relationship_type_id = 3      -- spouselegal
) AS t
WHERE pr.id = t.id;
```

```sql
-- Rollback (идейный, частично возможен только из бэкапа)
-- 1. Восстановление valid_to/valid_from требует заранее сохранённого снимка:
--    CREATE TABLE pr_snapshot_2026_04_17 AS
--      SELECT id, valid_from, valid_to FROM person_relationships;
--
-- 2. Откат к снимку:
-- UPDATE person_relationships pr
-- SET valid_from = s.valid_from,
--     valid_to   = s.valid_to
-- FROM pr_snapshot_2026_04_17 s
-- WHERE pr.id = s.id;
--
-- При отсутствии снимка откат считается практически невозможным (Irreversible).
```

#### Валидация

```sql
-- 1) Проверка: больше нет NULL в valid_to
SELECT COUNT(*) AS null_valid_to_count
FROM person_relationships
WHERE valid_to IS NULL;

-- 2) Проверка: bioparent/child согласованы с датой рождения ребёнка
SELECT pr.id, pr.relationship_type_id, pr.valid_from, p.birth_date
FROM person_relationships pr
JOIN people p
  ON (pr.relationship_type_id = 1 AND pr.person_to_id   = p.id)
  OR (pr.relationship_type_id = 2 AND pr.person_from_id = p.id)
WHERE p.birth_date IS NOT NULL
  AND pr.valid_from <> p.birth_date;

-- 3) Проверка: spouselegal не выходят за рамки даты смерти
SELECT pr.id, pr.valid_to, pf.death_date AS from_death, pt.death_date AS to_death
FROM person_relationships pr
JOIN people pf ON pf.id = pr.person_from_id
JOIN people pt ON pt.id = pr.person_to_id
WHERE pr.relationship_type_id = 3
  AND (
        (pf.death_date IS NOT NULL AND pr.valid_to::date > pf.death_date)
     OR (pt.death_date IS NOT NULL AND pr.valid_to::date > pt.death_date)
  );
```

#### Затронутый код

- Логика чтения/запросов PersonRelationship в сервисах и будущих репозиториях (интервалы `[valid_from, valid_to)`). [cite:31]

---

### [1.0] — 2026-04-15 — Введение Union / UnionChildren и нормализация семьи

**Тип:** Schema + Data  
**Автор:** Дмитрий Бондарев  
**ADR:** —  
**Обратимость:** Reversible (через сохранённые схемный/табличный снимки)

#### Описание

Начата нормализация структуры базы данных: выделены сущности `Union` (союз/брак) и `UnionChildren` (дети союза), а также приведены данные к новой модели. Цель — перейти от «голых» связей между людьми к архитектуре Person / Union / Memory / Event / Relationship и корректно моделировать семью через союзы родителей и их детей. [cite:31]

#### Изменения

| Действие | Объект           | Детали                                                      |
|----------|------------------|-------------------------------------------------------------|
| SNAPSHOT | `db_schema`      | Схема сохранена в `db_schema_before.sql`                    |
| SNAPSHOT | `db_tables`      | Список таблиц в `db_tables_before.txt`                      |
| CREATE   | `unions`         | `partner1_id`, `partner2_id`, `start_date`, `end_date`      |
| CREATE   | `union_children` | `union_id`, `child_id`                                      |
| DATA     | `unions`         | Построение союзов по связям `spouse*`                       |
| DATA     | `union_children` | Построение детей союзов + ручная чистка                     |
| DATA     | `person_relationships` | Удаление ошибочных связей (внуки как дети)     |

#### SQL

> Структура и данные строились скриптом; ниже — логика в SQL-псевдокоде. [cite:31]

```sql
-- Снимки состояния до изменений (выполнено вручную, MacBook)
-- Схема:
--   .output db_schema_before.sql
--   .schema
-- Таблицы:
--   .output db_tables_before.txt
--   .tables

-- 1. Таблица unions (структура)
CREATE TABLE unions (
    id          SERIAL PRIMARY KEY,
    partner1_id INTEGER NOT NULL REFERENCES people(id),
    partner2_id INTEGER NOT NULL REFERENCES people(id),
    start_date  DATE,
    end_date    DATE
);

-- 2. Таблица union_children (структура)
CREATE TABLE union_children (
    id       SERIAL PRIMARY KEY,
    union_id INTEGER NOT NULL REFERENCES unions(id),
    child_id INTEGER NOT NULL REFERENCES people(id)
);

-- 3. Построение Union по связям spouselegal / spousecommon (псевдокод)
--   INSERT INTO unions (partner1_id, partner2_id, start_date, end_date)
--   SELECT DISTINCT
--       LEAST(pr.person_from_id, pr.person_to_id) AS partner1_id,
--       GREATEST(pr.person_from_id, pr.person_to_id) AS partner2_id,
--       NULL::date AS start_date,
--       NULL::date AS end_date
--   FROM person_relationships pr
--   WHERE pr.relationship_type_id IN (3,4); -- spouselegal/spousecommon

-- 4. Построение UnionChildren по связям parent/child (псевдокод)
--   INSERT INTO union_children (union_id, child_id)
--   SELECT
--       u.id AS union_id,
--       c.id AS child_id
--   FROM unions u
--   JOIN person_relationships pr ON
--       pr.relationship_type_id IN (1,2) -- bioparent/child
--       AND (pr.person_from_id = u.partner1_id OR pr.person_from_id = u.partner2_id
--            OR pr.person_to_id = u.partner1_id OR pr.person_to_id = u.partner2_id)
--   JOIN people c ON
--       (pr.relationship_type_id = 1 AND pr.person_to_id   = c.id) OR
--       (pr.relationship_type_id = 2 AND pr.person_from_id = c.id);
```

```sql
-- Rollback (идейный)
-- 1. Удалить union_children:
-- DROP TABLE IF EXISTS union_children;
--
-- 2. Удалить unions:
-- DROP TABLE IF EXISTS unions;
--
-- 3. По необходимости восстановить схему/данные из db_schema_before.sql и db_tables_before.txt.
```

#### Валидация

```sql
-- 1) unions созданы и содержат пары партнёров
SELECT COUNT(*) AS unions_count FROM unions;

-- 2) union_children содержит ожидаемое число записей
SELECT COUNT(*) AS union_children_count FROM union_children;

-- 3) Проверка отсутствия "детей без союза"
SELECT COUNT(*) AS children_without_union
FROM person_relationships pr
WHERE pr.relationship_type_id IN (1,2)
  AND NOT EXISTS (
      SELECT 1
      FROM union_children uc
      WHERE uc.child_id IN (pr.person_from_id, pr.person_to_id)
  );
```

#### Затронутый код

- Модели и сервисы, работающие с Union / UnionChildren (семейный граф, таймлайн).