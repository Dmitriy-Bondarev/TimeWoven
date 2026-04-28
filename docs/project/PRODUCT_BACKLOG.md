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


## Сводка задач (срез 2026-04-27)


| ID | Приоритет | Статус | Краткое описание |
|---|---|---|---|
| **T-FAMILY-ACCESS-REBUILD** | **P0** | Planned | Полное восстановление слоя person_alias_service (сейчас shim после инцидента 2026-04-26) |
| **T-CORE-THEME-RESTORE** | **P0** | Planned | Восстановить утраченный модуль `app/core/theme.py` (`get_active_theme_preset`) |
| T42 | P1 | Planned | Meaning and Events Layer for Main Timeline (event-centric `/family/timeline`) |
| T43 | P1 | Planned | Family reply as collective memory entry (`/family/reply/{id}`) |
| T37A | P1 | Planned | Family Graph entry points split (Graph Lite / Time Machine / Legacy) |
| T37B | P1 | Planned | Graph Lite — основной семейный граф |
| T37C | P1 | Planned | Time Machine — temporal-поверхность семьи |
| T37D | P1 | Planned | Graph / Time privacy model note (design only) |
| T-DUPLICATE-FAMILY-TREE-ROUTE-INVESTIGATE | P2 | Planned | Расследовать дубль маршрута `/family/tree` в `tree.py` и `family_tree.py` |
| T-OPS-INDEX-LOG-FORMAT | P3 | Planned | Улучшить разделители полей в `TimeWoven_snapshots/INDEX.log` |
| T-PROTOCOL-IDE-COEXISTENCE | P3 | Planned | Добавить в PROJECT_OPS_PROTOCOL раздел про сосуществование с git-extension Cursor IDE |
| T-FAMILY-MEMORY-NEW-RETURN-303-INSTEAD-OF-422 | P3 | Planned | UX-минор: GET без авторизации/параметров → 303 на access вместо 422 pydantic-валидации |
| T-GIT-WORKFLOW-DOCS-2026-04-28 | P0 | Done | Введение Git branching model (main/develop/feature) |
| P1.13 | — | Deferred | Temporal Name / Surname History |
| **C.1** | — | **Done** | **Admin hardening (rate limit + idle timeout + audit log)** — закрыто 27.04.2026 (T-ADMIN-HARDENING-2026-04-27) |
| T40 | — | Done | Bilingual Landing (RU/EN) + Waitlist Polish (2026-04-25) |
| OP-2026-04-26 | — | Done | Admin people list: filters + aliases + gold theme (2026-04-26) |
| P1.10 | — | Done | Admin-only Person Creation Form |
| P1.11 | — | Done | Maiden Name Support (T8, 2026-04-23) |
| P1.12 | — | Done | Person Creation Without Contact Channel |
| P1.14 | — | Done | Exclude Deceased Relatives from Who-Am-I Selector |
| P1.15 | — | Done | Controlled Role Select In Admin Form (T9, 2026-04-23) |


---

### ✅ C.1 — Admin hardening (rate limit + idle timeout + audit log)
**Закрыто:** 27.04.2026 (T-ADMIN-HARDENING-2026-04-27)
**Коммиты:** `c927c3f`, `0bb0de4`, `b0ae7e8`, `0d608f2`
**Подробности:** см. PROJECT_LOG.md → T-ADMIN-HARDENING-2026-04-27

## T-ADMIN-CSRF-PROTECTION-FUTURE
**Приоритет:** P2 (безопасность, не блокер)
**Происхождение:** при закрытии C.1 27.04.2026.
**Цель:** защитить POST-эндпоинты админки (login, people edit, unions, access reset и др.) от CSRF-атак.
**Что нужно:**
- Сгенерировать CSRF-токен при логине, положить в HttpOnly cookie + добавить hidden input в формы.
- Проверять токен в зависимостях для всех `@router.post` под `require_admin`.
- Использовать `itsdangerous` или `secrets.token_urlsafe` для генерации.
**Размер:** S-M (~0.5 дня).
**Зависимости:** нет.

## T-ADMIN-2FA-TOTP-FUTURE
**Приоритет:** P2 (безопасность)
**Происхождение:** при закрытии C.1 27.04.2026.
**Цель:** добавить второй фактор для входа в админку (TOTP / Google Authenticator).
**Что нужно:**
- Привязка TOTP-секрета админу при первом входе или через env (`ADMIN_TOTP_SECRET`).
- Дополнительная страница после успешной проверки логин/пароль — ввод 6-значного кода.
- Использовать существующую логику TOTP из family_access_service (там уже работает для семейного доступа).
**Размер:** M (~1 день).
**Зависимости:** существующий TOTP-код в `family_access_service` как референс.

## T-ADMIN-IDLE-STORE-REDIS-FUTURE
**Приоритет:** P3 (улучшение, не критично)
**Происхождение:** при закрытии C.1 27.04.2026.
**Цель:** перенести `_LOGIN_ATTEMPTS` и `_ADMIN_LAST_SEEN` из памяти процесса в Redis, чтобы переживать рестарты и работать в multi-worker конфигурации.
**Что нужно:**
- Поднять Redis (если ещё нет в проекте — это решение само по себе).
- Заменить in-memory dict на Redis-keys с TTL.
- Сохранить тот же API helper-функций.
**Размер:** S (~0.5 дня после поднятия Redis).
**Зависимости:** Redis должен быть в инфраструктуре проекта; пока не нужен — вынесено в P3.

## T-THEME-VISUAL-INTEGRATION-FUTURE

**Приоритет:** P2 (визуал, не блокер)
**Статус:** в backlog, делаем на этапе шлифовки UI/UX
**Происхождение:** решение от 27.04.2026 при закрытии A.1 T-CORE-THEME-RESTORE

### Контекст
27.04.2026 восстановлен Python-API тем (`app/core/theme.py`) после инцидента 26.04: пресеты `current_dark` / `voice_premium`, персистентность через `bot_sessions` (key `__app_settings__`), функции `get_active_theme_preset` / `set_active_theme_preset` (commit `76f1f21`).

API работает: запись в БД с `voice_premium` подтверждена, функции отдают корректное значение. Однако визуально все страницы рендерятся в одном пресете (золотая/dark gold) — переключатель пресета на `/admin/theme` не влияет на CSS, потому что **визуальная интеграция пресетов в шаблоны не выполнена**.

### Что нужно сделать (когда дойдут руки до UI/UX)

1. **CSS-токены и два пресета в `app/web/static/site/theme.css`:**
   - Базовые токены: `--bg`, `--surface`, `--surface-2`, `--text`, `--text-muted`, `--accent`, `--accent-strong`, `--border`, `--shadow`.
   - Селектор корня по `[data-tw-theme="current_dark"]` и `[data-tw-theme="voice_premium"]` с разными значениями токенов.
   - Все компонентные правила переписать через `var(--token)`, без хардкода цветов.

2. **`app/web/templates/base.html`:**
   - На `<html>` повесить `data-tw-theme="{{ request.state.active_theme | default('current_dark') }}"`.
   - Шаблоны `family/`, `admin/`, `site/` наследуют от общего `base.html`.

3. **Middleware в `app/main.py`:**
   - На каждый запрос подгружать `active_theme_preset` из БД (с кэшем) и класть в `request.state.active_theme`.
   - Кэш — TTL 30 секунд, чтобы переключение виделось без рестарта, но БД не насиловалась.

4. **Роут `POST /admin/theme`:**
   - Принимает `preset` из формы (radio).
   - Валидирует через `normalize_theme_preset`.
   - Вызывает `set_active_theme_preset(db, preset)`.
   - Редирект назад на `/admin` с flash-сообщением.

5. **Админ-дашборд:**
   - Текущий блок темы со статусом "Скоро" → радио-кнопки на 2 пресета, активный отмечен по результату `get_active_theme_preset`.

6. **QA:**
   - Открыть `/landing`, `/admin`, `/family/tree` в обоих пресетах, проверить читаемость, контраст, фокус-стейты.
   - В инкогнито: переключение через POST /admin/theme должно влиять на все страницы без перезагрузки шаблонов.

### Зависимости
- Никаких блокирующих. Делать после: C.1 admin hardening, OP-LEGAL юр. документы, T40 лендинг (если будем делать).
- Можно делать параллельно с любой не-визуальной работой.

### Размер
M (средняя): ~1 день работы, 4-6 коммитов (CSS токены / base.html / middleware / роут / дашборд / QA-фикс).

### Почему не P0/P1
- Текущий визуал (золотая dark) — пользователю нравится и работает.
- Переключение тем — это фича для будущих пользователей, не для MVP.
- Пользовательская формулировка 27.04.2026: "мне сейчас как пользователю всё равно какая тема — главное чтобы работали".

---

## T-FAMILY-ACCESS-REBUILD — restore full person_alias_service layer


**Priority:** P0  
**Status:** Planned  
**Created:** 2026-04-27 (по итогам инцидента 2026-04-26)


### Goal
Восстановить полную функциональность слоя управления алиасами персон. Сейчас `app/services/person_alias_service.py` существует только как минимальный shim, экспортирующий `ALIAS_TYPES` и `ALIAS_STATUS` (см. docstring модуля).


### Context
Во время инцидента 2026-04-26 (см. `PROJECT_LOG.md` — `## INCIDENT 2026-04-26`) полный код сервиса был утрачен: на момент аварии существовал только как untracked-файл и в `.pyc`. После восстановления оставлен как shim, чтобы не блокировать `/admin/people` и связанные роуты, которые импортируют `ALIAS_TYPES` / `ALIAS_STATUS`.


### Что нужно восстановить
По косвенным признакам (импорты, миграции, шаблоны):
1. Полная бизнес-логика создания/обновления/удаления алиасов персон.
2. Workflow статусов алиасов (`active`, `pending`, `rejected`).
3. Поиск персон по алиасам (kinship_term, nickname, diminutive, formal_with_patronymic, other).
4. Логика мерджа дубликатов / pending-review для AI-сгенерированных алиасов.
5. Связь с `/admin/people/{id}/aliases` UI и admin templates `adminpersonaliases.html`.


### Источники для восстановления
- `app/api/routes/admin.py` — текущие импорты и места использования.
- `app/web/templates/admin/adminpersonaliases.html` — UI-контракт (поля, действия).
- `migrations/007_add_person_aliases.sql` — схема БД (таблицы, поля).
- Архив stash дня инцидента: `/root/projects/TimeWoven_snapshots/protected/STASH-REFERENCE-2026-04-26/stash_2_wip-before-p1-20.diff` — частичный код может присутствовать.


### Non-goals (фаза 1)
- Не вводить новые типы алиасов сверх существующих.
- Не менять схему БД (миграция 007 уже применена).
- Не делать AI-моде ration workflow в этой задаче.


### References
- `PROJECT_LOG.md` — `## INCIDENT 2026-04-26`
- `TECH_PASSPORT.md` — §3.3 (модуль помечен как SHIM)
- `app/services/person_alias_service.py` — текущий shim


---


## T-CORE-THEME-RESTORE — restore app/core/theme.py


**Priority:** P0  
**Status:** Planned  
**Created:** 2026-04-27 (по итогам инцидента 2026-04-26)


### Goal
Восстановить утраченный модуль `app/core/theme.py` с функцией `get_active_theme_preset(db)`, которая определяет активную тему оформления per-request.


### Context
Во время инцидента 2026-04-26 модуль `app/core/theme.py` был полностью утрачен. Временное решение — статическое значение `request.state.active_theme = "current_dark"` в `app/main.py`. Это работает, но блокирует функционал «выбор темы оформления», UI-стаб которого виден на `admin_dashboard` («Скоро: выбор темы оформления»).


### Что нужно восстановить
1. Функция `get_active_theme_preset(db: Session) -> str` — возвращает текущий активный пресет темы.
2. Хранение пресета (предположительно в БД или в `.env` — уточнить из stash@{1} архива).
3. Список допустимых пресетов (минимум `current_dark`; возможно `gold`, `light` и др.).
4. Восстановить middleware-логику в `app/main.py`: вернуть вызов `get_active_theme_preset(db)` вместо хардкода.


### Источники для восстановления
- Архив stash@{1}: `/root/projects/TimeWoven_snapshots/protected/STASH-REFERENCE-2026-04-26/stash_1_emergency-prod-breakage.diff` — содержит точный код, который был отключён, и оригинальный импорт.
- Архив stash@{2}: `stash_2_wip-before-p1-20.diff` — может содержать исходник модуля.


### Acceptance criteria
- Модуль `app/core/theme.py` существует, импортируется без ошибок.
- `request.state.active_theme` снова определяется через БД, не хардкод.
- Сервис стартует, `/health` отдаёт `ok`.
- Существующие шаблоны (admin, family) рендерятся без визуальной регрессии.


### References
- `PROJECT_LOG.md` — `## INCIDENT 2026-04-26`
- `TECH_PASSPORT.md` — §3.3, секция «Утрачено в инциденте»


---


## T-DUPLICATE-FAMILY-TREE-ROUTE-INVESTIGATE


**Priority:** P2  
**Status:** Planned  
**Created:** 2026-04-27


### Goal
Расследовать дублирование маршрута `/family/tree` в двух файлах:
- `app/api/routes/tree.py:768` — `@router.get("/family/tree", response_class=HTMLResponse, name="family_tree_page")`
- `app/api/routes/family_tree.py:9` — `@router.get("/family/tree", response_class=HTMLResponse)`


### Why
В `app/main.py` подключается только `tree_router` (см. `family_tree.py` помечен как legacy в `TECH_PASSPORT.md` §3.3). Прод сейчас работает корректно. Но наличие неподключённого роутера с конфликтующим путём — потенциальная мина: если кто-то в будущем подключит обе по неосторожности, FastAPI зарегистрирует оба, и порядок включения определит, какая страница реально откроется.


### Scope
1. Прочитать оба роутера, понять расхождения в логике.
2. Решить: удалить `family_tree.py` целиком, или унифицировать в один файл, или оставить как есть с явным комментарием в шапке файла «не подключать в main.py — конфликтует с tree.py».
3. Если удаляем — `git rm` + запись в `PROJECT_LOG.md` + проверка, что нигде не импортируется.


### Non-goals
- Не менять поведение `/family/tree` для пользователя.
- Не трогать `family_tree.html` шаблон.


### References
- `TECH_PASSPORT.md` — §3.3 (legacy routes)
- `app/main.py` — фактическое подключение routers


---


## T-OPS-INDEX-LOG-FORMAT


**Priority:** P3  
**Status:** Planned  
**Created:** 2026-04-27


### Goal
Улучшить формат файла `/root/projects/TimeWoven_snapshots/INDEX.log` для удобства человеческого чтения.


### Current state
Поля разделены табами (`\t`), что в выводе `cat`/`tail` смотрится как слипшиеся значения:
CLEAN-START-2026-04-2798696bc516a064eb6357647c34906d9e81ca145e2026-04-27T06:51:40+00:00protected/root/projects/...


### Desired
Один из вариантов:
- **A.** Заменить табы на `␣|␣` (pipe с пробелами) — читаемо в любом терминале.
- **B.** Перейти на однострочный JSON: `{"task_id":"CLEAN-START-2026-04-27","head":"98696bc...","ts":"...","mode":"protected","path":"..."}` — даёт машинную обрабатываемость через `jq`.


### Implementation
- Правка в `scripts/ops/safety_snapshot.sh` — место записи строки в `INDEX.log`.
- Существующие записи мигрировать вручную (пара строк).


### References
- `scripts/ops/safety_snapshot.sh`
- `docs/PROJECT_OPS_PROTOCOL.md` — §4.1


---


## T-PROTOCOL-IDE-COEXISTENCE


**Priority:** P3  
**Status:** Planned  
**Created:** 2026-04-27


### Goal
Добавить в `docs/PROJECT_OPS_PROTOCOL.md` отдельный раздел про сосуществование с git-extension в IDE (Cursor, VSCode), описывающий проблему интермиттирующего `.git/index.lock` и стандартное решение через `flock`.


### Context
27 апреля при коммите ops-протокола обнаружено: git-extension в Cursor IDE (через `cursor-server` / `fileWatcher` / `extensionHost`) дёргает `git status`, `git diff`, `git index` в фоне для отрисовки значков изменений. Это приводит к интермиттирующим сбоям `git add` с ошибкой `fatal: Unable to create '.git/index.lock': File exists`. Решение — оборачивать git-операции в `flock --timeout 30 .git/index.lock.flock <git command>`.


### Scope
1. Добавить в `PROJECT_OPS_PROTOCOL.md` раздел (предположительно §9.x или §6.5) "Coexistence with IDE git extensions":
   - Описание проблемы.
   - Стандартное решение (`flock` обёртка).
   - Альтернатива: отключить git extension в настройках IDE на время проектной работы (`git.enabled: false`).
   - Когда применять обёртку (всегда, или только при определённых паттернах работы).
2. Опционально: создать утилитный скрипт `scripts/ops/git_safe.sh` — обёртку, которая автоматически применяет flock.


### References
- `docs/PROJECT_OPS_PROTOCOL.md`
- `PROJECT_LOG.md` — запись 27 апреля 2026 (упоминание flock)


---


## T-FAMILY-MEMORY-NEW-RETURN-303-INSTEAD-OF-422


**Priority:** P3  
**Status:** Planned  
**Created:** 2026-04-27


### Goal
UX-улучшение: при GET-запросе на `/family/memory/new` без авторизованной family-сессии и без `person_id` сейчас FastAPI возвращает `422 Unprocessable Entity` (валидация pydantic). Корректнее возвращать `303 See Other` с редиректом на форму family access (как делают другие защищённые family-маршруты).


### Why
- 422 — не интуитивный UX-ответ для пользователя, который случайно открыл прямую ссылку.
- 303 на access-форму даёт понятный путь "залогиньтесь, чтобы создать воспоминание".


### Scope
1. Найти GET-обработчик `/family/memory/new` в `app/api/routes/tree.py` (упоминается в startup-проверке `_assert_family_memory_new_route`).
2. Перед валидацией pydantic-параметров вызвать `_require_family_zone(...)`, который выполняет редирект.
3. Убедиться, что POST-обработчик не задет.


### References
- `app/api/routes/tree.py` — обработчики `family/memory/new` (GET и POST)
- `TECH_PASSPORT.md` — §6.3 (Известные ограничения)


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
- `TECH_PASSPORT.md` — roadmap note §4.2
- `app/models` — `Memories`, `essence_text` (миграция 007)
- `app/services/timeline_event_view.py` — текущий промежуточный view-слой (не event-centric, но первый шаг)


---


## T43 — Family reply as collective memory entry (`/family/reply/{id}`)


**Priority:** P1  
**Status:** Planned


### Goal
Экран `/family/reply/{id}` должен эволюционировать из «экрана добавления ответа» в **полноценную точку входа в коллективную память** семьи.


### Scope (будущий отдельный продуктовый пакет)
1. **Привязка reply** не только к исходной истории, но и к **событию**, если событие определено.
2. **Event context на экране reply:** пользователь понимает, к какому событию добавляет воспоминание; связь **reply ↔ event** становится частью UX-модели.
3. **Сворачивание длинной исходной истории:** preview; действия **«Показать полностью»** / **«Свернуть»**.
4. **Тип ответа:** Воспоминание / Мысль / Факт.
5. **AI-помощь на экране reply:** помочь сформулировать, сделать короче, сделать яснее.
6. **Empty state:** более сильная семейная «пустота» / welcoming empty state.
7. **Дальнейшее сближение reply-flow** с общей **event-memory** моделью продукта (согласованность с T42 и family timeline / событийным слоем).


### Non-goals (текущий контур)
- **Не** включать в текущий локальный пакет **polish reply screen**; эта ступень — **отдельная будущая задача** без внедрения в текущем блоке.


### References
- `PROJECT_LOG.md` — TW-2026-04-26-R4 / family reply next package (2026-04-26)
- `PRODUCT_BACKLOG.md` — T42 (событийный слой timeline)


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


При изменении статуса любой задачи в этом файле необходимо:
1. Обновить `PRODUCT_BACKLOG.md` (включая сводную таблицу в начале файла).
2. Добавить запись в `PROJECT_LOG.md`, если была рабочая сессия изменений.
3. Обновить `CHANGELOG.md`, если изменение реально реализовано.
4. Обновить `DB_CHANGELOG.md` и `tech-docs/DATABASE_SCHEMA.md`, если менялась схема БД.
5. Обновить `TECH_PASSPORT.md`, если изменилась фактическая структура каталогов или модулей.


**Перед началом работы над любой задачей** (с 2026-04-27, см. `docs/PROJECT_OPS_PROTOCOL.md`):
1. Запустить `bash scripts/ops/clean_state_gate.sh` — должен вернуть PASS.
2. Запустить `bash scripts/ops/safety_snapshot.sh <TASK_ID>` — создать snapshot перед началом изменений.
3. Сформулировать ТЗ для implementation-агента по шаблону §6.1 протокола (SCOPE-LOCK / DO-NOT-TOUCH / PRE-CHECK / DEVIATION-RULE / EXIT-CRITERIA).
