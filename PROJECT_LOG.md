# PROJECT LOG — TimeWoven

## Update: T18.C — Max audio transcription inside session flow

Date: 2026-04-23

### Structural change

No

### Schema change

No

### Changes

- В `app/api/routes/bot_webhooks.py` в audio-ветке добавлен автоматический вызов `TranscriptionService` после успешного локального скачивания.
- Результат транскрипции добавляется в `draft_items` текущей open session через `max_session_service.add_audio_item(...)`.
- Для аудио теперь сохраняются поля: `audio_url`, `local_path`, `transcription_text`, `transcription_status`, `transcribed_at`, `transcription_error`.
- В `app/services/max_session_service.py` обновлён `_rebuild_draft_text`: включает успешные voice-фрагменты как `[voice] ...`.
- `finalize_session(...)` теперь всегда кладёт raw `draft_items` в metadata (`Memory.transcript_verbatim`), поэтому в финальной draft memory остаются все результаты транскрипции.
- Fallback реализован: при неуспехе транскрипции (`empty/error`) webhook не падает, аудио остаётся в черновике, финализация всё равно создаёт Memory.
- Удалён legacy-дубликат маршрута `/webhooks/maxbot/incoming`; оставлен один актуальный handler.
- Smoke-tests пройдены: service-level (успех+ошибка), webhook e2e (text+audio+Готово) через HTTP.

---

## Update: T18.B — Max chat sessions + draft aggregation + audio hardening

Date: 2026-04-23

### Structural change

Yes (new table `max_chat_sessions`)

### Schema change

Yes — миграция `006_add_max_chat_sessions.sql`

### Changes

- Добавлена таблица `max_chat_sessions` (id, max_user_id, person_id FK, status, created/updated/finalized_at, draft_text, draft_items JSON, message_count, audio_count, memory_id FK, analysis_status).
- Добавлен ORM-модель `MaxChatSession` в `app/models/__init__.py`.
- Создан `app/services/max_session_service.py`: `get_open_session`, `create_session`, `get_or_create_open_session`, `add_text_item`, `add_audio_item`, `finalize_session`, `is_finalize_command`.
- Рефакторинг `app/api/routes/bot_webhooks.py`: входящий текст/аудио → `add_text_item`/`add_audio_item`; команда «Готово/Завершить/…» → `finalize_session`; контакты без изменений.
- Audio hardening: `_download_audio_to_raw` вызывается всегда; при ошибке скачивания сессия не падает, CDN URL сохраняется в `draft_items`.
- Финализация создаёт `Memory(source_type='max_session', transcription_status='draft')` с AI-metadata.
- Finalize commands: `готово`, `завершить`, `это всё`, `это все`, `закончить`, `стоп`, `end`, `done`, `finish`.
- Smoke-test пройден: 9 шагов против реальной БД (lifecycle + fallback при AI error).

---

## Update: T18.A — AI-провайдер llama_local (LLaMA local HTTP server)

Date: 2026-04-23

### Structural change

No

### Schema change

No

### Changes

- В `app/services/ai_analyzer.py` добавлен класс `LlamaLocalAnalyzerProvider` (`provider_name="llama_local"`).
- Читает `AI_LLAMA_LOCAL_URL` из `.env`; POST `{"text": str}`; парсит `{"summary", "people", "events", "dates"}`.
- Таймаут 30 с (`LLAMA_LOCAL_TIMEOUT_SECONDS`); все ошибки → `status="error"`, сервис не падает.
- Добавлено поле `events` в возвращаемый словарь (для LLaMA-ответа; другие провайдеры возвращают пустой список).
- `_build_provider` в `ProviderAgnosticAnalyzer` дополнен веткой `"llama_local"`.
- Обновлены `TECH_PASSPORT.md` (раздел M2 AI abstraction) и `TimeWoven_Anchor_2026-04-23.md` (AI-анализ + Max-бот).

---

## Update: T17 — Soft-archive duplicate People 40/43 after Max contacts manual review

Date: 2026-04-23

### Structural change

No

### Schema change

No (data-only)

### Changes

- Диагностика FK для `person_id IN (40, 43)`: нулевые ссылки во всех таблицах — ребайнд не потребовался.
- `People.person_id=40` переведён в `record_status='test_archived'` (дубль `person_id=2`; `messenger_max_id` уже был перенесён вручную).
- `People.person_id=43` переведён в `record_status='test_archived'` (дубль `person_id=8`; `messenger_max_id` уже был перенесён вручную).
- `person_id IN (41, 42)` подтверждены как `active` + `relative` + ru/en в `People_I18n` — изменений не вносилось.
- Записи физически не удалены (soft cleanup через `record_status`, как в T14/T16).

---

## Update: T16 — Max contacts ingestion hardening and duplicate cleanup

Date: 2026-04-23

### Structural change

Yes

### Schema change

Yes

### Changes

- Контактные attachment-события из Max больше не создают `People` автоматически: вместо этого сохраняются в `MaxContactEvents` (raw payload + sender/contact ids + names + status).
- В `bot_webhooks` удалён path авто-создания contact-person (`role='member'`, `is_user=1`, `messenger_max_id`) при `type='contact'`.
- Выполнен cleanup тестовых дублей: `People.person_id IN (35,36,37,38,39)` помечены `record_status='test_archived'`.
- Выполнен cleanup test marker memories: `Memories.id IN (20..24)` и future `TEST CONTACT` markers переводятся в archived (`is_archived=true`, `transcription_status='archived'`, `source_type='max_contact_test_marker'`).
- Live family surfaces ужесточены до `People.record_status='active'` (who-am-i, family tree/json, timeline, welcome random memory).
- Админка продолжает видеть архивные/тестовые записи для ручной ревизии.

## Update: T14 — person record_status and live family hiding for test_archived

Date: 2026-04-23

### Structural change

No

### Schema change

Yes

### Changes

- В `People` добавлено поле `record_status` (`active|archived|test_archived`, default `active`).
- Live family surfaces скрывают только `test_archived`: `who-am-i` + PIN flow, `/family/person/{id}`, `/family/tree/json`, `/family/timeline`.
- Админский список `/admin/people` сохраняет видимость всех записей и показывает `record_status` отдельной колонкой.
- Добавлена миграция `migrations/004_add_record_status_to_people.sql`, включая data update: `person_id IN (20,21,22,23) -> test_archived`.

## Update: T13 — finalize T11 timeline filtering and T12 maiden name UI polish

Date: 2026-04-23

### Structural change

No

### Schema change

No

### Changes

- family timeline now shows only published items.
- raw/json-like payloads are hidden from family timeline.
- maiden name moved from `h1` to a secondary muted line under the person name.

## Update: T9 — Role select in admin person form

Date: 2026-04-23

### Structural change

No

### Schema change

No

### Changes

- `app/web/templates/admin/admin_person_new.html` — текстовое поле роли заменено на `select` с фиксированными значениями: `placeholder`, `relative`, `family_admin`, `bot_only`.
- `app/api/routes/admin.py` — добавлен whitelist ролей и нормализация input: невалидные значения приводятся к `placeholder`.
- `app/services/people_service.py` — добавлена сервисная защита по тому же whitelist для устойчивости при альтернативных вызовах.
- Ручная проверка: форма отдаёт `select`, роли `relative` и `family_admin` корректно сохраняются и отображаются в `/admin/people`.

## Update: T8 — P1.11 Maiden Name Support

Date: 2026-04-23

### Structural change

No

### Schema change

No

### Changes

- `app/web/templates/admin/admin_person_new.html` — добавлено поле `Девичья фамилия (при рождении)` (`maiden_name_ru`) в форму создания персоны.
- `app/api/routes/admin.py` — чтение `maiden_name_ru` из формы, нормализация (`strip`, пустое значение -> `None`) и маппинг в `person_data["maiden_name"]`.
- `app/services/people_service.py` — запись `maiden_name` в `People.maiden_name` при создании персоны.
- `app/api/routes/tree.py` — в context профиля добавлен `person_i18n` для корректного сравнения текущей и девичьей фамилии.
- `app/web/templates/family/profile.html` и `app/web/templates/family/person_card.html` — отображение формата `Имя Фамилия (урождённая X)` только если `maiden_name` заполнено и отличается от текущей фамилии.
- E2E проверка выполнена через приложение: сценарий с `maiden_name != last_name` показывает скобки, сценарий с пустым `maiden_name` — без скобок.

## Update: T10 — Repository hygiene (docs/tech-docs/temp reorganization)

Date: 2026-04-23

### Structural change

Yes

### Schema change

No

### Changes

- Инвентаризировано содержимое документационных папок.
- **docs/** теперь содержит только публичные артефакты для GitHub Pages: `CNAME`, `logo.png`.
  - Удалены: `DATABASE_SCHEMA.md` (перемещён в `tech-docs/`), `snapshots/` (перемещён в `tech-docs/snapshots/`), `PROJECT_LOG.md` (перемещён в корень репозитория).
- **tech-docs/** стал центральным хранилищем архитектурной документации:
  - `DATABASE_SCHEMA.md` — техническое описание схемы PostgreSQL.
  - `adr/` — Architecture Decision Records (ADR-001 до ADR-006).
  - `snapshots/` — снимки состояния структуры и графов для истории.
  - `family-graph-snapshot-timeline-notes.md` — исследовательские заметки.
  - `README.md` — индекс документации.
- **temp/** остаётся рабочей песочницей, но полностью игнорируется git (кроме `.gitkeep` и `README.md`).
  - `project_docs/` с шаблонами документации сохранена для справки.
- **Корень репозитория:** `PROJECT_LOG.md` перемещён сюда для удобного доступа к операционному журналу.
- `.gitignore` подтверждён и усилен правилами для `temp/`.

**Результат:** репозиторий упорядочен, документация централизована в `tech-docs/`, граница между публичной документацией (`docs/`) и архитектурной (`tech-docs/`) ясна.

## Update: P1.14 — Exclude deceased relatives from who-am-I selector

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- Список персон для login/who-am-I теперь фильтруется по `is_alive = 1`.
- Защищены смежные шаги flow (`POST /who-am-i`, `GET/POST /who-am-i/pin`): умершие персоны исключены и при прямом доступе по `person_id`.
- Умершие сохраняются в базе, графе, карточках и истории, но больше не участвуют в selector-flow входа.

## Update: Docs artifact — PRODUCT_BACKLOG registry introduced

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- Добавлен постоянный продуктовый артефакт `PRODUCT_BACKLOG.md` в корне проекта.
- `PRODUCT_BACKLOG.md` используется как живой реестр продуктовых задач, статусов и принятых решений.
- Документ синхронизируется с `CHANGELOG.md`, `DB_CHANGELOG.md` и `docs/PROJECT_LOG.md` по мере реализации задач.

## Update: P1.12 — Support person creation without contact channel

Date: 2026-04-22

### Structural change

No

### Schema change

Yes

### Changes

- `app/api/routes/admin.py` — добавлена канонизация `preferred_ch` из UI (`NONE/MAX/TG/EMAIL/PUSH`) в БД-совместимые значения; отсутствие канала сохраняется как `NULL`.
- `app/api/routes/admin.py` — контакты (`max_user_id`, `phone`, `contact_email`) нормализуются: пустые строки больше не пишутся в БД, сохраняются как `NULL`.
- `app/api/routes/admin.py` — для `IntegrityError` добавлены точные сообщения: дубликат Max ID, недопустимый канал связи, общий fallback по контактам.
- `app/services/people_service.py` — нормализация опциональных текстовых полей на уровне сервиса, сохранение `preferred_ch` и контактов без принудительного значения `"None"`.
- `app/web/templates/admin/admin_person_new.html` — добавлен явный вариант `Нет канала связи` (по умолчанию), поддержка `MAX` в UI и поле `Email` как необязательный контакт.
- `migrations/003_expand_preferred_channel_for_max.sql` — применена миграция в рабочей БД: CHECK `People.preferred_ch` расширен до `('Max', 'TG', 'Email', 'Push', 'None')`.
- Ручные тест-кейсы создания (умерший без контактов, живой без контактов, живой с Max) проходят успешно.

## Update: P1.10 — Admin-only Person Creation Form activation

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/api/routes/admin.py` — добавлены два защищённых эндпоинта `/admin/people` (GET, список), `/admin/people/new` (GET, форма) и `/admin/people/new` (POST, обработка). Все роуты защищены `require_admin`.
- `app/services/people_service.py` — добавлена функция `create_person_with_i18n()` для одного-шагового создания Person + RU-i18n + опциональной EN-i18n записей в одной транзакции.
- `app/services/__init__.py` — подключена функция `create_person_with_i18n` в пакет services.
- `app/web/templates/admin/admin_people.html` — добавлена кнопка «+ Новая персона» для перехода на форму `/admin/people/new`.
- `app/web/templates/admin/admin_person_new.html` — создан новый шаблон админ-формы с полями: пол, жив ли, роль, язык, даты рождения/смерти, телефон, Max ID, предпочтительный канал, аватар, RU (обязательно имя) и EN (опционально) локализация.
- Валидация на уровне POST-обработчика: required first_name_ru, gender, допустимые values для lang, preferred_ch, date_prec.
- Редирект на `/admin/people` (статус 302) после успешного создания, рендер формы с ошибкой (400) при проблемах.
- Max Messenger contact mapsится на существующее поле `messenger_max_id` в таблице People.

## Update: M3-local — Local stub AI provider (HTTP client only)

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/services/ai_analyzer.py` — `AI_PROVIDER=local_stub` теперь делает POST на `AI_LOCAL_STUB_URL` с телом `{ "text": ... }`, безопасно маппит `summary/people/dates` в общий результат анализа и не роняет pipeline при transport/JSON ошибках.
- `.env` — дефолт `AI_LOCAL_STUB_URL` приведён к `http://localhost:9000/analyze`, при этом `AI_PROVIDER=disabled` сохранён как безопасное поведение по умолчанию.
- `scripts/test_ai_local_stub.py` — добавлен локальный smoke-сценарий для режимов `disabled`, `local_stub` без URL, `local_stub` с недоступным URL и `local_stub` с успешным HTTP-моком.

## Update: M2 — Provider-agnostic AI analyzer for Max -> Memory

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/services/ai_analyzer.py` — добавлен единый интерфейс `analyze_memory_text(text)` и provider-agnostic слой с режимами `disabled | mock | anthropic | local_stub` через `AI_PROVIDER`.
- `app/services/ai_analyzer.py` — сохранена обратная совместимость через `MemoryAnalyzer.extract_entities(...)` (адаптер поверх нового интерфейса), чтобы не ломать текущие вызовы MaxBot.
- `app/api/routes/bot_webhooks.py` — после успешного `create_memory_from_max(...)` добавлен не-блокирующий вызов анализа; ошибки AI не роняют webhook и не мешают persistence/ACK.
- `app/services/memory_store.py` — добавлена `attach_analysis_to_memory(memory_id, analysis_result)` для безопасного сохранения анализа в metadata (`transcript_verbatim`) без изменения схемы БД.
- `.env` — добавлены `AI_PROVIDER` (безопасный default: `disabled`) и `AI_LOCAL_STUB_URL` как задел под будущий локальный провайдер.
- Контур M1 сохранён: входящее сообщение в любом случае сохраняется в Memory; ACK-ответ в Max остаётся простым.

## Update: M1 — Min loop Max -> Memory complete

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/api/routes/bot_webhooks.py` — входящий webhook `/webhooks/maxbot/incoming` стабилизирован для M1: невалидный JSON и payload без текста корректно возвращают `400`, добавлен минимальный контур сохранения текстовых сообщений в Memory + автоответ в Max после успешного сохранения.
- `app/services/memory_store.py` — добавлена функция `create_memory_from_max(user_id, text, raw_payload)`: сохраняет текст в `Memories.content_text`, source в `Memories.source_type='max_messenger'`, пытается связать сообщение с Person по `messenger_max_id`/`messenger_tg_id`, и пишет `external_id`/raw payload в metadata (`transcript_verbatim`).
- `app/bot/max_messenger.py` — `send_message(user_id, text)` больше не использует хардкод `chat_id`; отправка идёт через `httpx` на `MAX_API_SEND_URL` с `chat_id=user_id`.
- person mapping оставлен минимальным и безопасным: если соответствия нет, запись сохраняется в общий inbox (`author_id=NULL`) без падений.
- temporal/family graph слои не затрагивались.

## Update: Task 6C.3.1 — Keyframe Mode Toggle and Stale Fetch Guard

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/web/templates/family_tree.html` — добавлен явный toggle `Слои времени: ON/OFF` в блоке keyframe-навигации, а также визуальная индикация активного режима и лёгкая подсветка текущего keyframe year.
- `app/web/static/js/family_graph.js` — wheel keyframe-navigation переведена в управляемый режим: при `OFF` wheel остаётся zoom/pan, при `ON` wheel листает keyframes и блокирует D3 wheel zoom через zoom filter.
- `app/web/static/js/family_graph.js` — добавлена защита от stale fetch на уровне request sequence в `loadAndRender`; устаревшие ответы игнорируются, чтобы не откатывать `activeYear` и текущий snapshot.
- Существующий fallback workflow по обычному year-input сохранён; backend/API не менялись.
- `tech-docs/family-graph-snapshot-timeline-notes.md` и `CHANGELOG.md` синхронизированы для трассируемости задачи 6C.3.1.

## Update: Task 6C.3 — Keyframe Navigation Prototype for Family Graph

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/web/static/js/family_graph.js` — добавлена прототипная keyframe-навигация поверх stable year update: сбор keyframe years из текущих graph-данных, состояние `currentKeyframeIndex`, переходы prev/next и wheel-navigation в режиме `По году`.
- `app/web/templates/family_tree.html` — добавлены минимальные кнопки `‹ предыдущий слой` / `следующий слой ›` и индикатор текущего keyframe year рядом с temporal-контролами.
- `tech-docs/family-graph-snapshot-timeline-notes.md` — добавлен раздел `Prototype 6C.3 — Keyframe Navigation Notes` (подход, ограничения, рекомендации для Phase 2).
- Backend/API не менялись; numeric year input и fallback к обычному year workflow сохранены.

## Update: Task 6C.2 — Stable Year Update Prototype for Family Graph

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/web/static/js/family_graph.js` — реализован прототип стабильного обновления снапшота при смене года (feature flag `USE_STABLE_UPDATE`): в режиме «По году» обновление идёт in-place через keyed joins и reuse существующей D3 simulation.
- Для существующих узлов сохраняются текущие координаты (`x/y/vx/vy`), что уменьшает layout jumping при переходах между соседними годами.
- Для появляющихся/исчезающих узлов и рёбер добавлены базовые fade-in/fade-out transition.
- Поведение режима «Сейчас» не изменено; backend/API не менялись.
- `tech-docs/family-graph-snapshot-timeline-notes.md` — добавлен раздел "Prototype 6C.2 — Stable Update Notes" с ограничениями и next steps.

## Update: Task 6C.1 — Snapshot Timeline Preparation (ADR-006 Follow-up)

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `tech-docs/family-graph-snapshot-timeline-notes.md` — добавлен краткий техдок по подготовке Snapshot Timeline: текущая точка входа year-mode, где происходит reload/fetch, почему сейчас есть layout jumping, и минимальный Phase 1 путь без backend-рефакторинга.
- Зафиксировано, что на текущем этапе wheel/swipe не внедрялись и runtime-логика семейного графа не менялась.
- Этап выполнен как engineering discovery после ADR-006: подготовка к будущей реализации temporal layers / snapshot navigation.

## Update: ADR-006 Proposal — Temporal Layers and Snapshot Navigation

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `tech-docs/adr/ADR-006.md` — добавлен новый ADR со статусом `Proposed`: концепция temporal layers/snapshots для семейного графа, keyframe-навигация (wheel/swipe), continuity между соседними снапшотами и staged implementation path.
- `tech-docs/README.md` — обновлён индекс ADR (добавлена запись ADR-006).
- Зафиксировано, что ADR-006 не требует немедленных изменений БД или backend-логики; это roadmap для UX/visualization эволюции поверх текущего режима `Сейчас/По году`.

## Update: Task 6A — Year Timeline Slider in Family Graph

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/web/templates/family_tree.html` — добавлен UI-элемент шкалы времени (`#year-slider`) и подпись «Год для режима «По году»» в панели управления графом.
- `app/web/static/js/family_graph.js` — рефакторинг работы с годом: выделены `getCurrentYearFromUI()`, `setYearInUI(year)`, `applyYearAndReloadGraph(year)`.
- `app/web/static/js/family_graph.js` — добавлена двусторонняя синхронизация input ↔ slider, диапазон лет `1900..(current+5)` и шаг `1`.
- `app/web/static/js/family_graph.js` — добавлен debounced reload (250мс) для запросов `/family/tree/json?year=...` при движении бегунка, чтобы не перегружать API.
- Поведение режимов: в «Сейчас» поле года и слайдер отключены (видимы, но не активны); в «По году» активны и управляют temporal-визуализацией.

## Update: ADR-005 Proposal — Union v2 and Temporal Strict Mode

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `tech-docs/adr/ADR-005.md` — добавлен новый ADR со статусом `Proposed`: целевая модель Union v2 (`union_type`, `single_parent`, adoption/guardianship через union), а также концепция двух temporal-режимов (soft/strict) для семейного графа.
- `tech-docs/README.md` — обновлён индекс ADR (добавлены ADR-003, ADR-004, ADR-005).
- Подчёркнуто, что изменение на текущем этапе документальное: без миграций и без изменения поведения v1.

## Update: Family Graph 5F — Temporal Filtering End-to-End Fix

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/services/family_graph.py` — `extract_year()` теперь корректно парсит даты в формате "DD.MM.YYYY" (хранится в БД), не только "YYYY-MM-DD". Год извлекается из последней части при разделении по ".". Также перезапущен сервис, т.к. `family_graph.py` был изменён уже после запуска (`union_to_node` получал корректные даты, но старый бинарный процесс не подхватывал изменения).
- Причина проблемы: `union.start_date` и `union.end_date` хранятся как строки "DD.MM.YYYY" (например, "06.11.1976"). Предыдущий `extract_year` разбивал по "-" и получал `int("06.11.1976")` → ValueError → None, что делало все union permanently active.
- Проверка: `year=1980` → union 1 (1976–1983) `is_active=True`, union 2 (2007+) `is_active=False`; `year=2010` → union 1 `is_active=False`, union 2 `is_active=True`. ✓

## Update: Family Graph 5C — Filter & Temporal Bug Fixes

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/services/family_graph.py` — `union_to_node` принимает `year`, вычисляет `is_active` относительно него; при переданном `year` персоны с `birth_year > year` не попадают в граф (backend-фильтрация).
- `app/web/static/js/family_graph.js` — `updateVisuals` переработан: строится `hiddenNodeIds` из фильтра "Умершие", затем `visibleEdgeIds` с учётом скрытых узлов, затем `visibleDegree` — union-узлы и изолированные person-узлы без видимых рёбер скрываются; `getRequestedYear()` в режиме "Сейчас" возвращает `null`; `forceCollide`/`linkDistance` увеличены для root-узла.
- Проверки: Python `ast.parse` OK, JS `esprima.parseScript` OK; `curl year=1977` вернул на 1 узел и 1 ребро меньше — фильтрация подтверждена.

---

## Update: Temporal Family Graph 5B — Visual Polish

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/web/templates/family_tree.html` — визуально улучшены temporal-контролы (`Сейчас/По году` как toggle), состояния кнопок истории, disabled-стили поля года и типографика нижней панели.
- `app/web/static/js/family_graph.js` — обновлены стили и поведение графа без изменения backend-логики: более явные состояния рёбер (`active`/`inactive`/`neutral`), hover/focus polish, подпись фокусного узла с годами жизни, дружелюбный temporal summary и refined CTA в нижней панели.
- Проверка: JS parse (`esprima.parseScript`) успешно; `timewoven.service` перезапущен.

## Update: Temporal Family Graph v2 (v1.22)

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/schemas/family_graph.py` — расширен контракт узлов/рёбер для temporal-данных (`death_year`, `start_date`, `end_date`, `is_active`, `is_active_for_year`).
- `app/services/family_graph.py` — добавлена year-aware логика для графа: вычисление активности связи на выбранный год и заполнение `valid_from`/`valid_to`.
- `app/api/routes/tree.py` — `/family/tree/json` поддерживает `year`; `/family/tree` прокидывает `year` в шаблон; `/family/timeline` поддерживает фильтры `person_id`/`union_id` для кнопок из нижней панели.
- `app/web/templates/family_tree.html` — добавлены temporal-контролы (режим `Сейчас/По году` + input года), прокинут `window.GRAPH_YEAR`.
- `app/web/static/js/family_graph.js` — добавлен temporal-режим загрузки с `year`, визуальное разделение active/inactive/neutral рёбер, расширение нижней панели (person/union) и переходы в timeline.
- Проверка: Python compile и JS parse пройдены; `timewoven.service` перезапущен; `/health` и оба варианта `/family/tree/json` (с и без `year`) возвращают `200`.

## Update: Family Graph Syntax Hotfix (v1.21.1)

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/web/static/js/family_graph.js` — исправлен синтаксический дефект в районе `line ~460`: восстановлена функция `updateDepthButtons()` и корректная структура скобок, из-за которой браузер ранее падал с `missing ) in parenthetical`.
- Выполнена синтаксическая проверка JS через `esprima.parseScript` (валидно).
- Перезапущен `timewoven.service`, подтверждён статус `active (running)`.
- Проверены endpoint'ы после рестарта: `/static/js/family_graph.js` -> 200, `/family/tree/json?root_person_id=1&depth=2` -> 200, JSON содержит `nodes` и `edges`.

## Update: Family Graph 4B — Bottom Panel UX (v1.21)

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/web/static/js/family_graph.js` — убран action-card showTooltip (кнопки Профиль/Корень/Закрыть поверх графа). Добавлен: showHoverTooltip (name-only, no actions), updateBottomPanel(), getUnionPartners(). Обновлён click handler: person → setFocus + updateBottomPanel; union → updateBottomPanel + visual ring. History nav обновляет нижнюю панель. State расширен: selectedUnionId.
- `app/web/templates/family_tree.html` — удалены CSS-стили action-card (.tt-actions, .tt-btn). #graph-tooltip упрощён до hover-label. Добавлены: CSS .gip-* (нижняя панель в палитре TimeWoven), HTML #graph-info-panel с .gip-placeholder / .gip-content / .gip-name / .gip-meta / .gip-actions.
- Подробности: CHANGELOG v1.21-family-graph-4b-ux.

## Update: Family Graph v2 Acceptance Hotfix (v1.20.1)

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/web/templates/family_tree.html` — удалены дублирующиеся Jinja-блоки (`extends`/`block`) после первичного деплоя Graph v2.
- `app/web/static/js/family_graph.js` — файл переписан в валидный единый v2 скрипт (устранён parse error `Unexpected end of input`).
- Выполнена приёмка через Playwright (реальный браузер): граф рендерится; click/focus, tooltip, filters, depth и history работают; JS page errors отсутствуют.

## Update: Family Graph v2 MVP (v1.20)

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

- `app/web/static/js/family_graph.js` — полная замена (Graph v2): focus mode, semantic edges, dim, filters, history, dark tooltip, depth controls.
- `app/web/templates/family_tree.html` — полная замена: controls panel, filter buttons, depth ±, history nav, #graph-tooltip.
- Подробности: CHANGELOG v1.20-family-graph-v2-mvp.

## Update: Navigation & Admin Security Fixes (v1.19)

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

* Applied navigation & admin security fixes per audit (Задание №1) — see CHANGELOG v1.19-nav-auth-security-fixes.
* `app/security.py` — полностью переписан: добавлена реальная auth-логика через cookie `tw_admin_session`, `make_admin_token()`, защита `require_admin` с редиректом на `/admin/login`.
* `app/api/routes/admin.py` — добавлены `import os`, guard `require_admin` в `GET /admin/avatars`, реальная проверка credentials в `POST /admin/login`, защита `next` от open redirect, установка сессионной cookie.
* `app/api/routes/tree.py` — исправлен redirect в `POST /family/reply/{id}`: `person_id=None` больше не попадает в URL.
* `timewoven.service` перезапущен — production-сервер теперь работает на актуальном коде.

### Result

* `/health` → 200 на production.
* `next=` в `_require_family_session` передаёт реальный URL запроса.
* Все admin-маршруты требуют auth (cookie `tw_admin_session`), иначе редирект на `/admin/login`.
* `POST /admin/login` не допускает open redirect.
* `POST /family/reply` не генерирует `422` при отсутствии `person_id`.

---

## Baseline: Stabilization & Control Phase Complete

Date: 2026-04-21

### Folders

docs/snapshots/tree_2026-04-21.txt

### Files (Critical)

* app/models.py
* .env
* nginx.conf
* docker-compose.yml (если есть)
* requirements.txt или package.json

### Logic

* Структура зафиксирована как исходная точка стабилизации
* Все изменения структуры отслеживаются через snapshots
* Любые изменения должны сопровождаться логированием (Handshake protocol)
* Закрытие любой сессии изменений допускается только после проверки заполнения обязательных журналов

---

## Update: Total Traceability Protocol (Mandatory)

Date: 2026-04-22

### Structural change

No

### Schema change

No

### Changes

* Зафиксирован обязательный процесс логирования для всех изменений в фазе «Стабилизация и Контроль».
* Введено обязательство по каждой задаче обновлять `CHANGELOG.md` с датой, типом изменения и кратким обоснованием.
* Подтверждено правило: любые структурные изменения каталогов/файлов фиксируются в `docs/PROJECT_LOG.md` с причиной.
* Подтверждено правило: изменения SQLAlchemy/PostgreSQL требуют синхронизации `docs/DATABASE_SCHEMA.md` и записи в `DB_CHANGELOG.md`.
* Введен инфраструктурный контроль: изменения `scripts/backup_manager.sh` и Nginx-конфигураций должны логироваться в журналах.

### Result

* Total Traceability включен как обязательный operational gate.
* Сессия изменений не считается завершенной без подтверждения, что все релевантные журналы обновлены.

---

## Update: FastAPI Max Bot Webhook Router

Date: 2026-04-21

### Structural change

Yes

### Schema change

No

### Changes

* Added MAX_BOT_ID=235301348589_bot to .env.
* Added new router app/api/routes/bot_webhooks.py with prefix /webhooks/maxbot.
* Added POST endpoint /incoming with JSON payload parsing.
* Added payload validation for text field with HTTP 400 on missing value.
* Connected router in app/main.py via app.include_router(bot_webhooks.router).

### Result

* FastAPI webhook endpoint for Max Messenger is integrated and ready for incoming events.
* Implemented outgoing message logic for MAX Messenger API using httpx.
* Integrated Max Bot with Persistence Layer: incoming stories are saved to `Memories` via `app/services/memory_store.py`.

## Update: Max Messenger Bot Architecture Start

Date: 2026-04-21

### Structural change

Yes

### Schema change

No

### Changes

* Started Phase 2.2 architecture for Max Messenger Bot.
* Added new bot module folder app/bot with app/bot/__init__.py.
* Added async integration scaffold in app/bot/max_messenger.py.
* Wired MemoryAnalyzer call path for incoming text processing.

### Result

* Repository scan completed for Max Bot metadata in TECH_PASSPORT.md, .env, and app/web/templates/admin/admin_login.html.
* No fixed Max Bot ID or status was found in current project files.

## Fix: ENV Override for Anthropic Models

Date: 2026-04-21

### Structural change

No

### Schema change

No

### Changes

* Enabled dotenv override=True to force reload of updated .env variables

### Result

```text
Primary model (claude-3-5-sonnet-20241022) failed: NotFoundError: Error code: 404 - {'type': 'error', 'error': {'type': 'not_found_error', 'message': 'model: claude-3-5-sonnet-20241022'}, 'request_id': 'req_011CaGoQ1gzwrGy7Qw2FGWNj'}
Fallback model (claude-3-haiku-20240307) also failed: NotFoundError: Error code: 404 - {'type': 'error', 'error': {'type': 'not_found_error', 'message': 'model: claude-3-haiku-20240307'}, 'request_id': 'req_011CaGoQ3LTvyAz1PJMDK9Ru'}; returning empty extraction
Extracted entities:
{'dates': [], 'persons': [], 'locations': []}
Person lookup result: person_id=2
```

[2026-04-21] — Automation Update
* Action: Enabled daily crontab backup at 03:00
* Status: Stabilization block officially closed.

[2026-04-21] — Structural Change
* Action: Added `app/services` service module baseline for Phase 2.1 AI-Enrichment.
* Status: Services folder registered in project structure.

[2026-04-21] — AI Integration Update
* Action: Migrated `app/services/ai_analyzer.py` from mock extraction to Anthropic Claude API.
* Details: Added `ANTHROPIC_API_KEY` env-based config, JSON parsing with error handling, and model fallback (Sonnet -> Haiku).
* Status: AI extraction pipeline connected to external LLM provider.

## Update: Anthropic Model Fix

Date: 2026-04-21

### Structural change

No

### Schema change

No

### Changes

* Updated ANTHROPIC_PRIMARY_MODEL to claude-3-5-sonnet-20241022
* Updated ANTHROPIC_FALLBACK_MODEL to claude-3-haiku-20240307

### Result

```text
Primary model (claude-3-5-sonnet-latest) failed: NotFoundError: Error code: 404 - {'type': 'error', 'error': {'type': 'not_found_error', 'message': 'model: claude-3-5-sonnet-latest'}, 'request_id': 'req_011CaGoBpaRp6tVC1KhfLuUz'}
Fallback model (claude-3-haiku-latest) also failed: NotFoundError: Error code: 404 - {'type': 'error', 'error': {'type': 'not_found_error', 'message': 'model: claude-3-haiku-latest'}, 'request_id': 'req_011CaGoBqevKfXwJ2vL4L8vB'}; returning empty extraction
Extracted entities:
{'dates': [], 'persons': [], 'locations': []}
Person lookup result: person_id=2
```

---
