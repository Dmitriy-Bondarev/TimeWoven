# PRODUCT BACKLOG — TimeWoven

> Живой реестр продуктовых задач и решений проекта.
> Этот файл фиксирует:
> - что уже реализовано,
> - что запланировано,
> - какие продуктовые решения приняты,
> - что остаётся в работе.
>
> Не дублирует:
> - `CHANGELOG.md` — журнал релизов и фактически выкаченных изменений,
> - `DB_CHANGELOG.md` — журнал изменений схемы БД,
> - `PROJECT_LOG.md` — операционный журнал сессий изменений.
>
> Статусы:
> - Planned — решение принято, но реализация не завершена
> - In Progress — реализация начата
> - Done — реализовано и проверено
> - Deferred — отложено на будущий релиз

---

## T42 — Meaning and Events Layer for Main Timeline

**Priority:** P1  
**Status:** Planned

### Goal
Сделать так, чтобы **основной** `/family/timeline` строился не только из длинного неструктурированного текста воспоминаний, а из **выделенных смысловых единиц** (событий): короткие карточки с датой/периодом, местом, ролями участников, уверенностью и ссылкой на исходный фрагмент текста. Первоисточник — поля `Memories` (оригинал, пересказ, суть); события — **производный, проверяемый** слой.

### Why now
- Уже есть family-facing timeline, профиль персоны (story-board), published-only, audience/visibility, недавно — `essence_text` в family memory edit. Новый слой логично строить **над** существующими `Memories` и family UI, а не с нуля.
- Отдельно от T30 (инфра/деплой) и от операционного контура `admin / i18n / deploy` в части **реализации** — в backlog этот эпик фиксируется как **следующий крупный продуктовый** блок после docs-freeze; operational слой остаётся параллельным незакрытым пластом.
- T37B/C (Graph Lite, Time Machine) и будущие temporal-сценарии смогут опираться на **структурированные** события, а не только на сырой текст.

### Scope v1 (функциональный)
**Backend (черновик)**
- ORM (через миграции PostgreSQL) для `MemoryEvent`, `MemoryEventPerson`.
- Сервис извлечения/обновления событий из текста memory (readability + при необходимости essence, verbatim по политике качества).
- Хелперы нормализации дат (в т.ч. неточных) и sortable-поля.
- API/маршруты: генерация событий по memory, список/деталь, скрытие/подтверждение, **основной** aggregate timeline из `MemoryEvent` (а не напрямую из сырого текста).

**Family UI**
- `/family/timeline` в итоге **читает** событийный слой; карточка: краткое событие, дата/период, место, участники при наличии; ссылка на memory/персону без потери контекста.
- **Fallback:** если у memory ещё нет событий — мягкий откат к текущему режиму или явное «события ещё не подготовлены», без ломки страницы.

**Admin (минимум)**
- regenerate events для memory; список событий; hide/show; mark verified; ручная правка коротких title/summary/date/place.

### Data model (черновик v1)
**`MemoryEvent`:** `id`, `memory_id`, `event_type`, `title`, `summary`, `description`, `start_date_text`, `end_date_text`, `start_date_sort`, `end_date_sort`, `date_precision`, `place_text`, `confidence`, `source_fragment`, `is_ai_generated`, `is_human_verified`, `is_hidden`, `sort_order`, `created_at`, `updated_at`.

**`MemoryEventPerson`:** `event_id`, `person_id`, `role_code`, `is_primary` (+ PK/уникальность по дизайн-ревью).

**`MemoryPeriod`** — **не** в v1; отложить (phase 2 / отдельная задача).

**Входы для извлечения (с учётом кода):** `content_text`, `transcript_readable`, `transcript_verbatim`, `essence_text`, `MemoryPeople`, контекст персон/дат из текущей модели.

### Non-goals (v1)
- Сложная временная онтология, auto-merge дублей между memories, глобальная дедупликация фактов, богатая карта мест, **полноэкранный** moderation workflow.
- Замена или авто-перезапись **оригинального** текста memory событием; AI **не** стирает смысл без явной ручной линии (см. правила качества в PROJECT_LOG / техдизайне реализации).

### Phases (предлагаемая очередь)
1. **Docs / freeze** — этот epик зафиксирован в `PRODUCT_BACKLOG`, `PROJECT_LOG`, `TECH_PASSPORT` (текущий шаг).
2. **Schema** — модели, миграции, пустой/тестовый `MemoryEvent`.
3. **Extraction** — сервис выделения событий из текста/essence.
4. **Admin moderation lite** — ручные правки и подтверждение.
5. **Timeline switch** — family timeline читает `MemoryEvent` с fallback.
6. **Fallback & QA** — деградация при плохом extraction.

### Event quality (продуктовые правила)
- Событие короче и яснее исходного потока; **одна** основная мысль на событие.
- Неточная дата: человекочитаемая строка + sortable-поле с пониженной точностью.
- Обязательная привязка к **фрагменту** исходного текста; оригинал memory не заменяется.

### References
- `PROJECT_LOG.md` — Decision T42 (2026-04-26)
- `TECH_PASSPORT.md` — roadmap note §4.2.1
- `app/models` — `Memories`, `essence_text` (миграция 007)

---

## T40 — Bilingual Landing (RU/EN) + Waitlist Polish

**Status:** Done

### Goal
Сделать лендинг bilingual (RU/EN) на локалях, собрать статические версии для `/` и `/en/`, и довести waitlist/early-access UX до polished v1.

### Result (2026-04-25)
- Лендинг переведён на локали `landing` (RU/EN) и шаблон использует `t` (секция `landing`) вместо хардкода.
- Добавлена сборка статических версий:
  - `python3 scripts/build_landing.py ru` → `index.html`
  - `python3 scripts/build_landing.py en` → `en/index.html`
- Production static scheme: `/` = RU, `/en/` = EN.
- EN marketing copy polished.
- Визуальный polish (header/hero/cards/footer) + mobile header fix на очень узких экранах.
- Waitlist/early-access: отдельное email-поле `type="email"` + Telegram field, без изменения API payload.

### References
- `PROJECT_LOG.md` — Update: T40 (2026-04-25)
- `CHANGELOG.md` — v1.22.40 (2026-04-25)

---

## OP-2026-04-26 — Admin people list: table-header filters + aliases + gold explorer/avatars

**Status:** Done  
**ID:** OP-ADMIN-PEOPLE-UX-2026-04-26 (операционная подзадача контура admin UI, не смешивать с T42)

### Scope
- `/admin/people`: интерактивные фильтры и поиск **в строке заголовка таблицы**; корректное отображение алиасов (`label`, `alias_type`); вход к редактированию алиасов.
- `/explorer/`, `/admin/avatars`: визуальное выравнивание с gold-темой админки.

### Result
- Реализовано в шаблонах; выкат: `deploy.sh` + `deploy_landing.sh`, коммиты `5f4185e`, `05493eb` на `main` (см. `PROJECT_LOG.md`).

---

## T37A — Family Graph entry points split

**Priority:** P1  
**Status:** Planned

### Scope
- Развести family graph на три точки входа:
  - Graph Lite
  - Time Machine
  - Legacy Graph (admin-only / experimental)

---

## T37B — Graph Lite

**Priority:** P1  
**Status:** Planned

### Scope
- Новый основной семейный граф.
- Focus на выбранном человеке.
- Группировка по союзам.
- Дети не смешиваются между союзами.
- Визуальные границы/контуры союзов.
- Нижняя панель.
- Переход в профиль.
- Компактное управление глубиной.

---

## T37C — Time Machine

**Priority:** P1  
**Status:** Planned

### Scope
- Отдельная temporal‑поверхность семьи.
- Просмотр состояния семьи по годам.
- Использовать существующие temporal/keyframe наработки.
- Family-facing UX.

---

## T37D — Graph / Time privacy model note

**Priority:** P1  
**Status:** Planned

### Scope
- Отдельный эпик на privacy/visibility для graph и temporal views.
- Важно зафиксировать, что запрос на скрытие может исходить от одного участника семьи.
- Это не должно автоматически трактоваться как глобальное ограничение для всех.
- Пока без реализации, только design/backlog note.

---

## P1.10 — Admin-only Person Creation Form

**Status:** Done

### Goal
Активировать создание новых персон через админку без открытия функции для публичных пользователей.

### Decision
- Форма создания персоны доступна только в админском контуре.
- Все маршруты защищены через `require_admin`.
- Публичный UI не изменяется.

### Result
- Доступны:
  - список персон в админке,
  - кнопка создания новой персоны,
  - форма создания,
  - backend-создание `Person` + `PersonI18n`.
- Используется как безопасный режим ручного ввода новых персон в проде.

### References
- `PROJECT_LOG.md` — P1.10
- `CHANGELOG.md` — соответствующая запись релиза/фикса

---

## P1.11 — Maiden Name Support

**Status:** Done

### Goal
Добавить поддержку девичьей фамилии для женщин и других случаев смены фамилии.

### Decision
- Использовать поле `maiden_name` как ближайшую практическую реализацию.
- В админ-форме показывать отдельное необязательное поле: `Девичья фамилия (при рождении)`.
- В карточке персоны отображать девичью фамилию только если она отличается от текущей.

### Result (T8, 2026-04-23)
- Добавлено поле `maiden_name_ru` в форму создания персоны.
- Backend нормализует значение (`strip`, пустое -> `NULL`) и сохраняет в `People.maiden_name`.
- В карточке `/family/person/{person_id}` показывается формат `Имя Фамилия (урождённая X)`, если `maiden_name` заполнено и отличается от текущей фамилии.
- Если `maiden_name` пустое или совпадает с фамилией, показывается обычное `Имя Фамилия`.
- Схема БД не менялась.

---

## P1.15 — Controlled Role Select In Admin Form

**Status:** Done

### Goal
Убрать свободный ввод роли в админ-форме персоны и заменить на контролируемый набор значений.

### Decision
- В форме создания используется выпадающий список ролей вместо текстового input.
- Разрешённые роли: `placeholder`, `relative`, `family_admin`, `bot_only`.
- На backend применяется whitelist-нормализация: невалидные значения приводятся к `placeholder`.

### Result (T9, 2026-04-23)
- `admin_person_new.html`: поле `Роль в системе` заменено на `select` с фиксированными опциями.
- `admin.py`: добавлен whitelist ролей и безопасная нормализация значения из формы.
- `people_service.py`: добавлена сервисная защита (whitelist/fallback), чтобы исключить мусорные роли из других вызовов.
- Схема БД не менялась.

## P1.12 — Person Creation Without Contact Channel

**Status:** Done

### Goal
Разрешить создание персон без канала связи и без контактов, особенно для умерших родственников.

### Decision
- Канал связи и контактные поля не обязательны.
- Для сценария «нет канала связи» используется нейтральная логика:
  - `preferred_ch = NONE` на уровне UI / валидации,
  - пустые контакты нормализуются в `NULL`.
- Для умерших родственников отсутствие канала связи — нормальный и поддерживаемый сценарий.

### Result
- Исправлена ошибка создания персоны при отсутствии контактов.
- Поддержан сценарий:
  - умерший человек,
  - без телефона,
  - без email,
  - без Max ID,
  - без активного канала связи.
- Исправлены сообщения об ошибках и нормализация значений.

### References
- `PROJECT_LOG.md` — P1.12
- `DB_CHANGELOG.md` — migration 003 / preferred channel update
- `CHANGELOG.md` — bugfix/feature запись по результату

---

## P1.14 — Exclude Deceased Relatives from Who-Am-I Selector

**Status:** Done

### Goal
Исключить умерших родственников из экрана выбора пользователя `Кто вы?`, чтобы в login/select-flow отображались только те, кто может войти в приложение.

### Decision
- На текущем этапе применён обязательный фильтр: `is_alive = 1`.
- Для защиты от обхода через URL тот же фильтр добавлен на backend-шаги submit/pin.
- `is_user = 1` оставлен как следующий этап ужесточения, чтобы не блокировать текущий релиз.

### Result
- В dropdown `Кто вы?` больше не отображаются умершие.
- Умершие остаются в базе, графе, карточках и истории без изменений.
- login/select-flow теперь отделён от общей семейной модели по жизненному статусу.

### References
- `docs/PROJECT_LOG.md` — P1.14
- `CHANGELOG.md` — UX/Bugfix запись P1.14

---

## P1.13 — Temporal Name / Surname History

**Status:** Deferred

### Goal
Перейти от статического хранения фамилии к временной модели имени и фамилии.

### Product decision
Фамилия должна зависеть от даты просмотра:
- в обычной карточке показывается актуальная/последняя фамилия,
- в историческом контексте должна показываться фамилия, действовавшая на выбранную дату,
- девичья и прежние фамилии могут отображаться как вспомогательные значения для узнавания.

### Planned architecture
В будущей версии ввести temporal-сущность истории имени, например:
- `PersonNameHistory`
  - `person_id`
  - `first_name`
  - `last_name`
  - `name_type`
  - `valid_from`
  - `valid_to`
  - `is_primary`

### Planned UX
- В карточке без временного фильтра:
  - показывается последняя основная фамилия.
- В графе и историческом срезе:
  - показывается фамилия на выбранную дату.
- Девичья фамилия остаётся полезной как быстрый UX-мост до полной temporal-модели.

### Notes
Эта задача зависит от дальнейшего развития temporal-подхода, который уже используется для отношений (`valid_from`, `valid_to`).

---

## Naming / surname policy snapshot

### Current rule
- Если пользователь открывает карточку человека без временного контекста:
  - показываем актуальную или последнюю основную фамилию.
- Если у человека есть девичья фамилия и она важна для узнавания:
  - показываем её в скобках.
- Для женщин предпочтительный публичный формат:
  - `урождённая {maiden_name}`

### Future rule
- Имя и фамилия становятся временными атрибутами.
- На любой выбранной дате система должна уметь показать корректную фамилию на этот момент.

---

## Maintenance rule

При изменении статуса любой P-задачи в этом файле необходимо:
1. Обновить `PRODUCT_BACKLOG.md`
2. Добавить запись в `PROJECT_LOG.md`, если была рабочая сессия изменений
3. Обновить `CHANGELOG.md`, если изменение реально реализовано
4. Обновить `DB_CHANGELOG.md` и `DATABASE_SCHEMA.md`, если менялась схема БД