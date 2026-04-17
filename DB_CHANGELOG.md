# 🗄 DB Changelog — TimeWoven

> Журнал всех изменений схемы и данных базы данных.  
> Каждая запись документирует **что** изменилось, **зачем** и **как откатить**.

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

### [1.1] — 2026-04-17 — Temporal normalization v1 (PersonRelationship)

**Тип:** Data  
**Автор:** Дмитрий Бондарев  
**ADR:** —  
**Обратимость:** Partially reversible

#### Описание

Нормализация временной модели связей в таблице `person_relationships` на продовом PostgreSQL: устранены `NULL` в `valid_to`, `valid_from` для родительско‑детских связей согласован с датой рождения ребёнка, браки обрезаны по дате смерти участников, если она известна. Цель — сделать модель связей временно консистентной и пригодной для запросов вида «состояние семьи на дату» через интервал `[valid_from, valid_to)`.

#### Изменения

| Действие | Объект                                  | Детали                                                                 |
|----------|-----------------------------------------|------------------------------------------------------------------------|
| UPDATE   | `person_relationships.valid_to`         | Заменить `NULL` на `'9999-12-31'` для всех связей                      |
| UPDATE   | `person_relationships.valid_from`       | Заполнить из `people.birth_date` для типов `bioparent` и `child`       |
| UPDATE   | `person_relationships.valid_to`         | Для `spouselegal` обрезать по дате смерти одного из супругов           |

#### SQL

> Ниже — концептуальные SQL-скрипты; в реальности операции выполнялись в несколько шагов с dry‑run‑проверками.

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
-- valid_to хранится как текст, поэтому работаем через ::date
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
--    до применения изменений нужно было сделать:
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

- `app/models/relationship.py` — использование полей `valid_from` / `valid_to` как датовых строк.
- (план) сервисы/репозитории, использующие фильтрацию по интервалу `[valid_from, valid_to)`.

---

### [1.0] — 2026-04-15 — Введение Union / UnionChildren и нормализация семьи

**Тип:** Schema + Data  
**Автор:** Дмитрий Бондарев  
**ADR:** —  
**Обратимость:** Reversible (через сохранённые схемный/табличный снимки)

#### Описание

Начата нормализация структуры базы данных: выделены сущности `Union` (союз/брак) и `UnionChildren` (дети союза), а также приведены данные к новой модели. Цель — перейти от «голых» связей между людьми к архитектуре Person / Union / Memory / Event / Relationship и корректно моделировать семью через союзы родителей и их детей.

#### Изменения

| Действие | Объект          | Детали                                                      |
|----------|-----------------|-------------------------------------------------------------|
| SNAPSHOT | `db_schema`     | Схема сохранена в `db_schema_before.sql`                    |
| SNAPSHOT | `db_tables`     | Список таблиц в `db_tables_before.txt`                      |
| CREATE   | `unions`        | `partner1_id`, `partner2_id`, `start_date`, `end_date`      |
| CREATE   | `union_children`| `union_id`, `child_id`                                      |
| DATA     | `unions`        | Автоматическое построение союзов по связям `spouse*`        |
| DATA     | `union_children`| Автоматическое заполнение детей союзов + ручная чистка      |
| DATA     | `person_relationships` | Удаление ошибочных связей (внуки как дети)     |

#### SQL

> Структура и данные строились скриптом; ниже — логика в SQL-псевдокоде.

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

-- 3. Построение Union по связям spouselegal / spousecommon
-- (псевдокод: каждая уникальная пара супругов -> один Union)

-- 