# TimeWoven Anchor — 2026-04-25

**TimeWoven** — цифровая экосистема семейного наследия: воспоминания, привязанные к людям и событию семейного дерева, плюс контуры Max-бота, AI-анализа и администрирования. Семейные страницы переведены на **публичные UUID** и **TOTP-доступ** без утечки внутренних `person_id` в публичных ссылках.

Этот Anchor — **срез состояния на 25.04.2026** (стек, БД, family access, локальные AI, инфраструктура, бэкапы). Подробности по полям — в [TECH_PASSPORT.md](TECH_PASSPORT.md), [DB_CHANGELOG.md](DB_CHANGELOG.md) и [tech-docs/](tech-docs/).

---

## Product decision — family graph split: Graph Lite / Time Machine / Legacy Graph (T37)

- Family graph больше не рассматривается как один общий перегруженный интерфейс.
- Принято решение развивать **три отдельные поверхности**:
  1. **Graph Lite**
  2. **Time Machine**
  3. **Legacy Graph**
- **Graph Lite** и **Time Machine** — family-facing.
- **Legacy Graph** — только admin/personal use, experimental / version 1.0.
- `personal timeline` уже считается story-board отдельного человека.
- Поэтому отдельный Story Mode в графе пока не выносится в приоритет.
- Privacy для graph/time views — отдельный будущий эпик.
- Будущая visibility model должна учитывать: запрос на скрытие может исходить от **одного** участника семьи и **не обязан** быть глобальным правилом для всех viewers.

## 1. Архитектура сейчас

**Веб-приложение**
- **FastAPI** + **Uvicorn** на `127.0.0.1:8000`, внешний трафик через **Nginx** → HTTPS `app.timewoven.ru`.
- **systemd:** `timewoven.service` — основной entrypoint `app.main:app`.
- **Шаблоны:** Jinja2; семейные и админ-маршруты в `app/api/routes/tree.py`, `app/api/routes/admin.py` и др.

**Локальные AI на том же VPS (без обязательной отправки сырого аудио/текста наружу)**
- **`timewoven-llm.service`** — Docker Compose в `ops/local_llm/`, публикация **HTTP `127.0.0.1:9000`** (контейнер `timewoven-local-llm`). LLM (GGUF) внутри контейнера, том `./models` с весами; приложение зовёт аналитику по локальному URL (конфиг через `.env`, см. `app/services/ai_analyzer.py` и `ops/local_llm/README.md`).
- **`timewoven-whisper.service`** — Docker Compose в `ops/whisper_small/`, HTTP **`127.0.0.1:9100`** (faster-whisper small, CPU). Описание в `ops/whisper_small/README.md`.

**Взаимодействие с приложением:** FastAPI обращается к LLM/Whisper по **локальному** HTTP; проксирование наружу не требуется для сценария «только VPS». Сырьевые медиа и распознавание не обязаны уходить в публичные API.

---

## 2. БД и миграции (весна 2026)

**Family access (схема + скрипт)**
- Скрипт: `scripts/migrate_family_access.py` (`python -m scripts.migrate_family_access`).
- Таблица **`People`:** `public_uuid` (UUID, backfill, затем **NOT NULL**), `family_access_enabled`, `totp_secret_encrypted`, `totp_enabled_at`, `totp_last_used_at`, `family_access_revoked_at`; уникальный индекс по `public_uuid`.
- Таблицы: **`person_access_backup_codes`** (хеш одноразовых резервных кодов), **`family_access_sessions`** (сессия семьи по непрозрачному токену, `session_token_hash`, `expires_at`, `revoked_at`) + индексы по токену, персоне, сроку истечения.

**Миграция алиасов — `migrations/009_extend_person_aliases_v2.sql`**
- Эволюция `personaliases`: переименование `alias_text` → `label`, `alias_kind` → `alias_type` (после снятия старых CHECK), добавление `spoken_by_person_id`, `source`, `status`, `updated_at` и согласованных ограничений.
- **Зачем:** единая модель алиасов для админки и дальнейших сценариев (лейбл, тип, кто сказал, источник, статус).

**Прочее (коротко):** `008_create_early_access_requests.sql` — early access заявки; нумерованные миграции в `migrations/`.

---

## 3. Family access и безопасность

**Сценарий**
- Семейный профиль вне админки: **`/family/p/{public_uuid}`**; вход без сессии — guard переносит на **`/family/access/{public_uuid}?next=...`**, **не** на старый who-am-i/ PIN для публичных URL.
- **TOTP:** настройка в админке (QR, подтверждение кода), **6-значные** коды из приложения-аутентификатора, **одноразовые backup-коды**, **rate limit** (в коде: до **20** попыток в **15 минут** на пару **IP + public_uuid**; проверка TOTP с `valid_window=1` в **pyotp**).
- **Cookie `tw_family_access`:** HttpOnly, SameSite=Lax, Secure при HTTPS (см. `app/services/family_access_service.py`).
- **Сессии** в `family_access_sessions`; **сброс** в админке снимает секрет, отзывает сессии, помечает отзыв доступа.
- **Legacy:** `GET /family/person/{id}` → **301** на ` /family/p/{public_uuid}`.

---

## 4. Админ-инструменты family access

- Страница **`/admin/people/{id}/access`**: при открытии вызывается **`_ensure_public_uuid`** (если UUID не был в БД — присваивается и сохраняется), формируется **полный URL** (`https://app.timewoven.ru/.../family/p/{uuid}` с учётом `request.base_url` / `TW_PUBLIC_BASE_URL` / дефолтного хоста), UI с копированием в буфер и модалкой-fallback.
- Операции: **setup TOTP** (регенерация секрета и backup), **подтверждение** первого TOTP, **reset** (секрет + сессии + отзыв), **revoke all sessions**, просмотр количества активных сессий и оставшихся backup-кодов.

---

## 5. Инфраструктура сервера (срез 2026-04-25)

**Ресурсы (факт по текущему хосту проекта)**
- **RAM:** **~11 Gi** total (существенный апгрейд относительно ранних конфигураций **~1.8 Gi**, в которых не помещались тяжёлые ML-нагрузки).
- **CPU:** **6** vCPU.
- **Диск (root):** **~157 Gi**, занято **~21 Gi**, свободно **~130 Gi** (14% use) — запас под аудио, бэкапы, модели и Docker-слой.

**Назначение:** VPS рассчитан на **хранение семейного аудио**, **ежедневные дампы БД**, **локальные** Whisper/LLM в Docker **без** обязательной зависимости от внешних ASR/LLM API по умолчанию.

---

## 6. Бэкапы (стратегия, архитектурно)

**PostgreSQL**  
- Скрипт **`scripts/backup_manager.sh`**: `pg_dump` сжимается в **`backups/daily/postgres_dump_<UTC>.sql.gz`**.  
- Плюс **полный** архив проекта (tar, с исключениями для `.git`, `.venv`, тяжёлого `backups/daily`) — для воспроизводимости кода.  
- Ротация: хранение с ограничением по возрасту (~60 дней), еженедельные копии в подкаталог `archive/`.

**Файлы пользователя (аудио, загрузки)**  
- В тот же сценарий входит отдельный tar по каталогам **`app/web/static/audio/uploads`**, **`app/web/static/images/uploads`** (при отсутствии — создаётся служебный маркер, чтобы прогон был прозрачным).  
- Сырой/экспериментальный каталог `app/web/static/audio/raw/` и прочие пути — по мере внедрения **включать** в бэкап-стратегию отдельно (cron + тот же подход: tar/ rsync), чтобы не рассчитывать только на project tarball.

**Ответственность:** периодически проверять **восстановление** из `backups/daily` и целостность важных артефактов (см. also `data/backups/`, `archive/` в корне — исторические снимки).

---

## 7. План следующих шагов (май 2026)

| Код     | Смысл |
|--------|--------|
| **I18N-1** | Запуск **i18n-каркаса** (единый способ отмечать строки, базовая подстановка locale). |
| **I18N-2** | **Русификация лендинга** и публичных форм в части **ФЗ-53 / ФЗ-168** (юридически значимый текст, согласия, политика). |
| **I18N-3** | **Локализация основных экранов приложения** (семья, таймлайн, who-am-i и др.) на первом приоритете для ru/en. |

---

## 8. Где копать детали

| Тема | Где |
|------|-----|
| Паспорт, стек, деплой | [TECH_PASSPORT.md](TECH_PASSPORT.md) |
| Схема БД | [tech-docs/DATABASE_SCHEMA.md](tech-docs/DATABASE_SCHEMA.md) |
| Журнал миграций | [DB_CHANGELOG.md](DB_CHANGELOG.md) |
| Предыдущий срез | [TimeWoven_Anchor_2026-04-23.md](TimeWoven_Anchor_2026-04-23.md) |
