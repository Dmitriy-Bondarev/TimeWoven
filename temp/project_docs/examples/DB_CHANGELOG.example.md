# 🗄 DB Changelog — TimeWoven

> Журнал всех изменений схемы и данных базы данных.
> Каждая запись документирует **что** изменилось, **зачем** и **как откатить**.

---

<!-- Новые записи добавляются СВЕРХУ -->

### [1.2] — 2026-04-17 — Temporal Normalization v1: Union → Spouse Relationships

**Тип:** Data
**Автор:** Дмитрий Бондарев
**ADR:** [ADR-002](docs/adr/ADR-002.md)
**Обратимость:** Reversible

#### Описание

Заполнение `valid_from` и `valid_to` для spouse-связей на основе данных из таблицы `unions`. `start_date` союза копируется в `valid_from`, `end_date` (если есть) — в `valid_to` соответствующих PersonRelationship с типом `spouse`.

#### Изменения

| Действие | Объект                            | Детали                                      |
|----------|-----------------------------------|---------------------------------------------|
| UPDATE   | `person_relationships.valid_from` | Заполнить из `unions.start_date` для spouse  |
| UPDATE   | `person_relationships.valid_to`   | Заполнить из `unions.end_date` для spouse    |

#### SQL

```sql
-- Forward (применение)
UPDATE person_relationships pr
SET valid_from = u.start_date
FROM unions u
WHERE pr.relationship_type = 'spouse'
  AND (
    (pr.person_id = u.partner_1_id AND pr.related_person_id = u.partner_2_id)
    OR
    (pr.person_id = u.partner_2_id AND pr.related_person_id = u.partner_1_id)
  )
  AND u.start_date IS NOT NULL;

UPDATE person_relationships pr
SET valid_to = u.end_date
FROM unions u
WHERE pr.relationship_type = 'spouse'
  AND (
    (pr.person_id = u.partner_1_id AND pr.related_person_id = u.partner_2_id)
    OR
    (pr.person_id = u.partner_2_id AND pr.related_person_id = u.partner_1_id)
  )
  AND u.end_date IS NOT NULL;

-- Rollback (откат)
UPDATE person_relationships
SET valid_from = NULL, valid_to = NULL
WHERE relationship_type = 'spouse'
  AND (valid_from IS NOT NULL OR valid_to IS NOT NULL);
```

#### Валидация

```sql
-- Проверка: все spouse-связи с union должны иметь valid_from
SELECT pr.id, p1.full_name, p2.full_name, pr.valid_from, pr.valid_to
FROM person_relationships pr
JOIN people p1 ON pr.person_id = p1.id
JOIN people p2 ON pr.related_person_id = p2.id
WHERE pr.relationship_type = 'spouse'
ORDER BY pr.valid_from;

-- Проверка: нет расхождений с unions
SELECT u.id AS union_id, u.start_date, u.end_date,
       pr.valid_from, pr.valid_to
FROM unions u
JOIN person_relationships pr
  ON pr.relationship_type = 'spouse'
  AND (
    (pr.person_id = u.partner_1_id AND pr.related_person_id = u.partner_2_id)
    OR
    (pr.person_id = u.partner_2_id AND pr.related_person_id = u.partner_1_id)
  )
WHERE u.start_date != pr.valid_from
   OR (u.end_date IS NOT NULL AND u.end_date != pr.valid_to);
```

#### Затронутый код
- `app/models/relationship.py` — добавлены поля `valid_from`, `valid_to` в модель
- `app/services/union_service.py` — логика синхронизации дат при создании/обновлении Union

---

### [1.1] — 2026-04-17 — Temporal Normalization v1: Death Date Propagation

**Тип:** Data
**Автор:** Дмитрий Бондарев
**ADR:** [ADR-002](docs/adr/ADR-002.md)
**Обратимость:** Reversible

#### Описание

Заполнение `valid_to` для всех активных связей персон, у которых указана `death_date`. Если персона умерла, все её связи получают `valid_to = death_date`.

#### Изменения

| Действие | Объект                            | Детали                                          |
|----------|-----------------------------------|-------------------------------------------------|
| UPDATE   | `person_relationships.valid_to`   | Установить death_date для связей умерших персон  |

#### SQL

```sql
-- Forward
UPDATE person_relationships pr
SET valid_to = p.death_date
FROM people p
WHERE pr.person_id = p.id
  AND p.death_date IS NOT NULL
  AND pr.valid_to IS NULL;

-- Rollback
-- ВНИМАНИЕ: откат невозможен без сохранения предыдущего состояния.
-- Перед выполнением forward-скрипта был сделан снимок:
-- SELECT id, valid_to FROM person_relationships WHERE valid_to IS NULL;
-- Для отката: восстановить valid_to = NULL для записей из снимка.
```

#### Валидация

```sql
-- Проверка: у всех умерших персон связи имеют valid_to
SELECT p.full_name, p.death_date, pr.valid_to
FROM people p
JOIN person_relationships pr ON pr.person_id = p.id
WHERE p.death_date IS NOT NULL
  AND pr.valid_to IS NULL;
-- Ожидаемый результат: 0 строк
```

#### Затронутый код
- `app/models/relationship.py` — поля `valid_from: Date`, `valid_to: Date` (nullable)

---

### [1.0] — 2026-04-16 — Миграция SQLite → PostgreSQL

**Тип:** Migration
**Автор:** Дмитрий Бондарев
**ADR:** [ADR-001](docs/adr/ADR-001.md)
**Обратимость:** Reversible (архив SQLite сохранён)

#### Описание

Полная миграция данных из SQLite (`family.db`) в PostgreSQL 14. Создана база `timewoven`, пользователь `timewoven_user` с password-аутентификацией через TCP. Структура таблиц перенесена один-в-один, данные импортированы через Python-скрипт.

#### Изменения

| Действие | Объект                    | Детали                                             |
|----------|---------------------------|----------------------------------------------------|
| CREATE   | Database `timewoven`      | Основная база данных                                |
| CREATE   | User `timewoven_user`     | Сервисный пользователь с GRANT ALL на `timewoven`   |
| MIGRATE  | Все таблицы               | people, person_relationships, unions, memories и др. |
| CONFIG   | `pg_hba.conf`             | Password auth для timewoven_user через TCP (md5)     |

#### SQL

```sql
-- Forward
CREATE DATABASE timewoven;
CREATE USER timewoven_user WITH PASSWORD '***';
GRANT ALL PRIVILEGES ON DATABASE timewoven TO timewoven_user;

-- Таблицы создаются автоматически через SQLAlchemy metadata.create_all()
-- Данные импортированы через migrate_sqlite_to_pg.py

-- Rollback
-- 1. Остановить сервис: systemctl stop timewoven
-- 2. Вернуть DATABASE_URL в .env на sqlite:///family.db
-- 3. Перезапустить: systemctl start timewoven
-- Архив SQLite: /root/projects/TimeWoven/backups/family.db.2026-04-16
```

#### Валидация

```sql
-- Сверка количества записей
SELECT 'people' AS tbl, COUNT(*) FROM people
UNION ALL
SELECT 'person_relationships', COUNT(*) FROM person_relationships
UNION ALL
SELECT 'unions', COUNT(*) FROM unions;
```

#### Затронутый код
- `.env` — `DATABASE_URL` изменён на `postgresql+psycopg2://...`
- `app/config.py` — без изменений (читает DATABASE_URL из .env)
- `app/models/*.py` — без изменений (SQLAlchemy dialect-agnostic)

---

> **Правила ведения журнала:**
>
> 1. Каждое изменение схемы или массовое обновление данных — отдельная запись
> 2. Новые записи добавляются **сверху** (в обратном хронологическом порядке)
> 3. Версия = `{major}.{minor}` — мажорная при структурных изменениях, минорная при data-патчах
> 4. SQL всегда включает и forward, и rollback (если откат возможен)
> 5. После каждого применения выполняется валидационный запрос
