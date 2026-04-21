# CHANGELOG — TimeWoven

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