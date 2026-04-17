# Технический паспорт: TimeWoven v1.3

## Стек
- Backend: Python 3.x, FastAPI, Uvicorn
- Database: PostgreSQL 14 (основная БД с 2026-04-17)
- Database legacy: SQLite (family_actual.db — архивная копия)
- Frontend: Jinja2 Templates
- Инфраструктура: Ubuntu 22.04, Nginx, Certbot, Systemd
- Сервер: 193.187.95.221
- Git: github.com/Dmitriy-Bondarev/TimeWoven

## Структура проекта
- /root/projects/TimeWoven — корень проекта
- /root/projects/TimeWoven/app/ — FastAPI приложение
- /root/projects/TimeWoven/data/db/ — SQLite архивы
- /root/projects/TimeWoven/backups/ — резервные копии
- /static/images/avatars/ — аватары
- /static/images/uploads/ — загрузки
- Документация: iCloud Drive -> 010_Business/020_TimeWoven/Docs/

## PostgreSQL
- Host: localhost:5432
- Database: timewoven
- User: timewoven_user
- URL: postgresql+psycopg2://timewoven_user:***@localhost:5432/timewoven

## Таблицы (13)
- People: 9 записей
- People_I18n: 18 записей
- Events: 6 записей
- Memories: 3 записи
- MemoryPeople: 16 записей
- Quotes: 3 записи
- AvatarHistory: 4 записи
- RelationshipType: 12 записей
- PersonRelationship: 26 записей
- Unions: 2 записи
- UnionChildren: 5 записей
- Places: пусто
- EventParticipants: пусто

## Доменная модель
- Графовая модель связей (PersonRelationship)
- Union-модель семьи (Unions + UnionChildren)
- Золотая запись (Source of Truth) через администратора
- ИИ как гипотеза (Review Dashboard)

### Временная модель связей (valid_from / valid_to)

В таблице `PersonRelationship` поля `valid_from` и `valid_to` описывают период действия связи между людьми (биологическое родство, брак и др.). Мы используем valid‑time модель: храним, когда факт считается верным в реальном мире.

**Общие правила**

- `valid_from` — дата, с которой связь считается действующей.
- `valid_to` — дата, до которой связь действовала (интервал `[from, to)`).
- Для открытых (актуальных) связей `valid_to` заполняется как `9999-12-31`, а не оставляется `NULL`, чтобы запросы по интервалу были однозначными:

  ```sql
  WHERE valid_from <= :date
    AND valid_to   >  :date
  ```

#### Родительско‑детские связи (bioparent / child)

Семантика:

- `relationship_type_id = 1` — `bioparent` (родитель → ребёнок).
- `relationship_type_id = 2` — `child` (ребёнок → родитель).

**valid_from**

- Для обоих типов связей (`bioparent` и `child`) `valid_from` синхронизирован с датой рождения ребёнка (`People.birth_date`):
  - для `bioparent` ребёнок = `person_to_id`;
  - для `child` ребёнок = `person_from_id`.
- Если у ребёнка нет `birth_date`, `valid_from` может временно оставаться пустым до уточнения даты.

**valid_to**

- Биологическое родство не прекращается во времени.
- Для всех записей типов `bioparent` и `child` используется константа `9999-12-31` как «открытый конец» периода.
- Факт смерти родителя или ребёнка учитывается только в `People.death_date`, но не обрезает родительско‑детскую связь.

#### Брак / партнёрство (spouselegal / spousecommon)

Семантика:

- `relationship_type_id = 3` — `spouselegal` (официальный брак).
- `relationship_type_id = 4` — `spousecommon` (фактический/гражданский союз, логика аналогична, но сейчас нормализация выполнена только для `spouselegal`.

**valid_from**

- Для браков `valid_from` трактуется как:
  - дата свадьбы / официального заключения брака — для `spouselegal`;
  - дата начала фактических отношений — для `spousecommon` (будет уточняться).
- Значения могут быть заполнены из таблицы `Unions` (`start_date`), когда она будет полностью заполнена.

**valid_to**

- `valid_to` больше не хранится как `NULL` — все открытые связи приведены к `9999-12-31`.
- Для `spouselegal` действуют дополнительные ограничения:
  - при наличии `death_date` хотя бы у одного из партнёров `valid_to` не может быть позже ранней даты смерти;
  - текущее `valid_to` пересчитывается как минимум из:
    - предыдущего значения `valid_to` (считаем `NULL` как `9999-12-31`),
    - `death_date` партнёра A,
    - `death_date` партнёра B.
- В дальнейшем к этой логике будет добавлена дата развода/расставания из таблицы `Unions.end_date`, чтобы окончание брака определялось как минимум из (дата развода, дата смерти, `9999-12-31`).

Рекомендуемая формула: `valid_to` для брака = минимальная из (дата развода, дата смерти одного из партнёров, текущее верхнее значение или `9999-12-31`). Это позволяет строить состояние дерева/союзов на любую дату единым предикатом по интервалу `[valid_from, valid_to)`.

## Текущий функционал (v1.3)
- Timeline: интерактивная лента событий и воспоминаний
- Family Tree Viewer: /family/tree на базе Unions
- PIN-авторизация участников
- Личный кабинет с историей аватаров (AvatarHistory)
- Лендинг: https://www.timewoven.ru (Nginx, HTTPS)

## Следующий шаг
- Переключить app/db.py на PostgreSQL
- Перезапустить timewoven.service
- Протестировать все роуты

## Backlog
- [ ] Переключение FastAPI на PostgreSQL (db.py)
- [ ] Telegram Bot: Импульс дня
- [ ] UI Дерева: интерактивное визуальное древо
- [ ] Whisper Pipeline: транскрибация аудио из /data/raw/
- [ ] Refactoring: перенос эндпоинтов из main.py в routes/

## Сервер
- OS: Ubuntu 22.04
- IP: 193.187.95.221
- Nginx: reverse proxy + static landing
- SSL: Certbot (автообновление через systemd)
- Сервис: timewoven.service (systemd)
- SSH: по ключу (без пароля)