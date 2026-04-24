# 📸 Технический паспорт проекта: TimeWoven (v1.3-postgres)

> **Дата обновления:** 2026-04-25  
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
| Документация        | `tech-docs/` + материалы на Mac                        |
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

Runtime‑окружения (dev/prod) используют PostgreSQL через `DATABASE_URL` в `.env`. SQLite не используется в коде, а старые дампы лежат в `data/`. [cite:19][cite:21]

### 2.2 Инфраструктура

| Компонент          | Технология        | Назначение                                     |
|--------------------|-------------------|-----------------------------------------------|
| Веб-сервер         | Nginx             | Reverse proxy, статика лендинга, SSL termination |
| ASGI-сервер        | Uvicorn           | Запуск FastAPI-приложения                     |
| SSL/TLS            | Certbot / Let’s Encrypt | Сертификаты для всех доменов             |
| Процесс-менеджер   | systemd           | Автозапуск и мониторинг `timewoven.service`   |
| CI/CD              | GitHub + manual deploy | `git pull` + перезапуск сервиса            |

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

### 3.2 Фактическая структура каталогов

```text
/root/projects/TimeWoven/
├── app/
│   ├── main.py
│   ├── security.py
│   ├── api/
│   │   ├── timeline.py
│   │   └── routes/
│   │       ├── admin.py
│   │       ├── family_tree.py
│   │       └── tree.py
│   ├── core/
│   │   └── security.py
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
│   │   ├── family_graph.py
│   │   └── timeline_service.py
│   └── web/
│       ├── index.html
│       ├── templates/
│       │   ├── base.html
│       │   ├── family_tree.html
│       │   ├── family_tree_list.html
│       │   ├── admin/
│       │   │   ├── admin_login.html
│       │   │   ├── admin_people.html
│       │   │   ├── admin_transcriptions.html
│       │   │   └── avatars_form.html
│       │   ├── family/
│       │   │   ├── home.html
│       │   │   ├── person_card.html
│       │   │   ├── pin_form.html
│       │   │   ├── profile.html
│       │   │   ├── reply.html
│       │   │   ├── reply_sent.html
│       │   │   ├── timeline.html
│       │   │   └── who_am_i.html
│       │   └── site/
│       │       └── landing.html
│       └── static/
│           ├── audio/
│           │   ├── processed/
│           │   └── uploads/
│           ├── images/
│           │   ├── avatars/
│           │   └── brand/
│           ├── js/
│           │   └── family_graph.js
│           ├── site/
│           │   ├── site.css
│           │   └── site.css.bak_2026-04-15_v2
│           ├── favicon.png
│           ├── favicon-32.png
│           ├── logo.png
│           ├── logo-32.png
│           ├── logo-64.png
│           └── logo-128.png
├── archive/
│   ├── main.py.bak_2026-04-15
│   ├── main.py.bak_all_templates_2026-04-15
│   ├── main.py.bak_site_preview_2026-04-15
│   └── main_backup.py
├── backups/
│   └── 2026-04-17/
├── data/
│   ├── backups/
│   └── raw/
├── docs/
│   ├── CNAME
│   ├── index.html
│   └── logo.png
├── migrations/
│   └── 001_create_union_tables.sql
├── scripts/
│   └── watcher.py
├── tech-docs/
│   ├── README.md
│   └── adr/
├── temp/
│   ├── .gitkeep
│   ├── README.md
│   └── project_docs/
├── .env
├── .gitignore
├── CHANGELOG.md
├── DB_CHANGELOG.md
├── FAMILY_GRAPH_ANALYSIS.md
├── README.md
├── TECH_PASSPORT.md
├── create_postgres_schema.sql
├── db_schema_before.sql
├── db_tables_before.txt
├── deploy.sh
├── deploy_landing.sh
├── processor.py
├── requirements.txt
└── venv/…
```

### 3.3 Модульная архитектура (по коду)

| Модуль              | Файл(ы)                    | Ответственность                                  |
|---------------------|----------------------------|--------------------------------------------------|
| App entrypoint      | `app/main.py`              | Инициализация FastAPI, загрузка `.env`, подключение роутов и templates |
| Security (core)     | `app/core/security.py`     | Низкоуровневая безопасность (защита, утилиты)    |
| Security (app)      | `app/security.py`          | Высокоуровневая логика безопасности (require_admin и др.) |
| DB base             | `app/db/base.py`           | Базовые настройки SQLAlchemy                     |
| DB session          | `app/db/session.py`        | `SessionLocal` и engine                          |
| Models              | `app/models/__init__.py`, `event.py` | SQLAlchemy-модели (агрегированы в `__init__.py`) |
| Schemas             | `app/schemas/family_graph.py` | Pydantic-схемы для семейного графа           |
| Timeline API        | `app/api/timeline.py`      | Логика таймлайна на уровне API                  |
| Routes (family/admin)| `app/api/routes/tree.py`, `admin.py` | Маршрутизация для семьи и админки          |
| Legacy routes       | `app/api/routes/family_tree.py` | Исторический роутер дерева (подключение убрано) |
| Services            | `app/services/family_graph.py`, `timeline_service.py` | Сервисы графа и таймлайна              |
| Web templates       | `app/web/templates/...`    | Все HTML‑шаблоны (family, admin, site)          |
| Static              | `app/web/static/...`       | JS, CSS, логотипы, аватары, аудио               |
| Family + TOTP       | `app/api/routes/tree.py`, `app/services/family_access_service.py` | Публичные URL `/family/p/{public_uuid}`, `/family/access/...`, сессия `tw_family_access` |

### 3.4 Организация документации

Проект использует трёхуровневую иерархию документации:

#### **docs/** — Публичная документация и GitHub Pages

Минимальный набор файлов для интеграции с GitHub Pages и лендингом:

- **`CNAME`** — конфиг доменов для GitHub Pages (содержит `timewoven.ru`).
- **`logo.png`** — логотип проекта, используется лендингом.
- *(Остальные файлы игнорируются или перемещаются в `tech-docs/`)*

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
- **`family-graph-snapshot-timeline-notes.md`** — исследовательские заметки и анализ по граву и таймлайну (часть итератива).

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

- **`TimeWoven_Anchor_2026-04-25.md`** — срез «как сейчас» (family access, локальные AI, миграции, бэкапы, I18N-май); ранее: `TimeWoven_Anchor_2026-04-23.md`.
- **`PROJECT_LOG.md`** — операционный журнал всех значимых обновлений и решений; читается вверх по времени (новые записи сверху).
- **`TECH_PASSPORT.md`** — этот файл, общий технический паспорт.
- **`PRODUCT_BACKLOG.md`** — живой реестр задач (P-задачи, T-задачи) с статусами и решениями.
- **`CHANGELOG.md`** — История релизов и фич (для конечных пользователей).
- **`DB_CHANGELOG.md`** — История изменений схемы БД и миграций.
- **`FAMILY_GRAPH_ANALYSIS.md`** — расширенный анализ семейного графа и доменной модели.

---

## 4. Доменная модель (high-level)

### 4.1 Основные сущности (по назначению)

По текущей версии кода сущности агрегированы в `app/models/__init__.py`; по доменной логике используются:

- Person / PersonI18n — люди в семейном графе и их локализованные поля.
- PersonRelationship — связи (родители, дети, браки, и др.).
- Union / UnionChildren — браки/союзы и привязка детей к союзам.
- Memory — воспоминания (аудио, текст, фото).
- Quotes — ответы семьи на воспоминания.
- Event — доменные события (отдельный модуль `event.py`). [cite:24][cite:31]

### 4.2 Граф и таймлайн

- Граф семьи строится в `app/services/family_graph.py` и сериализуется через `app/schemas/family_graph.py`, выводится шаблонами `family_tree.html` / `family_tree_list.html` и `family_graph.js`. [cite:29]
- Таймлайн реализован комбинацией `app/api/timeline.py`, `timeline_service.py` и шаблона `family/timeline.html`. [cite:29]

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

**Админка:** `GET /admin/people/{id}/access` — обеспечение `public_uuid` при первом заходе (`_ensure_public_uuid`), показ **полного** публичного URL (`TW_PUBLIC_BASE_URL` / `request.base_url` / fallback `https://app.timewoven.ru`), копирование в буфер. Подробности — [TimeWoven_Anchor_2026-04-25.md](TimeWoven_Anchor_2026-04-25.md).

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
| Python env          | `/root/projects/TimeWoven/venv` или `.venv` (активное окружение) |
| **RAM (срез 2026-04-25)** | **~11 Gi** total (существенный рост к ранним конфигурациям **~1.8 Gi** в ADR-003) |
| **vCPU**            | **6**                                     |
| **Диск (root)**     | **~157 Gi** total, **~130 Gi** свободно (~14% занято) — запас под аудио, Docker-слой, модели LLM/Whisper, **ежедневные дампы** в `backups/daily` |

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
- `timewoven.ru` и `www.timewoven.ru` обслуживают лендинг из `/var/www/timewoven`.
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

### 5.6 Резервное копирование (срез 2026-04-25)

**База данных**
- Скрипт **`scripts/backup_manager.sh`**: `pg_dump` по `DATABASE_URL` из `.env`, сжатие **gzip** в каталог **`backups/daily/`** с именем `postgres_dump_<UTC>.sql.gz`.
- Параллельно создаётся **снимок кода/проекта** (tar, с исключениями для ненужного объёма) и **архив upload-папок** — `app/web/static/audio/uploads`, `app/web/static/images/uploads` (если каталога нет — пишется маркер, чтобы прогон был прозрачным).
- **Ретация** по mtime (порядка **60 дней**), на **воскресенья (UTC)** копии **дополнительно** складываются в `backups/daily/archive/`.

**Пользовательские медиа и сырьё**
- Критично для восстановления: **аудио-загрузки** (см. пути выше); при появлении единого raw-хранилища (например `app/web/static/audio/raw/`) **включать** в политику копирования отдельным шагом (cron: tar/rsync) — **не** полагаться только на «полный» tarball проекта, если в `.gitignore` лежат большие файлы.

**Ответственность:** периодически проверять **восстановление** из `backups/daily` (хотя бы `gunzip -t` + тестовый restore на staging). Скрипт и расписание (cron) — у владельца инфраструктуры; при смене путей — обновлять `UPLOAD_DIRS` в `backup_manager.sh`.

**Публичный base URL для ссылок (family):** в `.env` рекомендуется **`TW_PUBLIC_BASE_URL=https://app.timewoven.ru`**, чтобы админ-шаблоны и письма не зависели от `request.base_url` за reverse proxy; опционально `TW_DEFAULT_PUBLIC_BASE_URL` в коде как fallback.

---

## 6. Текущее состояние приложения (на 2026-04-19)

### 6.1 Рабочие части

По итогам дня 19.04.2026: [cite:29]

- Лендинг: `https://timewoven.ru/` — статический HTML, favicon/логотипы.  
- App:
  - Главная (`/`) — «Импульс дня» с аватаром, цитатой, плеером и ссылкой на автора.
  - `/family/person/{id}` — карточка человека, шаблон `family/profile.html`.
  - `/family/tree?...` — граф семьи с кликабельными нодами (D3).  
  - `/family/timeline` — таймлайн с воспоминаниями (и событиями по мере наполнения БД).
  - `/who-am-i` + `/who-am-i/pin` — выбор пользователя и PIN‑flow.
  - `/family/reply/{id}` — ответы семьи на воспоминания, сохранение в `Quotes`.
  - `/admin/transcriptions` — список транскрипций.
  - `/admin/people` — список людей.
  - `/admin/login` — форма входа (упрощённый flow).
  - `/admin/avatars` — форма загрузки аватаров.
  - `/health` — JSON `{"status": "ok"}`.

### 6.2 Недавние правки (19.04.2026)

Ключевые изменения, которые должны быть отражены в коде и документации: [cite:29]

- Загрузка `.env` перенесена в `app/main.py` до импорта роутеров.
- Root route `/` переведён с JSON‑заглушки на `TemplateResponse("family/home.html", ...)` с реальными данными из PostgreSQL.
- Убран дублирующий роутер `family_tree.py` из подключения в main (файл остался в проекте как legacy).
- Исправлен who‑am‑i flow (единый `person_id` по всему UI).
- Исправлен `Quote.id` (`autoincrement=True`) — устранён `IntegrityError`.
- Добавлен `POST /admin/login`, исправлен путь `/admin/people`.
- Исправлен импорт `HTMLResponse` в `admin.py`.
- В `family_graph` добавлен `person_id` и `url`, граф стал кликабельным.

### 6.3 Известные ограничения

- Один из старых ответов Дмитрия сохранён в неверной кодировке (кракозябры); новые записи после фикса client_encoding → UTF‑8 должны сохраняться корректно, старые требуют ручной правки. [cite:33]
- `POST /profile/avatar` ещё не реализован.
- Admin‑login пока не даёт реальной авторизации; `require_admin()` временно пропускает всех.
- Таймлайн выводит только те события (рождения, смерти, свадьбы), которые реально присутствуют в БД.

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
- `DB_CHANGELOG.md` — журнал изменений схемы и данных БД (temporal‑нормализация и др.).  
- `tech-docs/adr/` — ADR (архитектурные решения), включая миграцию SQLite → PostgreSQL и temporal‑модель. [cite:32][cite:35]

---

## 9. Roadmap (high-level)

| Приоритет | Задача | Описание |
|-----------|--------|----------|
| P0 | Реальная авторизация в админке | Убрать временное `require_admin()` и /admin/login без auth |
| P0 | Завершить temporal normalization v2 | Связать Unions и брачные связи в PersonRelationship |
| P0 | Исправить старые UTF‑8 артефакты | Очистить/исправить битые записи в БД |
| P1 | Реализовать avatar upload | Завершить `/admin/avatars` + `POST /profile/avatar` |
| P1 | Telegram Bot и Whisper | «Импульс дня» и транскрибация аудио |
| P2 | Улучшение графа и UI | Масштабирование графа, полировка UI, брендирование |
