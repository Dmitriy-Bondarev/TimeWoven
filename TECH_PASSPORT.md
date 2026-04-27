# 📸 Технический паспорт проекта: TimeWoven (v1.3-postgres)


> **Дата обновления:** 2026-04-27  
> **Автор:** Дмитрий Бондарев  
> **Статус:** Active


---


## 1. Обзор проекта


**TimeWoven** — цифровая экосистема семейного наследия: вместо сухого генеалогического дерева в центре стоят «Воспоминания» как субъективные единицы смысла (аудио, текст, фото, ответы семьи), привязанные к людям, событиям, местам и эпохам. [cite:20][cite:29]


Рабочая версия (`v1.3-postgres`) развёрнута на отдельном VPS, использует FastAPI + Uvicorn, PostgreSQL 14, Nginx и Jinja2‑шаблоны. Лендинг и приложение разделены по доменам `timewoven.ru` и `app.timewoven.ru`. [cite:29][cite:22]


| Параметр            | Значение                                               |
|---------------------|--------------------------------------------------------|
| Репозиторий         | `git@github.com:Dmitriy-Bondarev/TimeWoven.git`        |
| Продакшен URL (app) | `https://app.timewoven.ru`                             |
| Лендинг URL         | `https://timewoven.ru`                                 |
| WWW redirect        | `https://www.timewoven.ru` → `https://timewoven.ru`    |
| Сервер              | `193.187.95.221`                                       |
| Документация        | `tech-docs/` + `docs/` + материалы на Mac              |
| Баг-трекер          | GitHub Issues                                          |
| Лицензия            | Private                                                |


---


## 2. Стек технологий


### 2.1 Ядро


| Слой              | Технология        | Версия        | Назначение                                     |
|-------------------|-------------------|---------------|-----------------------------------------------|
| Язык              | Python            | 3.11+         | Основной язык бэкенда                         |
| Фреймворк         | FastAPI           | 0.110+        | REST/HTML, маршрутизация, валидация           |
| ASGI-сервер       | Uvicorn           | current       | Запуск FastAPI-приложения                     |
| ORM               | SQLAlchemy        | 2.0+          | Работа с БД, модели, запросы                  |
| База данных       | PostgreSQL        | 14+           | Основное рабочее хранилище                    |
| Шаблонизатор      | Jinja2            | 3.1+          | Серверный рендеринг HTML                      |
| i18n              | YAML + Jinja      | минимальный   | Локализация (RU/EN), фильтры `t` / `ts`       |


Runtime‑окружения (dev/prod) используют PostgreSQL через `DATABASE_URL` в `.env`. SQLite не используется в коде, а старые дампы лежат в `data/`. [cite:19][cite:21]


### 2.2 Инфраструктура


| Компонент          | Технология        | Назначение                                     |
|--------------------|-------------------|-----------------------------------------------|
| Веб-сервер         | Nginx             | Reverse proxy, статика лендинга, SSL termination |
| ASGI-сервер        | Uvicorn           | Запуск FastAPI-приложения                     |
| SSL/TLS            | Certbot / Let’s Encrypt | Сертификаты для всех доменов             |
| Процесс-менеджер   | systemd           | Автозапуск и мониторинг `timewoven.service`   |
| CI/CD              | GitHub + manual deploy | `git pull` + перезапуск сервиса            |
| Operational protocol | bash + git + flock | Protected snapshots, clean state gate, rollback (см. §5.5.2) |


### 2.3 Внешние интеграции (план)


| Сервис             | API / SDK             | Назначение                           |
|--------------------|-----------------------|--------------------------------------|
| Telegram Bot       | python-telegram-bot   | «Импульс дня» и уведомления (backlog) |
| Whisper / ASR      | local Whisper small (VPS) | Транскрибация аудиовоспоминаний (active) |


**Актуальное решение (2026-04-24):** Claude / Anthropic API выведен из активного контура проекта. Текущий рабочий путь — локальные провайдеры на VPS: `local_llm` для анализа текста и `local Whisper small` для транскрибации аудио. Legacy-поддержка Anthropic может оставаться как опциональная, но не должна быть default/рекомендуемой.


### 2.4 AI services on VPS (local LLM + Whisper)


**Назначение:** держать чувствительные семейные данные и тяжёлый вывод ML **на той же VPS**, что и приложение, с предсказуемой задержкой и без обязательной передачи сырого аудио/текста в публичные API.


| Systemd / каталог | Роль | Доступ приложения |
|-------------------|------|-------------------|
| **`timewoven-llm.service`** | Локальная **LLM** (Docker Compose в `ops/local_llm/`, образ с GGUF), HTTP **127.0.0.1:9000** | Анализ воспоминаний, резюме, прочие AI-фичи через провайдера `local_llm` / local HTTP в `app/services/ai_analyzer.py` (URL из `.env`) |
| **`timewoven-whisper.service`** | Локальный **Whisper (small)**, **faster-whisper** в Docker, **127.0.0.1:9100** | Транскрибация голосовых файлов; HTTP API в `ops/whisper_small/service.py` |


**Взаимодействие:** FastAPI вызывает эти сервисы **только по localhost**; схема «приложение → Nginx → внешний ASR/LLM» для базового сценария **не** требуется. Обновление моделей/контейнеров **независимо** от релиза веб-приложения (пересборка `docker compose` в соответствующем каталоге `ops/`).


**Зачем так:** (1) приватность — семейный контент остаётся в контуре VPS; (2) предсказуемая стоимость и задержка; (3) можно масштабировать RAM/CPU диска под ML (см. раздел 5) без смены внешнего провайдера.


### Интеграция с Max Messenger
* **Тип:** Входящий Webhook (FastAPI)
* **ID Бота:** `235301348589_bot`
* **Endpoint:** `POST /webhooks/maxbot/incoming`
* **Роутер:** `app/api/routes/bot_webhooks.py`
* **Обработчик логики:** `app.bot.max_messenger.MaxMessengerBot`
* **Статус:** Минимальный контур `Max -> Memory` замкнут (M1): входящий текст сохраняется в `Memories` и отправляется короткий ack-ответ в чат. Базовый person mapping работает по `messenger_max_id`; при отсутствии соответствия используется inbox (`author_id=NULL`).
* **M2 (AI abstraction):** после сохранения памяти webhook может вызвать provider-agnostic анализатор `analyze_memory_text(...)`.
   - Провайдер выбирается через `.env`. **Текущий рабочий провайдер анализа: `local_llm`** (VPS). `anthropic/claude` — legacy/optional и не используется как текущий путь.
   - При `disabled`/ошибке провайдера webhook не падает; сохранение Memory и ACK остаются гарантированными.
   - Результат анализа (если есть) сохраняется в metadata памяти (`transcript_verbatim`) без изменений схемы БД.
   - `local_stub` использует внешний локальный HTTP-endpoint (`AI_LOCAL_STUB_URL`) и безопасно возвращает `status=error`, если сервис недоступен или ответ невалиден.
   - `llama_local` (**T18.A, 2026-04-23**) — провайдер для локального LLaMA-совместимого HTTP-сервера (Mac M5 Pro). Читает URL из `AI_LLAMA_LOCAL_URL`, делает `POST {"text": ...}`, ожидает ответ `{"summary", "people", "events", "dates"}`. Доступен через SSH-туннель (`ssh -N -R 19000:localhost:9000 root@193.187.95.221`). При любой сетевой ошибке, таймауте или невалидном JSON безопасно возвращает `status="error"`, не роняя сервис.


---


## 3. Архитектура


### 3.1 Высокоуровневая схема


```text
┌─────────┐    HTTPS      ┌─────────┐    proxy_pass      ┌──────────┐
│ Browser │ ─────────────►│  Nginx  │───────────────────►│ Uvicorn  │
└─────────┘               └─────────┘                    └──────────┘
      ▲                         │                              │
      │                         │ / (timewoven.ru)             ▼
      │                         ├── static landing       ┌──────────┐
      │                         │   /var/www/timewoven   │ FastAPI   │
      │                         │                        │ app.main  │
      │                         └── / (app.timewoven.ru) └──────────┘
      │                                                          │
      └──────────────────────────────────────────────────────────▼
                                                            ┌──────────┐
                                                            │PostgreSQL│
                                                            │   14+    │
                                                            └──────────┘
```


### 3.2 Фактическая структура каталогов (срез 2026-04-27)


```text
/root/projects/TimeWoven/
├── app/
│   ├── main.py
│   ├── security.py
│   ├── api/
│   │   ├── timeline.py
│   │   └── routes/
│   │       ├── admin.py
│   │       ├── bot_webhooks.py
│   │       ├── family_tree.py        # legacy, исторический роутер
│   │       ├── tree.py
│   │       └── TW_Explorer.py
│   ├── core/
│   │   ├── i18n.py                   # YAML-based i18n + Jinja-фильтры t / ts
│   │   ├── security.py
│   │   └── whoami_experiment.py
│   ├── db/
│   │   ├── base.py
│   │   └── session.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── event.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── family_graph.py
│   ├── services/
│   │   ├── ai_analyzer.py
│   │   ├── family_access_service.py
│   │   ├── family_graph.py
│   │   ├── people_service.py
│   │   ├── person_alias_service.py   # SHIM (см. §3.3 и backlog T-FAMILY-ACCESS-REBUILD)
│   │   ├── timeline_event_view.py    # view-модель событий timeline (T42)
│   │   ├── timeline_service.py
│   │   └── transcription.py
│   └── web/
│       ├── index.html
│       ├── templates/
│       │   ├── base.html
│       │   ├── family_tree.html
│       │   ├── family_tree_list.html
│       │   ├── admin/                # admin UI (dashboard, people, person, access, diagnostics)
│       │   ├── family/               # family flow (welcome, profile, timeline, reply, memory_new, и др.)
│       │   └── site/
│       │       ├── landing.html
│       │       └── landing_en.html
│       └── static/
│           ├── audio/                # processed/ + raw/ + uploads/
│           ├── images/               # avatars/, brand/, uploads/
│           ├── js/
│           │   └── family_graph.js
│           ├── site/
│           │   ├── site.css
│           │   └── theme.css
│           ├── favicon.png
│           ├── favicon-32.png
│           ├── logo.png
│           ├── logo-32.png
│           ├── logo-64.png
│           └── logo-128.png
├── locales/                           # i18n: RU/EN (app, family, landing)
│   ├── en/{app,family,landing}.yml
│   └── ru/{app,family,landing}.yml
├── docs/
│   ├── PROJECT_OPS_PROTOCOL.md       # операционный протокол v1.0 (см. §5.5.2)
│   ├── CNAME
│   ├── index.html
│   └── logo.png
├── scripts/
│   ├── ops/                          # safety scripts (см. §5.5.2)
│   │   ├── clean_state_gate.sh
│   │   ├── safety_snapshot.sh
│   │   ├── rollback_to_snapshot.sh
│   │   └── README.md
│   ├── backup_manager.sh
│   └── watcher.py
├── archive/
├── backups/
│   └── daily/                        # postgres_dump_*, project_*, uploads_* (см. §5.6)
├── data/
│   ├── backups/
│   └── raw/
├── migrations/
├── tech-docs/
│   ├── README.md
│   └── adr/
├── temp/
│   ├── .gitkeep
│   └── README.md
├── .env
├── .gitignore
├── CHANGELOG.md
├── DB_CHANGELOG.md
├── FAMILY_GRAPH_ANALYSIS.md
├── README.md
├── TECH_PASSPORT.md
├── PROJECT_LOG.md
├── PRODUCT_BACKLOG.md
├── TimeWoven_Anchor_2026-04-23.md
├── TimeWoven_Anchor_2026-04-25.md
├── TimeWoven_Anchor_2026-04-27.md    # снимок состояния после восстановления
├── deploy.sh
├── deploy_landing.sh
├── requirements.txt
└── venv/ или .venv/
```


**Снапшоты вне репозитория** (mode 700):
/root/projects/TimeWoven_snapshots/
├── INDEX.log
├── <TASK_ID>/ # rolling, TTL ~30 дней
└── protected/ # без авто-удаления
├── CLEAN-START-2026-04-27/ # первая защищённая точка чистого старта
└── STASH-REFERENCE-2026-04-26/ # архив трёх stash дня инцидента


### 3.3 Модульная архитектура (по коду)


| Модуль              | Файл(ы)                    | Ответственность                                  |
|---------------------|----------------------------|--------------------------------------------------|
| App entrypoint      | `app/main.py`              | Инициализация FastAPI, загрузка `.env`, подключение роутов и templates, регистрация i18n-фильтров на всех Jinja2Templates через `_ensure_jinja_i18n_globals()`, startup-проверка `_assert_family_memory_new_route` |
| Security (app)      | `app/security.py`          | Высокоуровневая логика безопасности (require_admin и др.) |
| Admin audit log     | `app/core/admin_audit.py`  | JSONL audit log попыток входа в админку (`logs/admin_audit.log`) |
| **i18n core**       | **`app/core/i18n.py`**     | **YAML-based i18n: `install_jinja_i18n()`, фильтры `t` / `ts`, `detect_language()`, `set_context_lang()`, `reset_context_lang()`. Источник переводов — `locales/{ru,en}/{app,family,landing}.yml`** |
| DB base             | `app/db/base.py`           | Базовые настройки SQLAlchemy                     |
| DB session          | `app/db/session.py`        | `SessionLocal` и engine                          |
| Models              | `app/models/__init__.py`, `event.py` | SQLAlchemy-модели (агрегированы в `__init__.py`) — Person, Memory, Quote, Union, Event, EarlyAccessRequest, FamilyAccessSession, PersonAccessBackupCode, AvatarHistory и др. |
| Schemas             | `app/schemas/family_graph.py` | Pydantic-схемы для семейного графа           |
| Timeline API        | `app/api/timeline.py`      | Логика таймлайна на уровне API                  |
| Routes (family/admin)| `app/api/routes/tree.py`, `admin.py` | Маршрутизация для семьи и админки          |
| Legacy routes       | `app/api/routes/family_tree.py` | Исторический роутер дерева (подключение убрано из main, файл оставлен как референс — кандидат на расследование `T-DUPLICATE-FAMILY-TREE-ROUTE-INVESTIGATE`) |
| Services            | `app/services/family_graph.py`, `timeline_service.py`, `ai_analyzer.py`, `transcription.py`, `people_service.py` | Сервисы графа, таймлайна, AI-анализа, транскрибации |
| **Person aliases**  | **`app/services/person_alias_service.py`** | **SHIM-модуль (восстановлен из `.pyc` после инцидента 2026-04-26): экспортирует `ALIAS_TYPES` и `ALIAS_STATUS`. Полная функциональность — задача `T-FAMILY-ACCESS-REBUILD` в backlog.** |
| **Timeline events** | **`app/services/timeline_event_view.py`** | **View-модель событий таймлайна (T42, без изменений БД и без миграций): dataclass `TimelineEventView` + фабрика `memory_to_timeline_event_view()`. Используется `app/api/routes/tree.py` для `/family/timeline`.** |
| Web templates       | `app/web/templates/...`    | Все HTML‑шаблоны (family, admin, site)          |
| Static              | `app/web/static/...`       | JS, CSS, логотипы, аватары, аудио               |
| Family + TOTP       | `app/api/routes/tree.py`, `app/services/family_access_service.py` | Публичные URL `/family/p/{public_uuid}`, `/family/access/...`, сессия `tw_family_access` |


**Утрачено в инциденте 2026-04-26 (см. `PROJECT_LOG.md`):**
- `app/core/theme.py` — модуль `get_active_theme_preset(db)`. Временно заменён в `app/main.py` на статическое значение `request.state.active_theme = "current_dark"`. Восстановление — задача `T-CORE-THEME-RESTORE` в backlog.


### 3.4 Организация документации


Проект использует трёхуровневую иерархию документации плюс отдельный документ операционного протокола:


#### **docs/** — Публичная документация и операционный протокол


- **`PROJECT_OPS_PROTOCOL.md`** — операционный протокол v1.0 (с 2026-04-27): правила Clean State Gate, Safety Snapshot, Rollback, шаблон ТЗ для implementation-агента, разделение ролей. Обязателен к исполнению; реализация в `scripts/ops/` (см. §5.5.2).
- **`CNAME`** — конфиг доменов для GitHub Pages (содержит `timewoven.ru`).
- **`logo.png`** — логотип проекта, используется лендингом.


**Политика:** Если файл нужен только для разработки или это техническая документация → переместить в `tech-docs/`.


#### **tech-docs/** — Архитектурная документация и инженерные материалы


Основной дом для всей документации, имеющей отношение к внутреннему устройству проекта:


- **`README.md`** — индекс архитектурной документации с реестром ADR и ссылками.
- **`adr/`** — Architecture Decision Records (ADR-001, ADR-002, ..., ADR-006).
  - Каждый ADR описывает одно архитектурное решение: контекст, рассмотренные варианты, решение, последствия.
  - Шаблон: `adr/ADR.template.md` (в `temp/project_docs/`).
  - Новые ADR добавляются коммитом вида: `docs: add ADR-{NNN} — {краткое описание}`.
- **`DATABASE_SCHEMA.md`** — полное техническое описание схемы PostgreSQL с таблицами, колонками, ограничениями и примерами.
- **`snapshots/`** — снимки состояния для истории и отладки.
  - `tree_2026-04-21.txt` — текстовая структура семейного графа на конкретную дату.
  - Новые снимки добавляются по необходимости.
- **`family-graph-snapshot-timeline-notes.md`** — исследовательские заметки и анализ по графу и таймлайну (часть итератива).


**Политика:** Все техдокументы, анализы и ADR-ы хранятся здесь. Никогда не усложняй раздел `docs/`.


#### **temp/** — Рабочая песочница и шаблоны


Папка для локальных и экспериментальных файлов, **полностью игнорируемая git** (кроме `.gitkeep` и `README.md`):


- **`.gitkeep`** — маркер пустой папки.
- **`README.md`** — описание назначения папки и типичного использования (SQL-дампы, CSV-экспорты, отладочные скрипты, черновики миграций).
- **`project_docs/`** — шаблоны и примеры для документации:
  - `ADR.template.md` — шаблон нового ADR.
  - `DB_CHANGELOG.template.md` — шаблон записи в DB_CHANGELOG.
  - `TECH_PASSPORT.template.md` — шаблон технического паспорта.
  - `README.template.md` — шаблон README.
  - `requirements.template.txt` — шаблон requirements.
  - `examples/` — примеры заполненных документов.


**Политика:** `.gitignore` настроена на `temp/*` кроме `.gitkeep` и `README.md`. Локальные дампы, эксперименты и черновики остаются в песочнице и не попадают в репозиторий.


#### **Корень репо:** Основные артефакты и операционная логика


- **`TimeWoven_Anchor_2026-04-27.md`** — текущий якорь, срез «как сейчас» после восстановления и установки протокола; ранее: `TimeWoven_Anchor_2026-04-25.md`, `TimeWoven_Anchor_2026-04-23.md`.
- **`PROJECT_LOG.md`** — операционный журнал всех значимых обновлений и решений. Включает развёрнутый post-mortem инцидента 2026-04-26 (раздел `## INCIDENT 2026-04-26`).
- **`TECH_PASSPORT.md`** — этот файл, общий технический паспорт; описывает **факт** в коде, не намерение (требование §1.4 операционного протокола).
- **`PRODUCT_BACKLOG.md`** — живой реестр задач (P-задачи, T-задачи) с статусами и решениями.
- **`CHANGELOG.md`** — История релизов и фич (для конечных пользователей).
- **`DB_CHANGELOG.md`** — История изменений схемы БД и миграций.
- **`FAMILY_GRAPH_ANALYSIS.md`** — расширенный анализ семейного графа и доменной модели.


---


## Безопасность админки

### Авторизация
- **Cookie:** `tw_admin_session` (HttpOnly, SameSite=Lax). Значение = `sha256(ADMIN_USERNAME:ADMIN_PASSWORD)`.
- **Файл реализации:** `app/security.py` (45 строк → расширен до ~120 строк после T-ADMIN-HARDENING-2026-04-27).
- **Зависимость:** `require_admin(request)` подключена к 35 эндпоинтам.
- **Login route:** `POST /admin/login` (handler `admin_login_submit` в `app/api/routes/admin.py`).
- **Logout route:** `GET/POST /admin/logout`.

### Rate limit на /admin/login
- In-memory bucket по IP: 5 попыток/мин и 20 попыток/час.
- Реализация: `app/security.py::check_login_rate_limit()`.
- IP получается через `get_client_ip()` с учётом `X-Forwarded-For` (первый элемент).
- При превышении: HTTP 429 + запись в audit log.

### Idle timeout админской сессии
- 30 минут бездействия → cookie отзывается через `delete_cookie`, редирект на `/admin/login?next=...`.
- Реализация: in-memory dict `_ADMIN_LAST_SEEN` в `app/security.py`, проверка в `require_admin()`.
- Sliding window: каждое валидное обращение к админке обновляет `last_seen`.
- **Env override:** `TW_ADMIN_IDLE_TIMEOUT_SECONDS` (по умолчанию `1800`).
- **Ограничение:** state хранится в памяти процесса; при рестарте `timewoven.service` таймер начинается заново при первом обращении.

### Audit log
- **Файл:** `logs/admin_audit.log` (JSONL).
- **Реализация:** `app/core/admin_audit.py::log_login_attempt(ip, username, result)`.
- **Поля записи:** `ts` (UTC ISO), `event=admin_login_attempt`, `ip`, `username` (≤64 chars), `result` (`success`/`fail`/`rate_limited`).
- **Env override:** `TW_LOG_DIR` (по умолчанию `logs`).
- **Гарантия:** функция никогда не падает (OSError suppressed), не блокирует запрос.

### Что НЕ реализовано (P2/P3 кандидаты в backlog)
- CSRF protection
- 2FA / TOTP
- Redis для idle-store (переживание рестартов)
- Prometheus-метрики попыток входа

### Env переменные admin
| Переменная | По умолчанию | Назначение |
|---|---|---|
| `ADMIN_USERNAME` | `admin` | Имя админа |
| `ADMIN_PASSWORD` | `""` | Пароль админа (обязательная) |
| `TW_EXPLORER_SALT` | `timewoven-explorer` | Соль для daily password |
| `TW_ADMIN_IDLE_TIMEOUT_SECONDS` | `1800` | Idle timeout сессии (сек) |
| `TW_LOG_DIR` | `logs` | Директория для admin_audit.log |

## 4. Доменная модель (high-level)


### 4.1 Основные сущности (по назначению)


По текущей версии кода сущности агрегированы в `app/models/__init__.py`; по доменной логике используются:


- Person / PersonI18n — люди в семейном графе и их локализованные поля.
- PersonRelationship — связи (родители, дети, браки, и др.).
- Union / UnionChildren — браки/союзы и привязка детей к союзам.
- Memory — воспоминания (аудио, текст, фото).
- Quotes — ответы семьи на воспоминания.
- Event — доменные события (отдельный модуль `event.py`). [cite:24][cite:31]
- EarlyAccessRequest — заявки на ранний доступ (waitlist).
- FamilyAccessSession / PersonAccessBackupCode — семейные сессии и backup-коды для TOTP-флоу (см. §4.4).
- AvatarHistory — история загруженных аватаров.


### 4.2 Граф и таймлайн


- Граф семьи строится в `app/services/family_graph.py` и сериализуется через `app/schemas/family_graph.py`, выводится шаблонами `family_tree.html` / `family_tree_list.html` и `family_graph.js`. [cite:29]
- Таймлайн реализован комбинацией `app/api/timeline.py`, `timeline_service.py` и шаблона `family/timeline.html`. С 2026-04-26 поверх памяти строится тонкий **view-слой** `app/services/timeline_event_view.py` (без изменений БД и без миграций), используемый в `/family/timeline` через `memory_to_timeline_event_view()`. [cite:29]


#### Roadmap: main timeline — от memory-centric к event-centric (T42, 2026-04-26)


- **Текущее состояние:** основная семейная лента опирается на **воспоминания** (`Memories` — текст, пересказ, суть `essence_text` и т.д.) и существующие правила публикации/аудитории. Для отображения карточек используется промежуточный view-слой (см. §3.3, `timeline_event_view.py`).
- **Целевое направление (backlog T42):** **производный** слой **событий** (`MemoryEvent` + участники) поверх памяти: короткие, сортируемые, с датой/местом/уверенностью и ссылкой на фрагмент источника; **первоисточник** по-прежнему оригинальный текст/запись memory, а не подмена его карточкой события.
- **Семья:** `/family/timeline` в перспективе собирается из событийного слоя с **мягким fallback**, если извлечение ещё не выполнено или неудачно.
- Детали сущностей, non-goals и фазы — `PRODUCT_BACKLOG.md` (T42), decision — `PROJECT_LOG.md` (2026-04-26).


### 4.3 Temporal‑подход (в двух словах)


Temporal‑модель (valid_from/valid_to для PersonRelationship и Unions) описана детально в `DB_CHANGELOG.md` и ADR, и используется для восстановления состояния семьи на произвольную дату. [cite:31][cite:35]


### 4.4 Family access & TOTP (безопасность семейной зоны)


**Модель доступа**
- У каждой персоны в `People` есть стабильный **`public_uuid`**; публичные ссылки ведут на **`/family/p/{public_uuid}`**, без раскрытия числового `person_id` в URL.
- **Вход** для гостя: форма на **`/family/access/{public_uuid}`** (TOTP из приложения-аутентификатора и/или **одноразовые backup-коды**), после успешной проверки — **cookie** сессии и редирект на запрошенную страницу.
- **Guard** семейных страниц (`_require_family_zone` в `app/api/routes/tree.py`): при отсутствии валидной семейной сессии — редирект на **форму доступа по тому же `public_uuid`**, с параметром `next=`, а не на старый who-am-i для публичных путей.
- Старые URL **`/family/person/{id}`** сохраняются как совместимость: ответ **301** → **`/family/p/{public_uuid}`**.


**TOTP и политика**
- Секрет TOTP **хранится в БД в зашифрованном виде** (Fernet, ключи окружения `TW_FAMILY_FERNET_KEY` / dev-seed, см. `family_access_service.py`).
- Проверка кода: **6 цифр**, `pyotp.TOTP(...).verify(code, valid_window=1)` — **±1** временной слот.
- **Rate limit:** не более **20** попыток на скользящем окне **15 минут** на пару **(IP клиента, public_uuid)** (in-process deque в `family_access_service.py`).


**Сессии и reset**
- Активные логины хранятся в **`family_access_sessions`** (хеш непрозрачного токена, срок, отзыв).
- **Cookie** `tw_family_access`: **HttpOnly**, **SameSite=Lax**, **Secure** при HTTPS (см. `set_family_access_cookies` / `cookie_secure_flag`).
- В админке **reset** доступа: обнуляется секрет TOTP, очищаются backup-коды, **отзываются** все сессии персоны, доступ **закрыт** до повторного setup.


**Админка:** `GET /admin/people/{id}/access` — обеспечение `public_uuid` при первом заходе (`_ensure_public_uuid`), показ **полного** публичного URL (`TW_PUBLIC_BASE_URL` / `request.base_url` / fallback `https://app.timewoven.ru`), копирование в буфер. Подробности — [TimeWoven_Anchor_2026-04-27.md](TimeWoven_Anchor_2026-04-27.md).


---


## 5. Инфраструктура и деплой


### 5.1 Сервер


| Параметр            | Значение                                  |
|---------------------|-------------------------------------------|
| Хостинг             | Hostkey VPS                               |
| ОС                  | Ubuntu 22.04 LTS                          |
| IP                  | `193.187.95.221`                          |
| SSH                 | `root@193.187.95.221`                     |
| Путь к проекту      | `/root/projects/TimeWoven`                |
| Путь к снапшотам    | `/root/projects/TimeWoven_snapshots/` (mode 700, вне репо) |
| Python env          | `/root/projects/TimeWoven/venv` или `.venv` (активное окружение) |
| **RAM (срез 2026-04-25)** | **~11 Gi** total (существенный рост к ранним конфигурациям **~1.8 Gi** в ADR-003) |
| **vCPU**            | **6**                                     |
| **Диск (root)**     | **~157 Gi** total, **~130 Gi** свободно (~14% занято) — запас под аудио, Docker-слой, модели LLM/Whisper, **ежедневные дампы** в `backups/daily` и **снапшоты** в `TimeWoven_snapshots/` |


Сервер по объёму RAM/диска **рассчитан** на хранение семейного аудио, локальные контейнеры **LLM + Whisper** (`ops/local_llm`, `ops/whisper_small`) и регулярные бэкапы без внешнего object storage «по умолчанию».


### 5.2 PostgreSQL


| Параметр | Значение |
|----------|----------|
| Host     | `localhost:5432` |
| Database | `timewoven` |
| User     | `timewoven_user` |
| DSN      | `postgresql+psycopg2://timewoven_user:***@localhost:5432/timewoven` |


Подключение к PostgreSQL тестируется через `app/db/session.py` и небольшой скрипт в README: выводит counts по Person и Memory. На 19.04.2026: `Person count = 9`, `Memory count = 9`. [cite:29]


### 5.3 Systemd unit


```ini
# /etc/systemd/system/timewoven.service
[Unit]
Description=TimeWoven FastAPI Application
After=network.target postgresql.service


[Service]
User=root
WorkingDirectory=/root/projects/TimeWoven
ExecStart=/root/projects/TimeWoven/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
EnvironmentFile=/root/projects/TimeWoven/.env


[Install]
WantedBy=multi-user.target
```


### 5.4 Nginx и HTTPS


- Все три домена (`timewoven.ru`, `www.timewoven.ru`, `app.timewoven.ru`) защищены Let’s Encrypt‑сертификатами. [cite:22]
- HTTP → HTTPS редиректы настроены единым конфигом.
- `timewoven.ru` и `www.timewoven.ru` обслуживают лендинг из `/var/www/timewoven` (RU-версия в корне, EN-версия в `/en/` через `deploy_landing.sh`).
- `app.timewoven.ru` проксирует на `http://127.0.0.1:8000` (Uvicorn), передаются заголовки `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`. [cite:29][cite:22]


### 5.5 Процедура деплоя


```bash
ssh root@193.187.95.221
cd /root/projects/TimeWoven


git pull origin main
source .venv/bin/activate  # или source venv/bin/activate
pip install -r requirements.txt


systemctl restart timewoven.service
systemctl status timewoven.service --no-pager
curl -s https://app.timewoven.ru/health
```


**Обертки в репозитории:** в корне проекта `deploy.sh` (по сути `git pull origin main` + `systemctl restart timewoven` / `timewoven.service`) и `deploy_landing.sh` — сборка/копирование лендинга в `/var/www/timewoven` и reload nginx. С 2026-04-26 `deploy_landing.sh` опционально публикует EN-версию (`landing_en.html` → `/var/www/timewoven/en/index.html`), если исходник присутствует.


**Перед каждым новым заданием** (с 2026-04-27): обязательны `bash scripts/ops/clean_state_gate.sh` (PASS) и `bash scripts/ops/safety_snapshot.sh <TASK_ID>`. См. §5.5.2 и `docs/PROJECT_OPS_PROTOCOL.md`.


### 5.5.1 Admin UI / front-stabilization (срез 2026-04-26)


- **`/admin/people`:** поиск (id/имя) и клиентские фильтры живут **во второй строке `<thead>`** таблицы; над таблицей — счётчик «Показано n из m». Ссылка **«Алиасы»** ведёт на `/admin/people/{id}/aliases`; в колонке алиасов используются поля **`label` и `alias_type`** (v2-модель в бэкенде), не устаревшие имена полей.
- **`/explorer/`**, **`/admin/avatars`:** приведены к **gold**-токенам (тёмный фон, акцент `#f59e0b`, согласованные surface/input), без смены маршрутов и бизнес-логики.


### 5.5.2 Operational protocol & safety scripts (срез 2026-04-27)


Введён по итогам инцидента 2026-04-26 (см. `PROJECT_LOG.md` — `## INCIDENT 2026-04-26`).


**Документ:** `docs/PROJECT_OPS_PROTOCOL.md` v1.0 — единый источник правды по тому, как мы безопасно меняем систему. Описывает 4 уровня защиты, шаблон ТЗ, разделение ролей (автор / Perplexity главный исследователь / VSCode-Cursor implementation-агент), правило DEVIATION-RULE.


**Скрипты:** `scripts/ops/`
- **`clean_state_gate.sh`** — проверка чистоты репо и сервиса перед началом задания (6 проверок: git status / stash / branch / log sync / systemctl / health).
- **`safety_snapshot.sh`** — полный архив рабочего дерева (включая untracked) + git bundle + опционально pg_dump. Поддерживает rolling-30-дней и `--protected` режим без TTL.
- **`rollback_to_snapshot.sh`** — откат к снапшоту с автоматическим pre-rollback snapshot для двойной страховки.


**Каталог снапшотов:** `/root/projects/TimeWoven_snapshots/` (mode 700, вне репозитория).


**Защищённые точки (без авто-удаления):**
- `protected/CLEAN-START-2026-04-27/` — первая в истории проекта точно зафиксированная точка чистого старта (52M: `worktree.tar.gz` 28M + `repo.bundle` 24M + `meta.txt`).
- `protected/STASH-REFERENCE-2026-04-26/` — архив трёх stash дня инцидента (`.diff` + `.stat` для каждого), сохранён до явного `git stash drop`.


**Workflow:** перед каждым новым заданием обязательны `clean_state_gate.sh` (PASS) и `safety_snapshot.sh <TASK_ID>`. Каждое задание имеет ТЗ по шаблону из секции 6.1 протокола (SCOPE-LOCK / DO-NOT-TOUCH / PRE-CHECK / DEVIATION-RULE / EXIT-CRITERIA). Все git-операции, которые могут конкурировать с git-extension Cursor IDE, оборачиваются в `flock --timeout 30 .git/index.lock.flock <git command>`.


### 5.6 Резервное копирование (срез 2026-04-25, проверка 2026-04-26)


**2026-04-26 (OP-DIAG-BACKUP):** ежедневные артефакты `postgres_dump_20260426-030002.sql.gz`, `project_20260426-030002.tar.gz`, `uploads_20260426-030002.tar.gz` проверены на целостность (`gzip -t` / листинг `tar`); лог: `backups/daily/backup_manager.log`. Дополнительно перед работами по слою timeline: ручные `postgres_dump_pre_timeline_20260426-1629.sql.gz` + `project_pre_timeline_20260426-1630.tar.gz` (тот же `pg_dump` и те же `tar`‑исключения, что в `scripts/backup_manager.sh`).


**База данных**
- Скрипт **`scripts/backup_manager.sh`**: `pg_dump` по `DATABASE_URL` из `.env`, сжатие **gzip** в каталог **`backups/daily/`** с именем `postgres_dump_<UTC>.sql.gz`.
- Параллельно создаётся **снимок кода/проекта** (tar, с исключениями для ненужного объёма) и **архив upload-папок** — `app/web/static/audio/uploads`, `app/web/static/images/uploads` (если каталога нет — пишется маркер, чтобы прогон был прозрачным).
- **Ретация** по mtime (порядка **60 дней**), на **воскресенья (UTC)** копии **дополнительно** складываются в `backups/daily/archive/`.


**Пользовательские медиа и сырьё**
- Критично для восстановления: **аудио-загрузки** (см. пути выше); при появлении единого raw-хранилища (например `app/web/static/audio/raw/`) **включать** в политику копирования отдельным шагом (cron: tar/rsync) — **не** полагаться только на «полный» tarball проекта, если в `.gitignore` лежат большие файлы.


**Дополнительный слой защиты (с 2026-04-27):** safety snapshots в `/root/projects/TimeWoven_snapshots/` — отличаются от `backups/daily` тем, что фиксируют **состояние перед каждым заданием** (включая untracked), а не периодически по cron. Не заменяют ежедневные backup'ы, дополняют их.


**Ответственность:** периодически проверять **восстановление** из `backups/daily` (хотя бы `gunzip -t` + тестовый restore на staging). Скрипт и расписание (cron) — у владельца инфраструктуры; при смене путей — обновлять `UPLOAD_DIRS` в `backup_manager.sh`.


**Публичный base URL для ссылок (family):** в `.env` рекомендуется **`TW_PUBLIC_BASE_URL=https://app.timewoven.ru`**, чтобы админ-шаблоны и письма не зависели от `request.base_url` за reverse proxy; опционально `TW_DEFAULT_PUBLIC_BASE_URL` в коде как fallback.


---


## 6. Текущее состояние приложения (на 2026-04-27)


### 6.1 Рабочие части


- Лендинг: `https://timewoven.ru/` — статический HTML (RU), `https://timewoven.ru/en/` — EN-версия.
- App:
  - Главная (`/`) — «Импульс дня» с аватаром, цитатой, плеером и ссылкой на автора.
  - `/family/welcome` — приветственная страница family-флоу.
  - `/family/p/{public_uuid}` и `/family/access/{public_uuid}` — публичные карточки и форма входа по TOTP/backup-коду.
  - `/family/person/{id}` — карточка человека (legacy URL, 301 → `/family/p/{public_uuid}`).
  - `/family/tree?...` — граф семьи с кликабельными нодами (D3).
  - `/family/timeline` — таймлайн на view-слое `TimelineEventView`.
  - `/family/reply/{id}` — ответы семьи на воспоминания, сохранение в `Quotes`.
  - `/family/memory/new` — POST для создания нового воспоминания (с проверкой регистрации в startup).
  - `/family/memory/{id}/edit` — редактирование воспоминания.
  - `/admin/` — главная админки (требует login).
  - `/admin/login` (GET/POST) — форма входа.
  - `/admin/people`, `/admin/people/{id}/edit`, `/admin/people/{id}/aliases`, `/admin/people/{id}/access` — управление персонами.
  - `/admin/transcriptions`, `/admin/avatars`, `/admin/early-access` — управление контентом и заявками.
  - `/admin/ai-local-llm-check`, `/admin/whisper-local-test`, `/admin/memory-pipeline-test` — диагностические страницы локальных AI-сервисов.
  - `/explorer/` — TW Explorer.
  - `/health` — JSON `{"status": "ok"}`.


### 6.2 Недавние правки (27.04.2026)


- Установлен операционный протокол `docs/PROJECT_OPS_PROTOCOL.md` + `scripts/ops/`.
- Шесть атомарных коммитов разобрали остаточный WIP инцидента 2026-04-26 (см. `PROJECT_LOG.md` — запись 27 апреля).
- Сервис перезапущен на новом коде, `/health` отдаёт `ok` локально и публично.
- Создан защищённый snapshot `protected/CLEAN-START-2026-04-27`.
- Три stash от 26.04 архивированы и удалены.


### 6.3 Известные ограничения


- `app/core/theme.py` утрачен в инциденте 2026-04-26; временно заменён на статическое `current_dark`. Восстановление — `T-CORE-THEME-RESTORE`.
- `app/services/person_alias_service.py` живёт как минимальный shim; полная функциональность — `T-FAMILY-ACCESS-REBUILD`.
- Один из старых ответов Дмитрия сохранён в неверной кодировке (кракозябры); новые записи после фикса client_encoding → UTF‑8 должны сохраняться корректно, старые требуют ручной правки. [cite:33]
- `POST /profile/avatar` ещё не реализован.
- Админ-авторизация включена через `app/security.py::require_admin()` (cookie `tw_admin_session`). Дополнительно: rate limit на `POST /admin/login`, audit log попыток входа, idle timeout (см. раздел «Безопасность админки»).
- Таймлайн выводит только те события (рождения, смерти, свадьбы), которые реально присутствуют в БД.
- `/family/memory/new` при GET-запросе без person_id и family-сессии возвращает 422 (валидация pydantic) — поведение корректное, но UX-минор `T-FAMILY-MEMORY-NEW-RETURN-303-INSTEAD-OF-422` зафиксирован в backlog.


---


## 7. Управление зависимостями


### 7.1 Файлы


- `requirements.txt` — ручной, осмысленный список зависимостей с комментариями и группировкой. [cite:27]
- `requirements.lock.txt` — полный снимок окружения (`pip freeze`), используется при воспроизведении среды.


### 7.2 Протокол обновления


1. Установить / обновить пакеты в виртуальном окружении:
   ```bash
   pip install ...
   ```
2. Обновить lock-файл:
   ```bash
   pip freeze > requirements.lock.txt
   ```
3. Вручную синхронизировать `requirements.txt` (добавить новые пакеты в соответствующие блоки, обновить версии и комментарии). [cite:27]
4. Закоммитить оба файла.


---


## 8. Документация и ADR


- `TECH_PASSPORT.md` — этот документ, техническая карта проекта.
- `docs/PROJECT_OPS_PROTOCOL.md` — операционный протокол, описывает **как** мы безопасно меняем систему (с 2026-04-27).
- `PROJECT_LOG.md` — операционный журнал, включая post-mortem инцидента 2026-04-26.
- `PRODUCT_BACKLOG.md` — реестр задач и решений.
- `DB_CHANGELOG.md` — журнал изменений схемы и данных БД (temporal‑нормализация и др.).
- `tech-docs/adr/` — ADR (архитектурные решения), включая миграцию SQLite → PostgreSQL и temporal‑модель. [cite:32][cite:35]


---


## 9. Roadmap (high-level)


| Приоритет | Задача | Описание |
|-----------|--------|----------|
| — | Реальная авторизация в админке | ✅ Реализовано: `tw_admin_session` + `require_admin()`; hardening: rate limit, audit log, idle timeout (T-ADMIN-HARDENING-2026-04-27) |
| P0 | Завершить temporal normalization v2 | Связать Unions и брачные связи в PersonRelationship |
| P0 | Исправить старые UTF‑8 артефакты | Очистить/исправить битые записи в БД |
| P0 | T-FAMILY-ACCESS-REBUILD | Полное восстановление person_alias_service слоя (сейчас shim) |
| P0 | T-CORE-THEME-RESTORE | Восстановить утраченный `app/core/theme.py` (`get_active_theme_preset`) |
| P1 | Реализовать avatar upload | Завершить `/admin/avatars` + `POST /profile/avatar` |
| P1 | T42 — meaning/events layer | Перевести `/family/timeline` на event-centric модель (см. PRODUCT_BACKLOG) |
| P1 | T43 — family reply as collective memory entry | Эволюция `/family/reply/{id}` |
| P1 | Telegram Bot и Whisper | «Импульс дня» и интеграция транскрибации |
| P2 | Улучшение графа и UI | Масштабирование графа, полировка UI, брендирование |
| P2 | T-DUPLICATE-FAMILY-TREE-ROUTE-INVESTIGATE | Расследовать дубль маршрута `/family/tree` в `tree.py` и `family_tree.py` |
