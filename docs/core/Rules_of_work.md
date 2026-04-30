🧭 TimeWoven — Rules of Work v2 (CTO Edition)

State: 2026-04-29 | Post-Architecture Stabilization

0. Архитектурная модель системы
MacBook        = Development Factory
GitHub         = Source of Truth (Control Tower)
Production     = Runtime Only
PostgreSQL     = Dual-mode (local + prod)
Cursor         = Primary IDE + SSH ops tool
1. Основной принцип
Никакие изменения не делаются напрямую в production.
Все изменения проходят через feature → develop → main flow.
2. Ежедневный цикл работы
Утро (старт дня)
cd ~/projects/TimeWoven
source .venv/bin/activate
git checkout develop
git pull origin develop
make health

Выбор задачи:

только 1 active feature
Feature development
git checkout -b feature/T-NEW-TASK

Работа:

код
тесты
docs
локальный запуск
Локальная проверка
make dev
make test
make health
Commit rule
git add .
git commit -m "T-XXX: short description"
git push -u origin feature/T-XXX
3. Merge flow (development)
feature/* → develop (via PR)

Перед merge:

локально протестировано
нет breaking changes
нет незавершённых миграций
4. Release flow (production)
develop → main → production
Release steps:
git checkout develop
git pull origin develop
make health
PR: develop → main
merge approved
server:
git checkout main
git pull origin main
systemctl restart timewoven
curl /health
5. Forbidden actions (STRICT)
❌ commits directly to main
❌ development on production server
❌ bypassing feature branches
❌ manual DB edits on production
❌ force push to shared branches
❌ running migrations without review
6. Cursor usage model

Allowed:

✔ logs inspection
✔ config review
✔ SSH read-only audit
✔ controlled deployment scripts

Not allowed:

✖ feature development directly on server
✖ unsynchronized production edits
7. Database model
timewoven_core        = system registry (families, metadata)
timewoven_<family>    = isolated domain data per family

Rules:

no schema changes without explicit migration
no manual production DB edits
schema changes always go through develop
8. Environment system
Mac:
  .env → active dev config

Git:
  .env.example → template only

Server:
  .env → production secrets (NOT in git)
9. Make-based workflow
make dev      → start local server
make stop     → stop server
make health   → check API
make test     → run tests
10. Release checklist

Before production release:

✔ develop tested locally
✔ no pending migrations
✔ no failing tests
✔ health check OK
✔ feature merged

After release:

✔ server updated
✔ restart completed
✔ /health = OK
✔ PROJECT_LOG updated
11. System mindset
MacBook is the only place where code is born.
GitHub is the system of truth.
Production only executes validated state.
🏁 Result of this version

Теперь у тебя:

единый рабочий стандарт
предсказуемые релизы
безопасный production
чистая dev среда
масштабируемая архитектура

---

All schema changes MUST go through Alembic after 2026-04-29
No direct SQL schema edits in production

## Engineering Rules (effective 2026-04-29)

### Development Model

* MacBook is the primary development environment.
* Production server is runtime environment only.
* Feature development must happen locally first.

### Git Flow

* feature/* branches are for active work.
* develop is integration branch.
* main is release branch.

### CI Discipline

* Pull requests require green CI before merge.
* Direct risky changes to protected branches are discouraged.

### Database Discipline

* All schema changes must go through Alembic migrations.
* No direct schema edits in production.
* Manual SQL hotfixes only in emergency with written log entry.

### Observability Discipline

* Errors must be diagnosable through logs.
* Health endpoint must remain operational.
* New critical flows should emit audit events.

---
## Ежедневный цикл работы (идеальный)

### Утро
- `git checkout develop`
- `git pull origin develop`
- `git checkout -b feature/T-NEW-TASK`

### Работа в Cursor
- код
- тесты
- docs
- локальная проверка

### Коммит
- `git add .`
- `git commit -m "T-NEW-TASK: short summary"`
- `git push -u origin feature/T-NEW-TASK`

### Merge / Release
- PR: `feature/T-NEW-TASK` → `develop`
- PR: `develop` → `main`
- После merge: deploy на production

### Cursor на сервере (SSH)
Можно:
- читать логи
- inspect configs
- read-only audit
- deploy scripts
- emergency fixes по ТЗ

Нельзя как норма:
- жить кодом на сервере
- писать фичи в prod repo
- менять ветки хаотично

### Настройка веток (очень рекомендую)
Держать локально всегда:
- `main`
- `develop`
- `feature/*`

Naming standard:
- `feature/T-VOICE-UPLOAD`
- `feature/T-PERSON-PAGE`
- `feature/T-TIMELINE-PERF`
- `hotfix/T-LOGIN-FIX`

### Идеальный deploy flow
MacBook tested → merge develop → release to main → server `git pull main` → restart (если нужно) → health check

---
### Architecture
MacBook = Factory  
GitHub = Control Tower  
Production Server = Runtime

---
## TimeWoven SOLO FOUNDER OPERATING SYSTEM v1 (кратко)
Каждый день:

Утро (5 минут):
- git status
- git pull develop
- выбрать 1 главную задачу
- открыть Cursor

День:
- работа только в feature branch

Вечер:
- commit / push / note in PROJECT_LOG

Что запрещено себе теперь:
- ❌ “быстро поправлю на сервере”
- ❌ “сделаю прямо в develop без ветки”
- ❌ “потом разберусь с git”
