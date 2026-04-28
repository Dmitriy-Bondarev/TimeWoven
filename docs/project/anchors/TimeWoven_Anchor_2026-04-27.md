# TimeWoven Anchor — 2026-04-27

**TimeWoven** — цифровая экосистема семейного наследия: воспоминания, привязанные к людям и событиям семейного дерева, плюс контуры Max-бота, AI-анализа и администрирования. Семейные страницы используют **публичные UUID** и **TOTP-доступ** без утечки внутренних `person_id` в публичных ссылках.

Этот Anchor — **срез состояния на 27.04.2026** после восстановления от инцидента 26.04 и введения операционного протокола. Подробности по полям — в [TECH_PASSPORT.md](TECH_PASSPORT.md), [DB_CHANGELOG.md](DB_CHANGELOG.md), [docs/PROJECT_OPS_PROTOCOL.md](docs/PROJECT_OPS_PROTOCOL.md), [tech-docs/](tech-docs/).

Предыдущий срез: [TimeWoven_Anchor_2026-04-25.md](TimeWoven_Anchor_2026-04-25.md).

---

## Главное за период 25.04 → 27.04

**26 апреля** при работе по задаче P1.20 (admin login hardening) часть исходников family access слоя была физически утрачена — они существовали только как untracked-файлы и были потеряны при операциях с git stash. Прод поднят в тот же день emergency hotfix-ом с временным отключением части функционала.

**27 апреля** введён **операционный протокол** ([docs/PROJECT_OPS_PROTOCOL.md](docs/PROJECT_OPS_PROTOCOL.md) v1.0), весь оставшийся WIP инцидента разобран по новому протоколу в **9 атомарных коммитов без единого отклонения от scope**, создана первая в истории проекта **защищённая точка чистого старта**.

Полная хронология и Learning Log — в [PROJECT_LOG.md](PROJECT_LOG.md), раздел `## INCIDENT 2026-04-26`.

---

## 1. Операционный протокол (новое с 27.04)

С 2026-04-27 в проекте действует формальный протокол, обязательный для всех изменений. Он состоит из четырёх уровней защиты:

1. **Clean State Gate** — `bash scripts/ops/clean_state_gate.sh` обязателен перед каждым новым заданием. 6 проверок: `git status` пустой, `git stash` пустой, валидное имя ветки, синхронизация с origin, `timewoven.service` active, `/health` отдаёт 200.
2. **Safety Snapshot** — `bash scripts/ops/safety_snapshot.sh <TASK_ID>` создаёт полный архив рабочего дерева, включая **untracked-файлы** (это ключевое отличие от `git stash`, потеря которого вызвала инцидент 26.04). Поддерживает rolling-30-дней и `--protected` режим без TTL. Опционально дампит БД (флаг `--with-db` обратно при rollback).
3. **Один блок — один коммит — untracked = 0** — каждое задание заканчивается чистым `git status` и одним подписанным коммитом `T-XXX: ...`.
4. **DEVIATION-RULE контракта ТЗ** — implementation-агент обязан остановиться при любой невозможности выполнить задание точно как описано, и вернуть `BLOCKED:` отчёт. Никаких автономных подмен scope.

**Откат** при необходимости: `bash scripts/ops/rollback_to_snapshot.sh <TASK_ID>` — восстанавливает worktree (опционально git и БД), при этом сначала делает свой собственный pre-rollback snapshot.

**Каталог снапшотов:** `/root/projects/TimeWoven_snapshots/` (mode 700, вне репозитория).

**Защищённые точки:**
- `protected/CLEAN-START-2026-04-27/` — первая в истории проекта точка чистого старта (52M: worktree.tar.gz 28M + repo.bundle 24M + meta.txt). Полное восстановление одной командой.
- `protected/STASH-REFERENCE-2026-04-26/` — архив трёх stash дня инцидента (.diff + .stat для каждого), сохранён как референс для будущих задач восстановления.

---

## 2. Архитектура сейчас

**Веб-приложение**
- **FastAPI** + **Uvicorn** на `127.0.0.1:8000`, внешний трафик через **Nginx** → HTTPS `app.timewoven.ru`.
- **systemd:** `timewoven.service` — основной entrypoint `app.main:app`. `app/main.py` через `_ensure_jinja_i18n_globals()` регистрирует i18n-фильтры на всех `Jinja2Templates`-окружениях (tree, admin, timeline, TW_Explorer) при старте + `_assert_family_memory_new_route` startup-проверка.
- **Шаблоны:** Jinja2; семейные и админ-маршруты в `app/api/routes/tree.py`, `app/api/routes/admin.py`, и др.

**i18n core (M4.5, 2026-04-26)**
- Минимальный YAML-based i18n: `app/core/i18n.py` (`install_jinja_i18n`, фильтры `t` и `ts`, `detect_language`, `set_context_lang` и др.).
- Источник переводов: `locales/{ru,en}/{app,family,landing}.yml`.
- Используется в `app/main.py`, `app/api/routes/admin.py`, `app/api/routes/tree.py` и шаблонах family/admin/landing.

**Локальные AI на том же VPS** (без обязательной отправки сырого аудио/текста наружу — без изменений с 25.04)
- **`timewoven-llm.service`** — Docker Compose `ops/local_llm/`, HTTP `127.0.0.1:9000`. LLM (GGUF) внутри контейнера.
- **`timewoven-whisper.service`** — Docker Compose `ops/whisper_small/`, HTTP `127.0.0.1:9100` (faster-whisper small, CPU).

**Лендинг**
- `https://timewoven.ru/` (RU) и `https://timewoven.ru/en/` (EN). Сборка через `scripts/build_landing.py`. С 26.04 `deploy_landing.sh` опционально публикует EN-версию.

---

## 3. Состояние family access слоя (после восстановления)

| Модуль | Состояние |
|---|---|
| `app/core/i18n.py` | **Восстановлен полностью**, в git с 27.04 (коммит `6d4b668`). |
| `app/services/timeline_event_view.py` | **Новый view-слой T42** (без БД, без миграций), в git с 27.04 (коммит `d15d4aa`). |
| `app/services/person_alias_service.py` | **SHIM-модуль** (восстановлен из `.pyc`): экспортирует `ALIAS_TYPES` и `ALIAS_STATUS`. Полная функциональность — задача `T-FAMILY-ACCESS-REBUILD` (P0) в backlog. |
| `app/core/theme.py` | **Утрачен** в инциденте 26.04. Временно заменён на статическое `request.state.active_theme = "current_dark"` в `app/main.py`. Восстановление — задача `T-CORE-THEME-RESTORE` (P0). |
| `locales/{ru,en}/{app,family,landing}.yml` | **Все 6 файлов в git** с 27.04 (коммит `6d4b668`). |
| Admin templates (login, dashboard, people, transcriptions, person_edit, person_access, и т.д.) | **На месте, рабочие**, прод проверен ручным проходом. Часть восстановлена в коммите `e54fad1`. |

**Маршруты family access** (без изменений с 25.04, проверены ручным проходом 27.04):
- `/family/p/{public_uuid}` — публичная карточка по UUID;
- `/family/access/{public_uuid}` — TOTP/backup-код вход;
- `/family/welcome`, `/family/timeline`, `/family/person/{id}` (legacy 301 → `/family/p/{uuid}`), `/family/reply/{memory_id}`, `/family/memory/new`, `/family/memory/{id}/edit`;
- guard `_require_family_zone` в `tree.py` редиректит на форму доступа при отсутствии валидной family-сессии.

**TOTP/безопасность** (без изменений с 25.04): 6-значные коды, `valid_window=1`, rate limit 20/15min на пару (IP, public_uuid), Fernet-шифрование секрета, cookie `tw_family_access` HttpOnly/SameSite=Lax/Secure.

---

## 4. БД и миграции

**Без изменений в схеме за период 25.04 → 27.04.** Последняя описанная миграция — `migrations/009_extend_person_aliases_v2.sql` (см. Anchor 25.04).

**Backups**
- `scripts/backup_manager.sh` (cron, 03:00 UTC) — `postgres_dump_<UTC>.sql.gz`, `project_<UTC>.tar.gz`, `uploads_<UTC>.tar.gz` в `backups/daily/`. Ротация ~60 дней + воскресные копии в `backups/daily/archive/`.
- **Дополнительный слой защиты с 27.04:** safety snapshots в `/root/projects/TimeWoven_snapshots/` — фиксируют состояние **перед каждым заданием** (включая untracked), не заменяют ежедневные backups, а дополняют их.

---

## 5. История 9 коммитов 27 апреля
df7c51d T-CHANGELOG-UPDATE-2026-04-27 CHANGELOG v1.22.38 (consolidated 25-27.04)
a45adc6 T-DOCS-RECONCILIATION-2026-04-27 TECH_PASSPORT, BACKLOG, OPS_PROTOCOL §10.4, -WORKFLOW_ROLES
9aed37f T-PROJECT-LOG-RESTORE-2026-04-27 INCIDENT 2026-04-26 post-mortem in PROJECT_LOG
98696bc T-LANDING-EN-DEPLOY-2026-04-26 deploy_landing.sh EN support
e54fad1 T-ADMIN-RESTORE-AND-PAGES-2026-04-26 atomic admin layer restoration (14 files)
74e9d93 T-FAMILY-PROFILE-COPY-2026-04-26 family/profile + welcome copy pass
d15d4aa T-TIMELINE-EVENTS-VIEW-2026-04-26 TimelineEventView + tree.py + timeline.py
6d4b668 T-RECOVERY-FAMILY-ACCESS-SHIM-2026-04-26 i18n core + person_alias shim + locales
35e01ec T-OPS-PROTOCOL-INSTALL-2026-04-27 protocol + 3 ops scripts + README
bb66718 (предыдущая ветка) fix(family-profile): hero dates, hide maiden

Все 9 коммитов выполнены по новому протоколу: SCOPE-LOCK, явные `git add` пути (без `-A`/`-u`/`.`), DEVIATION-RULE при любом отклонении, обязательный self-check после каждого. Implementation-агент дважды корректно остановился по DEVIATION-RULE (обрезанное commit-сообщение, конфликт `.git/index.lock` с git-extension Cursor IDE) — это и есть подтверждение, что новые правила работают.

---

## 6. Что в backlog как P0 (требуют восстановления)

| Задача | Что нужно |
|---|---|
| **T-FAMILY-ACCESS-REBUILD** (P0) | Полное восстановление person_alias_service слоя поверх текущего shim. Источники: `migrations/007_add_person_aliases.sql`, шаблон `adminpersonaliases.html`, импорты в `admin.py`, архив `protected/STASH-REFERENCE-2026-04-26/stash_2_wip-before-p1-20.diff`. |
| **T-CORE-THEME-RESTORE** (P0) | Восстановить `app/core/theme.py` с `get_active_theme_preset(db)`. Источник: архив `stash_1_emergency-prod-breakage.diff` содержит точный код, который был отключён. |

См. полный список в [PRODUCT_BACKLOG.md](PRODUCT_BACKLOG.md) (Сводка задач 2026-04-27).

---

## 7. Инфраструктура сервера (срез 27.04)

**Ресурсы** (без изменений с 25.04):
- **RAM:** ~11 Gi total
- **CPU:** 6 vCPU
- **Диск (root):** ~157 Gi total, ~130 Gi свободно

**Сервисы:** все три active (timewoven, timewoven-llm, timewoven-whisper). После restart 27.04 06:59 UTC основной сервис работает на новом коде с PID 387738.

**Назначение:** VPS рассчитан на хранение семейного аудио, ежедневные дампы БД, snapshot-каталог (`TimeWoven_snapshots/`) и локальные Whisper/LLM в Docker — без обязательной зависимости от внешних API.

---

## 8. План следующих шагов

| Код | Что |
|---|---|
| **T-FAMILY-ACCESS-REBUILD** (P0) | Полное восстановление сервиса алиасов (заменить shim). |
| **T-CORE-THEME-RESTORE** (P0) | Восстановить модуль выбора темы оформления. |
| **T42** (P1) | Перевести `/family/timeline` на event-centric модель (текущий промежуточный шаг — view-слой `timeline_event_view.py`). |
| **T43** (P1) | Family reply как точка входа в коллективную память (event context, типы ответа, AI-помощь). |
| **T-DUPLICATE-FAMILY-TREE-ROUTE-INVESTIGATE** (P2) | Расследовать дубль маршрута `/family/tree` в `tree.py` и `family_tree.py`. |
| Минор задачи (P3) | T-OPS-INDEX-LOG-FORMAT, T-PROTOCOL-IDE-COEXISTENCE, T-FAMILY-MEMORY-NEW-RETURN-303-INSTEAD-OF-422. |
| **I18N-2/3** | Русификация лендинга для соответствия ФЗ-53/ФЗ-168, локализация основных экранов на ru/en (продолжение M4.5). |

---

## 9. Где копать детали

| Тема | Где |
|---|---|
| Паспорт, стек, деплой, процесс | [TECH_PASSPORT.md](TECH_PASSPORT.md) |
| **Операционный протокол (как мы работаем)** | [docs/PROJECT_OPS_PROTOCOL.md](docs/PROJECT_OPS_PROTOCOL.md) |
| Журнал решений и инцидентов, post-mortem 26.04 | [PROJECT_LOG.md](PROJECT_LOG.md) |
| Реестр задач и приоритетов | [PRODUCT_BACKLOG.md](PRODUCT_BACKLOG.md) |
| История релизов и фич | [CHANGELOG.md](CHANGELOG.md) |
| Схема БД | [tech-docs/DATABASE_SCHEMA.md](tech-docs/DATABASE_SCHEMA.md) |
| Журнал миграций | [DB_CHANGELOG.md](DB_CHANGELOG.md) |
| Предыдущие срезы | [TimeWoven_Anchor_2026-04-25.md](TimeWoven_Anchor_2026-04-25.md), [TimeWoven_Anchor_2026-04-23.md](TimeWoven_Anchor_2026-04-23.md) |
| Архив stash дня инцидента (референс) | `/root/projects/TimeWoven_snapshots/protected/STASH-REFERENCE-2026-04-26/` |
| Защищённая точка чистого старта | `/root/projects/TimeWoven_snapshots/protected/CLEAN-START-2026-04-27/` |
