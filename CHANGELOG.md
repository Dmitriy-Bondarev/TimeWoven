# CHANGELOG — TimeWoven

## [v1.22.28-admin-ux-depth10-t24] — 2026-04-23

### Feature | Admin UX | Family Graph

- **Feature (T24.1)**: в списке `/admin/people` ссылка `Редактировать` перемещена ближе к началу строки (после статуса записи) для работы без горизонтального скролла.
- **Feature (T24.2)**: максимальная глубина family graph повышена до `10` в backend (`/family/tree`, `/family/tree/json`) и frontend-контролах.
- **Feature (T24.3)**: форма `/admin/people/{person_id}/edit` перегруппирована в рабочие блоки (основные данные, даты/статусы, контакты, семейные связи, резерв под воспоминания) без изменения существующих маршрутов.

## [v1.22.27-union-9-family-correction-t23_4] — 2026-04-23

### Fix | Data Correction | Family

- **Fix (T23.4)**: выполнена корректировка `Unions.id=9` под новую семью: партнёры обновлены до `(57,58)`.
- Набор детей для союза 9 приведён к целевому `{16,59,60}` с SQL-proof до/после.
- Изменение data-only, без миграций схемы.

## [v1.22.26-max-live-replies-session-flow-t19] — 2026-04-23

### Feature | Max Bot | Live Replies For Session Flow

- **Feature (T19)**: добавлен контролируемый reply-слой для Max session flow в новом модуле `app/services/bot_reply.py`.
- Реализованы функции:
  - `build_ack_for_new_session(...)`
  - `build_ack_for_audio(...)`
  - `build_ack_for_finalize(...)`
- Основной режим: безопасные жёсткие шаблоны; опционально при `AI_PROVIDER=llama_local` — короткая вариация через AI с hard-limit длины (<=240 символов).
- Любые AI-сбои не ломают webhook: reply слой автоматически уходит в fallback шаблон.
- `bot_webhooks.py` подключён к `bot_reply` в 3 ключевых точках:
  - первое текстовое сообщение новой/пустой сессии;
  - подтверждение после аудио;
  - подтверждение после успешной финализации.
- Smoke-test подтверждён: `text -> audio -> Готово!` возвращает короткие user-friendly ответы и корректно завершает `session -> draft Memory`.

## [v1.22.25-finalize-command-normalization-t18d] — 2026-04-23

### Fix | Max Sessions | Finalize Command Parsing

- **Fix (T18.D)**: исправлен переход `Max session -> draft Memory` для команд завершения с пунктуацией (`Готово!`, `это всё!`, и т.д.).
- `is_finalize_command(...)` теперь нормализует ввод: `strip()`, `lower()`, удаление хвостовой пунктуации `! . ?`.
- В webhook text-ветке команда завершения не попадает в `draft_items` как обычный текст: вместо этого вызывается `finalize_session(...)`.
- Подтверждено live-сценарием: `текст -> голос -> Готово!` приводит к `session.status='finalized'`, заполненному `memory_id`, созданию `Memory(source_type='max_session', transcription_status='draft')`.
- Metadata памяти содержит `session_id`, `draft_items`, `audio_count`, `message_count`, `local_path` и audio-item поля транскрипции.

## [v1.22.24-max-audio-transcription-session-flow-t18c] — 2026-04-23

### Feature | Max Bot | Audio Transcription In Session Flow

- **Feature (T18.C)**: автоматическая транскрипция аудио встроена в session flow T18.B.
- После скачивания локального файла webhook пытается выполнить `TranscriptionService.transcribe_file(...)`.
- Аудио-элемент в `draft_items` теперь хранит: `audio_url`, `local_path`, `transcription_text`, `transcription_status`, `transcribed_at`, `transcription_error`.
- `draft_text` агрегируется из текстовых сообщений + успешных voice-фрагментов (`[voice] ...`).
- На `finalize_session(...)` AI анализ запускается по полному агрегированному тексту (включая voice fragments), а `Memory.transcript_verbatim` содержит полные raw `draft_items`.
- Fallback сохранён: при сбое транскрипции сессия не падает, аудио сохраняется, пользователь получает мягкий ACK.
- В `bot_webhooks.py` удалён legacy-дубликат `@router.post("/incoming")`; оставлен единый актуальный session-based handler.

## [v1.22.23-max-chat-sessions-t18b] — 2026-04-23

### Feature | Max Bot | Sessions + Draft Aggregation + Audio Hardening

- **Feature (T18.B)**: новый session-слой для Max-бота (`max_chat_sessions` таблица + `max_session_service.py`).
- Каждое входящее сообщение (текст или аудио) теперь добавляется в **черновик открытой сессии** вместо немедленного создания опубликованной Memory.
- Сессия финализируется командой **«Готово» / «Завершить» / «Это всё» / «done» / «finish»**: собирается `draft_text`, запускается AI-анализ, создаётся `Memory(transcription_status='draft')`.
- **Audio hardening**: аудиофайл гарантированно скачивается в `web/static/audio/raw/` при получении; в сессии хранятся и CDN URL, и локальный путь; при ошибке скачивания сессия продолжается (CDN URL сохраняется, в ACK добавляется предупреждение).
- **AI fallback**: при недоступности AI-провайдера сессия всё равно финализируется в `Memory(draft)`; ошибка логируется, `analysis_status='error'`.
- Контактные события (`MaxContactEvents`) — без изменений (T16).
- Миграция: `migrations/006_add_max_chat_sessions.sql` применена.

## [v1.22.22-llama-local-ai-provider-t18a] — 2026-04-23

### Feature | AI | Max Bot

- **Feature (T18.A)**: добавлен AI-провайдер `llama_local` в `ai_analyzer.py`.
- Читает URL из `AI_LLAMA_LOCAL_URL`; POST `{"text": ...}`; ожидает `{"summary", "people", "events", "dates"}`.
- Timeout 30 с; сетевые ошибки, таймаут и невалидный JSON возвращают `status="error"`, исключение наружу не пробрасывается.
- Поле `events` из ответа LLaMA сохраняется в `AnalysisResult` (новое поле, остальные провайдеры его не заполняют).
- `.env`: `AI_PROVIDER=llama_local`, `AI_LLAMA_LOCAL_URL=http://127.0.0.1:19000/analyze`.
- Туннель: `ssh -N -R 19000:localhost:9000 root@193.187.95.221` (Mac → VPS).
- Обновлены `TECH_PASSPORT.md` и `TimeWoven_Anchor_2026-04-23.md`.

## [v1.22.21-duplicate-people-cleanup-t17] — 2026-04-23

### Cleanup | People | Max Contacts

- **Cleanup (T17)**: `People.person_id IN (40, 43)` переведены в `record_status='test_archived'` — дубли, выявленные при ручной ревизии Max contact events после T16.
- FK-диагностика по всем таблицам показала нулевые ссылки на 40/43 — ребайнд не потребовался.
- `person_id IN (41, 42)` подтверждены как live-активные (`active`, `relative`, ru+en в `People_I18n`).
- Физическое удаление строк не выполнялось; `messenger_max_id` для 2 и 8 корректны.

## [v1.22.20-max-contact-events-no-autocreate-t16] — 2026-04-23

### Fix | Max Contacts | Duplicate Protection

- **Fix (T16)**: отключено авто-создание `People` из Max contact attachments в `/webhooks/maxbot/incoming`.
- **Feature (T16)**: добавлен минимальный contact inbox `MaxContactEvents` для enrichment-событий (`new|matched|merged|archived`) с сохранением raw payload.
- **Cleanup (T16)**: `People.person_id IN (35..39)` переведены в `record_status='test_archived'` (без удаления записей).
- **Cleanup (T16)**: тестовые marker memories `TEST CONTACT*` архивируются (`is_archived=true`, `transcription_status='archived'`, `source_type='max_contact_test_marker'`) и не попадают в live timeline.
- **Live UX hardening**: family surfaces (`who-am-i`, tree, timeline, welcome random memory) используют только `People.record_status='active'` и боевые published, non-archived memories.

## [v1.22.19-record-status-live-family-filtering-t14] — 2026-04-23

### Feature | Family UX | People

- **Feature (T14)**: добавлено поле `People.record_status` со значениями `active | archived | test_archived`, default `active`.
- **Live-family filtering**: записи со статусом `test_archived` скрыты из `who-am-i` + PIN flow, `/family/person/{id}`, `/family/tree/json`, `/family/timeline`.
- **Admin visibility**: `/admin/people` продолжает показывать все записи и теперь отображает колонку `record_status`.
- **Data patch**: в миграции T14 выполнено `person_id IN (20,21,22,23) -> record_status='test_archived'`.

## [v1.22.18-timeline-filtering-maiden-ui-polish-t13] — 2026-04-23

### Fix | Timeline | Profile

- Family timeline now shows only published items and hides technical raw blobs (T11).
- Maiden name is now shown as a secondary muted line under the main name (T12).

## [v1.22.17-role-select-admin-form-t9] — 2026-04-23

### Feature | Admin | People

- **Feature (T9)**: поле `Роль в системе` в админ-форме новой персоны переведено с текстового ввода на контролируемый `select`.
- **Role values**: используется фиксированный набор: `placeholder`, `relative`, `family_admin`, `bot_only`.
- **Backend guard**: добавлен whitelist/fallback в `admin.py` и `people_service.py`, чтобы исключить мусорные/случайные значения роли.
- **Schema**: изменений БД нет.

## [v1.22.16-maiden-name-support-p1_11-t8] — 2026-04-23

### Feature | UX | People

- **Feature (Task P1.11, T8)**: в админ-форму создания персоны добавлено поле `Девичья фамилия (при рождении)` (`maiden_name_ru`).
- **Backend normalization**: при создании персоны `maiden_name_ru` нормализуется (`strip`, пустая строка -> `NULL`) и сохраняется в `People.maiden_name`.
- **Family profile UX**: в карточке `/family/person/{person_id}` отображается формат `Имя Фамилия (урождённая X)`, только если `maiden_name` заполнено и отличается от текущей фамилии.
- **Regression-safe behavior**: если `maiden_name` отсутствует или совпадает с текущей фамилией, карточка показывает стандартное `Имя Фамилия` без скобок.
- **Validation**: выполнена E2E проверка через работающее приложение и подтверждены оба сценария отображения.

## [v1.22.15-who-am-i-exclude-deceased-p1_14] — 2026-04-22

### Bugfix | UX | Family Auth Flow

- **Bugfix (Task P1.14)**: экран `Кто вы?` теперь показывает только живых участников (`People.is_alive = 1`).
- **Flow hardening**: добавлен тот же фильтр в `POST /who-am-i` и `GET/POST /who-am-i/pin`, чтобы исключить выбор умерших через прямой URL или подмену `person_id`.
- **Product behavior**: умершие остаются в семейной модели (граф/карточки/история), но исключены из login/select-flow.

## [v1.22.14-product-backlog-bootstrap] — 2026-04-22

### Process | Documentation

- **Docs artifact**: в корень проекта добавлен постоянный реестр `PRODUCT_BACKLOG.md` для ведения продуктовых задач, статусов и решений.
- **Process update**: зафиксировано правило синхронизации backlog-изменений с `docs/PROJECT_LOG.md` и `CHANGELOG.md` для прозрачной трассировки продуктовых решений.

## [v1.22.13-admin-person-create-form-p1] — 2026-04-22

### Feature | Admin | People

- **Feature (Task P1, New person in one step)**: добавлены `GET/POST /admin/people/new` в `app/api/routes/admin.py` с серверной валидацией формы и созданием персоны через единый сервисный вызов.
- **Feature (Transactional create service)**: создан `app/services/people_service.py` с `create_person_with_i18n(...)`, который в одной транзакции создаёт `People` + обязательную RU-локализацию + опциональную EN-локализацию.
- **Feature (Max contact mapping)**: поле формы `max_user_id` маппится в `People.messenger_max_id`; поддержан `preferred_ch='Max'` и fallback `'None'`.
- **Feature (Admin UI)**: добавлен шаблон `app/web/templates/admin/admin_person_new.html` и кнопка `+ Новая персона` в `app/web/templates/admin/admin_people.html`.
- **Schema sync**: добавлена миграция `migrations/003_expand_preferred_channel_for_max.sql` и обновлены `create_postgres_schema.sql`, `docs/DATABASE_SCHEMA.md` для канала `Max`.

## [v1.22.12-local-stub-http-client-m3-local] — 2026-04-22

### Feature | AI | Local Stub

- **Feature (Task M3-local)**: `app/services/ai_analyzer.py` — `AI_PROVIDER=local_stub` теперь вызывает внешний локальный HTTP-endpoint через `AI_LOCAL_STUB_URL`, маппит `summary/people/dates` в стандартный `AnalysisResult` и игнорирует лишние поля ответа.
- **Safety (Local provider fallback)**: при отсутствии URL, недоступности сервиса, таймауте, не-200 ответе или невалидном JSON анализатор возвращает `status=error` и не поднимает исключение в webhook/pipeline.
- **Ops (Local defaults)**: `.env` — сохранён безопасный `AI_PROVIDER=disabled`, дефолт `AI_LOCAL_STUB_URL` обновлён на `http://localhost:9000/analyze`.

## [v1.22.11-max-memory-ai-provider-agnostic-m2] — 2026-04-22

### Feature | Bot | AI Abstraction

- **Feature (Task M2, Provider-agnostic analyzer)**: `app/services/ai_analyzer.py` — добавлен единый интерфейс `analyze_memory_text(text)` со стандартизированным результатом: `summary`, `persons`, `dates`, `locations`, `raw_provider`, `status`.
- **Feature (Config-driven providers)**: поддержаны `AI_PROVIDER=disabled|mock|anthropic|local_stub`; режим `disabled` безопасно возвращает `status=disabled`, `mock` выдаёт тестовую структуру без внешнего API, `local_stub` возвращает `not_implemented`.
- **Feature (Anthropic safety)**: существующая Claude-логика перенесена в отдельный провайдер с primary/fallback моделью и безопасной обработкой ошибок (без падения webhook).
- **Feature (Webhook integration)**: `app/api/routes/bot_webhooks.py` — после успешного `create_memory_from_max(...)` выполняется не-блокирующий вызов анализа; при ошибке AI transport+persistence не ломаются.
- **Feature (Metadata persistence, no schema changes)**: `app/services/memory_store.py` — добавлена `attach_analysis_to_memory(...)`, сохраняющая результат анализа в `Memories.transcript_verbatim` metadata.
- **Compatibility**: `MemoryAnalyzer.extract_entities(...)` оставлен как backward-compatible адаптер для старых вызовов в `app/bot/max_messenger.py`.

## [v1.22.10-max-memory-min-loop-m1] — 2026-04-22

### Feature | Bot | Transport/Persistence

- **Feature (Task M1, Min loop Max -> Memory)**: `app/api/routes/bot_webhooks.py` — входящий webhook `/webhooks/maxbot/incoming` теперь гарантированно сохраняет текстовые сообщения в `Memories` через минимальный persistence-контур.
- **Feature (Persistence helper)**: `app/services/memory_store.py` — добавлена `create_memory_from_max(user_id, text, raw_payload)` с базовым person mapping по `messenger_max_id`/`messenger_tg_id` и fallback в общий inbox (`author_id=NULL`).
- **Feature (Outbound reply)**: после успешного сохранения webhook вызывает `MaxMessengerBot.send_message(...)` с подтверждением: "Спасибо, я сохранил эту историю в семейный архив.".
- **Fix (Webhook validation)**: при отсутствии текста и отсутствии медиа webhook возвращает `400` (валидационная ошибка), вместо потенциальных `500`.
- **Fix (MAX send target)**: `app/bot/max_messenger.py` — `send_message` больше не использует хардкод chat_id; используется `MAX_API_SEND_URL` и входящий `user_id`.
- **Ops (Logging noise)**: удалены лишние отладочные записи в `webhook_test.log` из базового happy-path, оставлено компактное структурированное логирование через `logger`.

## [v1.22.9-family-graph-keyframe-mode-stale-fetch-guard-6c3_1] — 2026-04-22

### Feature | Frontend | UI/Graph Stabilization

- **Feature (Task 6C.3.1, Keyframe Mode toggle)**: `app/web/templates/family_tree.html` + `app/web/static/js/family_graph.js` — добавлен явный переключатель `Слои времени: ON/OFF` для управления wheel-поведением в temporal keyframes.
- **Behavior (Wheel scope + predictability)**: keyframe wheel navigation работает только в явном режиме `ON` и только в зоне графа/таймлайна; при `OFF` wheel возвращается к обычному D3 zoom.
- **Behavior (Zoom conflict safety)**: при `ON` D3 wheel zoom блокируется zoom-filter'ом, чтобы wheel однозначно листал keyframes без конфликта жестов.
- **Stability (Stale fetch protection)**: в `loadAndRender` добавлен request sequence guard; устаревшие fetch-ответы игнорируются и не могут откатить сцену на старый год.
- **UX (Minimal feedback)**: добавлена лёгкая подсветка текущего `Кадр: <год>` при быстрой keyframe-навигации.
- **Validation**: `family_graph.js` синтаксически валиден (`esprima.parseScript`).

## [v1.22.8-family-graph-keyframe-navigation-prototype-6c3] — 2026-04-22

### Feature | Frontend | UI/Graph

- **Feature (Task 6C.3, Keyframe timeline prototype)**: `app/web/static/js/family_graph.js` — добавлены keyframes на основе текущих graph snapshot-данных (birth/death/start/end years), состояние `currentKeyframeIndex` и переходы `goToPrevKeyframe()` / `goToNextKeyframe()`.
- **Feature (Normalization)**: keyframe years валидируются, дедуплицируются и сортируются по возрастанию; при отсутствии keyframes включается fallback на обычный year workflow.
- **Feature (UI)**: `app/web/templates/family_tree.html` — добавлены минимальные кнопки навигации `‹ предыдущий слой` / `следующий слой ›` и индикатор текущего кадра.
- **Feature (Wheel prototype)**: в режиме `По году` добавлена wheel-навигация по keyframes (throttled), использующая stable update path из 6C.2 без backend-изменений.
- **Validation**: `family_graph.js` успешно проходит `esprima.parseScript`.

## [v1.22.7-family-graph-stable-year-update-prototype-6c2] — 2026-04-22

### Feature | Frontend | Family Graph

- **Prototype (Task 6C.2)**: `app/web/static/js/family_graph.js` — добавлен feature flag `USE_STABLE_UPDATE` и прототип in-place обновления снапшота в режиме «По году» без полного teardown SVG.
- **Stable update path**: для year-переходов (`applyYearAndReloadGraph`) данные графа обновляются через keyed joins (nodes/edges), с сохранением координат существующих узлов и reuse текущей D3 simulation.
- **Temporal transitions**: добавлены мягкие fade-in/fade-out для появляющихся/исчезающих узлов и рёбер, чтобы уменьшить визуальный jump при смене года.
- **Safety**: режим «Сейчас» и обычный полный `render()` оставлены без изменения; прототип можно отключить через флаг.
- **Docs**: обновлён `tech-docs/family-graph-snapshot-timeline-notes.md` секцией "Prototype 6C.2 — Stable Update Notes".

## [v1.22.6-family-graph-snapshot-timeline-prep-6c1] — 2026-04-22

### Docs | Architecture | Frontend Research

- **Docs (Task 6C.1)**: добавлен инженерный разведочный документ `tech-docs/family-graph-snapshot-timeline-notes.md` по подготовке Snapshot Timeline для family graph.
- **Research (Current frontend)**: зафиксированы текущие entry points year-mode (`window.GRAPH_YEAR`, `state.temporalMode/selectedYear`), точка загрузки графа (`loadAndRender`) и факт полного пересоздания D3-сцены при смене года.
- **Roadmap (Phase 1)**: описан минимальный путь без backend-изменений: snapshot-controller на фронте, переходы по индексам снимков, reuse текущего `applyYearAndReloadGraph(year)`.
- **Risks**: отдельно зафиксированы источники layout jumping и границы работ, требующие отдельной задачи (keyed joins, reuse simulation, continuity policy, gestures).

## [v1.22.5-adr-006-temporal-layers-snapshot-navigation] — 2026-04-22

### Docs | Architecture

- **Architecture (ADR)**: добавлен `tech-docs/adr/ADR-006.md` со статусом `Proposed`: переход family graph от year-input модели к навигации по temporal snapshots/layers.
- **Scope (Frontend UX roadmap)**: зафиксированы этапы внедрения (flat keyframe timeline -> stable transitions -> optional layer-stack visualization) без обязательного 3D.
- **Compatibility**: runtime-код и схема БД не менялись; текущий режим `Сейчас/По году` остаётся baseline.
- **Docs (ADR Index)**: обновлён реестр `tech-docs/README.md` с новой записью ADR-006.

## [v1.22.4-family-graph-year-timeline-slider-6a] — 2026-04-22

### Feature | Frontend | UI/Graph

- **Feature (Task 6A, Timeline slider)**: `app/web/templates/family_tree.html` — добавлена UI-шкала времени (`input[type=range]`) рядом с year-input и краткий label для режима «По году».
- **Feature (Year sync)**: `app/web/static/js/family_graph.js` — добавлены функции `getCurrentYearFromUI()`, `setYearInUI(year)`, `applyYearAndReloadGraph(year)`; реализована синхронизация input ↔ slider.
- **Feature (Debounce)**: `app/web/static/js/family_graph.js` — добавлен `debounce(fn, delay)` и debounced перезагрузка графа (250мс) при перетаскивании слайдера в режиме «По году».
- **UX (Temporal modes)**: в режиме «Сейчас» year-input и слайдер остаются видимыми, но отключены; в режиме «По году» активируются и используют выбранный год.
- **Range policy (v1)**: диапазон лет установлен как `1900..(текущий год + 5)`, шаг `1`.

## [v1.22.3-adr-005-union-v2-proposal] — 2026-04-22

### Docs | Architecture

- **Architecture (ADR)**: добавлен `tech-docs/adr/ADR-005.md` с предложенным направлением Union v2: `union_type`, single-parent союзы, моделирование adoption/guardianship и будущий strict temporal mode.
- **Docs (ADR Index)**: обновлён реестр `tech-docs/README.md` — добавлены записи ADR-003, ADR-004, ADR-005 для актуального индекса.
- **Scope**: изменений схемы БД и runtime-кода нет; решение имеет статус `Proposed`.

## [v1.22.2-family-graph-filter-temporal-fixes-5c] — 2026-04-22

### Fix | Frontend | Backend

- **Fix (Deceased filter)**: `family_graph.js` — при отключении фильтра "Умершие" теперь скрываются и рёбра к скрытым узлам (раньше стрелки зависали в воздухе).
- **Fix (Children filter)**: `family_graph.js` — при отключении "Дети" осиротевшие узлы-дети без видимых рёбер полностью скрываются.
- **Fix (Partners filter)**: `family_graph.js` — union-узлы без видимых рёбер после отключения "Партнёры" скрываются автоматически.
- **Fix (Temporal year mode)**: `family_graph.py` — при передаче `year` узлы персон с `birth_year > year` не включаются в граф; `union_to_node` теперь вычисляет `is_active` относительно выбранного года, а не текущего.
- **Fix (now-mode year leak)**: `family_graph.js` — `getRequestedYear()` в режиме "Сейчас" возвращает `null`, не отправляя `year` в backend.
- **Fix (Focus collision)**: `family_graph.js` — `forceCollide` и `linkDistance` увеличены для root-узла (+6px и +28px), подписи не перекрываются.
- **Validation**: Python `ast.parse` OK, JS `esprima.parseScript` OK; `timewoven.service` перезапущен; `curl /health` 200.

## [v1.22.1-temporal-family-graph-visual-polish-5b] — 2026-04-22

### UX | Frontend

- **UX (Temporal graph polish)**: `app/web/templates/family_tree.html` — улучшен визуальный стиль контролов и нижней панели без изменения layout: toggle-группа `Сейчас / По году`, приглушённое disabled-состояние поля года, более явные состояния кнопок истории (`←/→`).
- **UX (Node/edge styling)**: `app/web/static/js/family_graph.js` — усилена визуальная дифференциация рёбер (`active`/`inactive`/`neutral`) по цвету, толщине и dash-стилю; сохранено полное скрытие рёбер при отключении фильтров `Партнёры/Дети`.
- **UX (Focus & hover)**: `app/web/static/js/family_graph.js` — добавлен мягкий hover-акцент узлов/подписей, refined focus-ring, компактные узлы и более заметные `union`-узлы; подпись фокуса расширена годами жизни.
- **UX (Bottom panel)**: `app/web/static/js/family_graph.js` + `app/web/templates/family_tree.html` — улучшена типографика и структура person/union summary; CTA-кнопки приведены к primary/secondary: `Перейти в профиль`, `Сделать корнем`, `Timeline человека/союза`.
- **Validation**: JS parse OK (`esprima.parseScript`), `timewoven.service` перезапущен.

## [v1.22-temporal-family-graph-v2] — 2026-04-22

### Feature | Backend | Frontend

- **Feature (Temporal payload)**: `app/schemas/family_graph.py` и `app/services/family_graph.py` расширены для temporal-графа.
  - `person` node: добавлены `death_year`.
  - `union` node: добавлены `start_date`, `end_date`, `is_active`.
  - `edge`: добавлено `is_active_for_year` + заполнение `valid_from`/`valid_to` по данным союза/рождения.
- **Feature (Year mode API)**: `app/api/routes/tree.py` — endpoint `/family/tree/json` теперь поддерживает query-параметр `year` (пример: `/family/tree/json?root_person_id=1&depth=2&year=2015`) и передаёт его в граф-сервис.
- **Feature (Temporal UI controls)**: `app/web/templates/family_tree.html` + `app/web/static/js/family_graph.js` — добавлены режимы `Сейчас` / `По году`, input года и перезагрузка графа с параметром `year`.
- **Feature (Temporal styling)**: на фронте рёбра визуально разделены по состоянию на год: `active` (обычный стиль), `inactive` (faded/серый), `neutral` (промежуточный стиль при отсутствии данных).
- **Feature (Bottom panel + timeline linkage)**: нижняя панель расширена для person/union (годы жизни, периоды союзов, дети, temporal summary) и добавлены кнопки перехода в timeline: `/family/timeline?person_id=...`, `/family/timeline?union_id=...`.
- **Feature (Timeline filters)**: `app/api/routes/tree.py` — `/family/timeline` принимает `person_id` и `union_id` для контекстного отображения связанных событий.
- **Validation**:
  - Python compile OK (`py_compile` для изменённых backend-файлов).
  - JS parse OK (`esprima.parseScript` для `family_graph.js`).
  - `timewoven.service` перезапущен и активен.
  - Проверки: `/health`, `/family/tree/json?root_person_id=1&depth=2`, `/family/tree/json?root_person_id=1&depth=2&year=2015` возвращают `200`.

## [v1.21.1-family-graph-syntax-hotfix] — 2026-04-22

### Bugfix | Frontend

- **Bugfix (JS Parse Error)**: `app/web/static/js/family_graph.js` — исправлен синтаксический дефект около `family_graph.js:460` (`Uncaught SyntaxError: missing ) in parenthetical`): восстановлен корректный блок `updateDepthButtons()` и баланс скобок.
- **Validation**: клиентский JS успешно парсится (`esprima.parseScript`) после деплоя, endpoint `/family/tree/json` возвращает валидные `nodes/edges`.
- **Infrastructure**: перезапущен `timewoven.service`, статус `active (running)`.

## [v1.21-family-graph-4b-ux] — 2026-04-22

### UX | Frontend

- **UX (Remove floating action-card)**: `app/web/templates/family_tree.html` — удалён тёмный action-card tooltip над узлами графа (HTML `#graph-tooltip`, CSS `.tt-actions`, `.tt-btn`, `.tt-meta`). Tooltip переработан в лёгкий hover-label (имя персоны, без кнопок, `pointer-events: none`).
- **UX (Bottom contextual panel)**: добавлен `#graph-info-panel` под панелью управления. При загрузке показывает root-персону. При клике на персону — обновляется: имя, год рождения, пол, кнопки «Перейти в профиль» и «Сделать корнем». Палитра панели соответствует TimeWoven (`--bg`, `--surface`, `--accent`).
- **UX (Union selection)**: клик по union-узлу — обновляет нижнюю панель (союз, имена участников из текущего графа). Действий для union нет (нет стабильного route). Union-узел при выборе получает amber-stroke `#f59e0b`.
- **UX (History nav)**: back/forward теперь также обновляют нижнюю панель по текущему focused person.
- **UX (Hint text)**: обновлён заголовочный подзаголовок (убрана ссылка на карточку).
- **No DB changes**: API `/family/tree/json` не изменён, схема БД не затронута.
- **Changed files**: `app/web/static/js/family_graph.js`, `app/web/templates/family_tree.html`.

## [v1.20.1-family-graph-acceptance-hotfix] — 2026-04-22

### Bugfix | QA

- **Bugfix (Template Render)**: `app/web/templates/family_tree.html` — удалены дублирующиеся `{% extends %}` / `{% block content %}`, которые вызывали `500` (`TemplateSyntaxError: Unexpected end of template`) на `/family/tree` после авторизации.
- **Bugfix (Frontend Asset Integrity)**: `app/web/static/js/family_graph.js` — устранено повреждение файла (смешение v1/v2 кода, `Unexpected end of input` в браузере). Файл принудительно переписан в единый валидный Graph v2 скрипт.
- **QA (Smoke Test)**: Выполнен browser-level smoke-test (Playwright, headless Chromium) с cookie-авторизацией: render=true, click_focus=true, tooltip=true, union_click_no_focus_change=true, filters=true, depth=true, history=true, page_errors=[].
- **Known non-blocking**: В console фиксируется внешний SRI warning для Font Awesome CSS (из базового шаблона), не влияет на рендер/работу семейного графа.

## [v1.20-family-graph-v2-mvp] — 2026-04-22

### Feature | UX | Visualization

- **Feature (Graph UX)**: Полная замена `app/web/static/js/family_graph.js` — Graph v2 (~290 строк). Старый v1 код удалён (два конфликтующих `mouseover`, click→navigate).
- **Feature (Focus Mode)**: Клик по персоне → фокус (dim остальных) + показ tooltip. Навигация в профиль — только через кнопку "Профиль →" в tooltip. Правая кнопка мыши → сменить корень графа (reroot + reload).
- **Feature (Focus History)**: Кнопки ← / → в панели управления — навигация по истории фокусировки. Amber-кольцо вокруг текущего фокуса.
- **Feature (Depth Controls)**: Кнопки − / + меняют глубину графа (1–5) и перезагружают данные через `/family/tree/json`.
- **Feature (Semantic Edges)**: Партнёрские рёбра — синие сплошные (#4a90e2); дочерние — зелёные пунктирные (#22c55e). Раздельные arrowhead-маркеры per edge type.
- **Feature (Dim)**: Не-соседние узлы и рёбра приглушаются до opacity 0.12 / 0.07. Союзные (union) узлы — 0.12 если не связаны с фокусом.
- **Feature (Filters)**: Три toggle-кнопки: Партнёры / Дети / Умершие — скрывают соответствующие рёбра или узлы в реальном времени.
- **Feature (Tooltip)**: Тёмный tooltip (#1a1a2e) с именем, мета (год рождения, †, пол) и тремя action-кнопками. Tooltip закрывается кликом по фону.
- **Template (family_tree.html)**: Полная замена — добавлена `.graph-controls` панель под канвасом, `#graph-tooltip` абсолютно позиционированный в `#graph-wrapper`, новые CSS-переменные. `window.GRAPH_DATA_URL` заменён на `window.GRAPH_ROOT_PERSON_ID` + `window.GRAPH_DEPTH`.
- **No DB changes**: API `/family/tree/json` не изменён, схема БД не затронута.

## [v1.19-nav-auth-security-fixes] — 2026-04-22

### Bugfix | Security | Infrastructure

- **Infrastructure (Deploy)**: Перезапущен `timewoven.service` после накопленных фиксов v1.14–v1.16; `GET /health` теперь возвращает `200 {"status":"ok"}` на production.
- **Bugfix (Navigation)**: `_require_family_session` в `tree.py` теперь сохраняет реальный URL запроса в параметр `next=` (включая query-строку). Ранее жёстко писал `/family/welcome`, из-за чего после логина пользователь всегда попадал на главную вместо запрошенной страницы. Проверено: `/family/timeline` → `next=/family/timeline`, `/family/tree?root_person_id=1` → `next=/family/tree%3F...`.
- **Security (Admin Auth)**: `app/security.py` — восстановлена реальная проверка `require_admin`: сравнивает cookie `tw_admin_session` с `sha256(ADMIN_USERNAME:ADMIN_PASSWORD)`. Переменные берутся из `.env`. Ранее функция всегда возвращала `None` (пропускала всех). Добавлена функция `make_admin_token()` для установки cookie при логине.
- **Security (Admin Auth)**: `GET /admin/avatars` — добавлена пропущенная проверка `require_admin`. Был единственный admin-маршрут без auth-guard.
- **Security (Open Redirect)**: `POST /admin/login` — добавлена валидация параметра `next`: принимаются только пути, начинающиеся с `/` без `//` и без схемы (`://`). При невалидном `next` — редирект на `/admin`. Аналогично уже реализованной защите в `who-am-i/pin`.
- **Security (Admin Login)**: `POST /admin/login` теперь реально сверяет `username`/`password` с `.env`-переменными `ADMIN_USERNAME`/`ADMIN_PASSWORD` и устанавливает сессионную cookie `tw_admin_session` (httponly, samesite=lax, 8 часов).
- **Bugfix (UX)**: `POST /family/reply/{memory_id}` — исправлен redirect при отсутствии `person_id`: больше не попадает строка `"None"` в query-параметр, которая вызывала `422 Unprocessable Entity` на GET-обработчике. Если `person_id` не передан — redirect на `?saved=1` без `person_id`.

## [v1.18-backup-manager-hotfix] — 2026-04-22

### Infrastructure | Backup Reliability

- **Infrastructure (Backup Script)**: `scripts/backup_manager.sh` усилен проверкой бинарника `pg_dump` через `command -v` с fail-fast ошибкой при отсутствии, чтобы исключить silent-fail в cron окружении.
- **Infrastructure (Operations)**: Создана директория `/root/projects/TimeWoven/backups/daily/archive` и выполнен ручной тестовый запуск бэкапа с подтверждением генерации артефактов в `backups/daily/`.
- **Infrastructure (Scheduler)**: Обновлена crontab-запись на запуск через полный путь и рабочую директорию: `cd /root/projects/TimeWoven && /bin/bash /root/projects/TimeWoven/scripts/backup_manager.sh >> /root/projects/TimeWoven/backups/daily/backup_manager.log 2>&1`.

## [v1.17-total-traceability-protocol] — 2026-04-22

### Infrastructure | Process Control

- **Infrastructure (Governance)**: Введен обязательный протокол логирования всех изменений проекта (Total Traceability) в фазе «Стабилизация и Контроль».
- **Process Rule (CHANGELOG)**: После выполнения любой задачи необходимо добавить запись в `CHANGELOG.md` с датой, типом изменения (`Feature|Bugfix|Security|Infrastructure`) и кратким описанием «что и зачем».
- **Process Rule (Structure)**: При структурных изменениях каталогов/файлов проекта требуется запись в `docs/PROJECT_LOG.md` с причиной изменения.
- **Process Rule (Schema Sync)**: При любом изменении SQLAlchemy-моделей или схемы PostgreSQL требуется немедленная синхронизация `docs/DATABASE_SCHEMA.md` и запись в `DB_CHANGELOG.md`.
- **Process Rule (Infra Control)**: Изменения в backup-скриптах (включая `scripts/backup_manager.sh`) и Nginx-конфигурации подлежат обязательной фиксации в журналах изменений.
- **Session Gate**: Сессия изменений считается завершенной только после подтверждения, что обновлены все релевантные журналы (`CHANGELOG.md`, `docs/PROJECT_LOG.md`, `docs/DATABASE_SCHEMA.md`, `DB_CHANGELOG.md` при schema-изменениях).

## [v1.16-max-audio-ingestion-minimal] — 2026-04-22

### Feature | Audio Ingestion

- **Feature (Ingestion)**: `bot_webhooks.py` теперь при входящем MAX audio attachment пытается скачать файл локально в `app/web/static/audio/raw/` с предсказуемым именем `max_{attachment_id}_{timestamp}.{ext}`.
- **Backwards compatible storage**: внешний `audio_url` по-прежнему сохраняется в поле `Memories.audio_url`; локальный путь сохраняется в `Memories.transcript_verbatim` как JSON-ключ `local_audio_path`.
- **Fallback safety**: при ошибке скачивания webhook не падает, память всё равно создаётся в статусе `pending_manual_text`, а в metadata проставляется `audio_download_error=download_failed`.
- **Admin playback source selection**: `admin.py` и `admin_transcriptions.html` теперь используют локальный путь как приоритетный `src` плеера, а при его отсутствии автоматически откатываются на внешний URL.
- **Whisper readiness**: подготовлена база для следующего шага авто-транскрибации через `TranscriptionService` (локальный файл уже доступен на диске).

## [v1.15-audio-pipeline-audit] — 2026-04-22

### Bugfix | Audio Pipeline

- **Bugfix (CODE)**: `admin.py` — фильтр `/admin/transcriptions?status=pending` теперь включает статус `pending_manual_text`. Ранее все реальные аудио-записи из MAX webhook были невидимы в UI (webhook сохранял со статусом `pending_manual_text`, но фильтр смотрел только на `["pending", "draft"]`).
- **Bugfix (UX)**: `admin_transcriptions.html` — добавлен CSS-класс `.status-pending_manual_text` (янтарный цвет) для корректного рендера badge у аудио-записей из MAX.
- **Анализ (DATA)**: Записи IDs 8 и 9 в Memories с `audio_url LIKE 'example.com%'` подтверждены как тестовые данные из ручного дебага (`webhook_test.log` строки 11-12, 17-18). Не баг кода. SQL для soft-mark задокументирован.
- **Анализ (INFRA)**: MAX CDN URL (`vd509.okcdn.ru`) истекает через ~24 часа (`expires` параметр). Реальное production-аудио воспроизведению недоступно после истечения. Требуется локальное кеширование аудио при приёме webhook.
- **Анализ (ARCH)**: `TranscriptionService` (Whisper) существует но нигде не вызывается. Текущий пайплайн — ручная транскрипция: пользователь отправляет текст следом за аудио. Автоматическая транскрипция через Whisper — следующий шаг.

## [v1.14-route-debug] — 2026-04-22

### Bugfix | Infrastructure

- **Bugfix**: Добавлен маршрут `GET /health` в `main.py` — возвращает `{"status": "ok"}`. Ранее возвращал 404.
- **Bugfix**: `_require_family_session` теперь передаёт реальный текущий URL в параметр `?next=` вместо хардкоженного `/family/welcome`. Пользователь после логина возвращается на запрошенную страницу (например `/family/timeline`).
- **Bugfix**: `who_am_i_pin_submit` теперь корректно использует параметр `next` при редиректе после успешного PIN-входа (ранее всегда отправлял на `/family/welcome`). Добавлена защита от open redirect (принимаются только пути, начинающиеся с `/`).
- **UX Navigation**: в профиле добавлен переход `карточка человека -> семейный граф` через deep-link `/family/tree?root_person_id={id}`.
- **Graph Focus/Highlight**: страница графа прокидывает `root_person_id` в клиентский JS и подсвечивает/фокусирует соответствующую персону при загрузке (фиксированный root + центрирование через zoom transform после завершения layout).
- **Анализ данных**: `audio_url = https://example.com/...` — проблема в данных, не в коде. Тестовые записи из ручного дебага бота. SQL для поиска/очистки приложен ниже в документации.

## [v1.13-final-stabilization] — 2026-04-21
### Day Finalization

- MAX Bot API: Полная интеграция. Исправлена отправка сообщений (перевод ID в query-параметры).
- Smart Linker: Реализована логика склейки «Аудио + Текст» для формирования «Золотых записей».
- Onboarding: Добавлена автоматическая регистрация родственников через пересылку контактов в бота.
- Database: Проведена миграция таблицы `Memories` (добавлена колонка `is_archived`).
- UX: Добавлена иконка «Связи» в глобальное меню для быстрого доступа к графам.

## [v1.12-daily-impulse-push-start] — 2026-04-21

### Max Messenger Bot (Phase 2.8)

- Добавлен сервис `app/services/daily_impulses.py` с пулом универсальных вопросов и `get_random_impulse()`.
- В `app/services/memory_store.py` добавлена проверка активности `has_memory_today(person_id)`.
- В `app/bot/max_messenger.py` добавлен метод `send_daily_impulse(person_id)` для инициативной отправки вопроса пользователю.
- В `app/api/routes/admin.py` добавлен тестовый эндпоинт `POST /admin/test-impulse/{person_id}` для ручного триггера импульса.

## [v1.11-maxbot-registration-flow] — 2026-04-21

### Max Messenger Bot (Phase 2.7)

- Добавлена таблица состояния бота `bot_sessions` для хранения шага регистрации (`AWAITING_FIO_DOB`).
- Реализован полный New User Registration Flow в `app/bot/max_messenger.py`.
- Ветка `Новый` теперь сохраняет сессию и ожидает сообщение с форматом `ФИО, ГГГГ-ММ-ДД`.
- Добавлен парсинг входного текста регистрации и создание нового профиля (`People` + `People_I18n`) с привязкой `messenger_max_id`.
- После успешной регистрации сессия удаляется и бот отправляет приветственное сообщение.

## [v1.10-maxbot-user-identification] — 2026-04-21

### Max Messenger Bot (Phase 2.6)

- Реализован User Identification Flow в `app/bot/max_messenger.py`.
- При новом `user_id` бот отправляет приветствие и список родственников без `messenger_max_id`.
- Добавлена обработка ответа номером: выбранному профилю проставляется текущий `messenger_max_id`.
- Добавлена обработка ответа `Новый` с TODO-заглушкой на создание профиля.
- После успешной идентификации истории сохраняются в `Memories` с привязкой к найденному `person_id`.

## [v1.9-maxbot-persistence-layer] — 2026-04-21

### Max Messenger Bot (Phase 2.4)

- Добавлен сервис хранения `app/services/memory_store.py` с `save_raw_memory(user_id, text, audio_url)` для записи входящих историй в таблицу `Memories`.
- Интегрировано сохранение воспоминаний в `app/bot/max_messenger.py` в методе `process_incoming_text`.
- Для сохраненных историй выставляется `transcription_status='published'` и `source_type='max_bot'`.
- Добавлен TODO для будущей привязки `user_id` мессенджера к `person_id` (в текущей схеме `People` нет `external_id/messenger_id`).

## [v1.8-maxbot-voice-support] — 2026-04-21

### Max Messenger Bot (Phase 2.3)

- Добавлена поддержка голосовых сообщений в Max Bot: обработка `voice`/`audio`/`attachment(type=audio)` в webhook-роутере.
- Реализован метод `process_incoming_audio` в `app/bot/max_messenger.py`:
  - отправка уведомления пользователю о старте расшифровки,
  - скачивание аудиофайла во временный файл,
  - транскрибация через сервис `app/services/transcription.py`,
  - передача распознанного текста в `process_incoming_text`.
- Добавлен сервис транскрибации `TranscriptionService` (`app/services/transcription.py`) с методом `transcribe_file`.

## [v1.7-maxbot-webhook-api] — 2026-04-21

### Max Messenger Bot (Phase 2.2)

- Добавлен FastAPI-роутер вебхука Max Messenger: app/api/routes/bot_webhooks.py.
- Реализован POST-эндпоинт /webhooks/maxbot/incoming для приема JSON payload.
- Добавлена базовая валидация входящего payload: при отсутствии text возвращается HTTP 400.
- Подключена передача payload в app.bot.max_messenger.max_messenger_webhook.
- В .env добавлен ID бота: MAX_BOT_ID=235301348589_bot.

## [v1.6-max-bot-architecture] — 2026-04-21

### Max Messenger Bot (Phase 2.2)

- Запущена архитектурная подготовка интеграции Max Messenger Bot: добавлен каркас модуля app/bot.
- Добавлен базовый асинхронный webhook-каркас app/bot/max_messenger.py.
- В каркасе интегрирован вызов MemoryAnalyzer из app/services/ai_analyzer.py для первичной обработки входящего текста.

## [v1.5-ai-enrichment] — 2026-04-21

### AI Enrichment

- Добавлен модуль `app/services/ai_analyzer.py` с базовым классом `MemoryAnalyzer` для mock-анализа текстов воспоминаний.
- Добавлен тестовый pipeline-скрипт `scripts/test_pipeline.py` для прогона entity extraction и проверки поиска персоны `Алексей` через SQLAlchemy.
- Интегрирован Anthropic API (`Claude`) в `MemoryAnalyzer`: извлечение `dates/persons/locations` через `claude-3-5-sonnet-20241022` с fallback на `claude-3-haiku-20240307`, ответ парсится через `json.loads`.
- В `requirements.txt` добавлена зависимость `anthropic` и поддержка переменной окружения `ANTHROPIC_API_KEY`.

## [v1.4-backup-security] — 2026-04-21

### Резервное копирование (G-F-S)

- Добавлен автоматизированный скрипт `scripts/backup_manager.sh` для ежедневных резервных копий.
- В nightly-процессе формируются:
  - `pg_dump` PostgreSQL,
  - архив всего проекта,
  - отдельный архив upload-директорий (`audio/uploads`, `images/uploads`).
- Все ежедневные артефакты сохраняются в `/root/projects/TimeWoven/backups/daily/`.
- Реализована ротация по правилам G-F-S:
  - в daily-зоне удаляются файлы старше 60 дней, кроме файлов, созданных в воскресенье,
  - по воскресеньям бэкапы дополнительно копируются в архивную зону,
  - в архивной зоне удаляются файлы старше 1 года.

### Безопасность Explorer

- Усилен ежедневный пароль доступа к TW Explorer: длина хэша увеличена с 8 до 16 символов.

## [v1.3-postgres] — 2026-04-19

### Инфраструктура и БД

- PostgreSQL 14 установлен и настроен на сервере Hostkey VPS. [cite:21]  
- Создана база `timewoven`, пользователь `timewoven_user` с доступом к БД. [cite:21]  
- Схема 13+ таблиц развёрнута в PostgreSQL, данные перенесены из SQLite.  
- Резервные копии схемы/данных зафиксированы в `/backups/2026-04-17/`. [cite:29]  
- `DATABASE_URL` перенесён в `.env`, загрузка через `load_dotenv` до инициализации приложения. [cite:29]

### Перенос данных в PostgreSQL (состояние на 2026‑04‑17)

- People: 9, People_I18n: 18, Events: 6  
- Memories: 3 → впоследствии дополнены до 9 (фактический count на 2026‑04‑19). [cite:29]  
- MemoryPeople: 16, Quotes: 3  
- AvatarHistory: 4, RelationshipType: 12  
- PersonRelationship: 26, Unions: 2, UnionChildren: 5

### Нормализация временной модели (PersonRelationship)

- Убраны `NULL` из `valid_to` для связей: открытые интервалы приведены к `9999-12-31`. [cite:31]  
- Для `bioparent` (`relationship_type_id = 1`) и `child` (`relationship_type_id = 2`) `valid_from` заполнен из даты рождения ребёнка (`People.birth_date`). [cite:31]  
- Для `bioparent`/`child` `valid_to` зафиксирован как `9999-12-31` (родство не обрезается по смерти). [cite:31]  
- Для `spouselegal` (`relationship_type_id = 3`) `valid_to` обрезан по дате смерти одного из супругов (если есть `People.death_date`), с учётом кастов `::date`. [cite:31]  
- Таблица `Unions` зафиксирована как источник дат начала/окончания браков (`start_date`/`end_date`); полная синхронизация `valid_from`/`valid_to` с `Unions` запланирована в следующей версии. [cite:31]

### Веб-инфраструктура и HTTPS

- Подняты HTTPS‑сертификаты Let’s Encrypt для доменов: `timewoven.ru`, `www.timewoven.ru`, `app.timewoven.ru`. [cite:22][cite:29]  
- Настроен единый Nginx‑конфиг:
  - HTTP → HTTPS редиректы для всех доменов.
  - `timewoven.ru` / `www.timewoven.ru` → статический лендинг (`/var/www/timewoven`). [cite:29]
  - `app.timewoven.ru` → `proxy_pass http://127.0.0.1:8000` (Uvicorn). [cite:29]
- Добавлены `X-Forwarded-Proto`, `X-Real-IP`, `X-Forwarded-For`, `Host` в proxy headers. [cite:29]

### Приложение: FastAPI / маршруты / фронтенд

- `app/main.py`:
  - Загрузка `.env` через `python-dotenv` перенесена до импорта роутеров и подключения к БД. [cite:29]
  - Инициализированы `Jinja2Templates` и подключены web‑шаблоны из `app/web/templates`. [cite:29]
- Корневой маршрут `/`:
  - Переведён с JSON‑заглушки на `TemplateResponse("family/home.html", ...)`. [cite:29]
  - Теперь выбирает последнюю `Memory` с непустым `author_id` и текстом, подтягивает `Person`, `PersonI18n` и `avatar_url`. [cite:29]
- Маршруты семьи и дерева (`app/api/routes/tree.py`): [cite:29]
  - `GET /` — импульс дня с реальным человеком из БД.
  - `GET /family/person/{person_id}` — карточка человека (`profile.html`).
  - `GET /family/tree?root_person_id=1&depth=2` — интерактивный граф семьи.
  - `GET /family/timeline` — таймлайн (воспоминания + события).
  - `GET /who-am-i` / `POST /who-am-i` — выбор пользователя и redirect на PIN‑форму.
  - `GET /who-am-i/pin` / `POST /who-am-i/pin` — PIN‑верификация и redirect на `next?person_id=...`.
  - `GET /family/reply/{memory_id}` / `POST /family/reply/{memory_id}` — просмотр и сохранение ответов семьи (`Quotes`).
- Админ-маршруты (`app/api/routes/admin.py`): [cite:29]
  - `GET /admin` → redirect на `/admin/transcriptions`.
  - `GET /admin/transcriptions` — список транскрипций с именами/аватарами.
  - `POST /admin/transcriptions/{id}/publish` — публикация транскрипции.
  - `GET /admin/people` — список людей (исправлен путь, был `/admin/admin/people`).
  - `GET /admin/login` / `POST /admin/login` — форма входа и временный login‑flow.
  - `GET /admin/avatars` — форма для загрузки аватаров.
- Legacy‑роутер `family_tree.py` убран из подключения в `main.py`, но оставлен в проекте как рез