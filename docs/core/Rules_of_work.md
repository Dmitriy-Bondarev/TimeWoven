🧭 Идеальная operational схема для TimeWoven

Mac dev + GitHub + Production Server + Safe DB migrations + Backups

Для вашего проекта это уже не “сайт”, а семейная цифровая память, значит схема должна быть как у серьёзного SaaS, но без лишней корпоративной тяжести.

🧱 1. Три среды (обязательно)
[DEV]      MacBook
[MAIN]     GitHub
[PROD]     vm-nano server
🟢 DEV (Mac)

Только для разработки.

Содержит:

локальный код
локальный PostgreSQL
тестовые базы:
timewoven_core_dev
timewoven_demo
Cursor
эксперименты
миграции до выката

Никогда:

не работать на проде напрямую
не писать продовые данные сюда
🔵 GitHub

Единый source of truth.

Хранит:

код
docs
ADR
migrations
scripts
CI checks later

Никогда:

secrets
реальные дампы БД
prod пароли
🔴 PROD (vm-nano)

Только:

живое приложение
живая БД
реальные пользователи
backup jobs

Никогда:

разработка
тесты
хаотичные правки руками
🔁 2. Идеальный цикл работы
Каждый новый task:
1. Mac dev
2. Test local DB
3. Commit
4. Push GitHub
5. Pull on server
6. Backup
7. Migration
8. Restart app
9. Smoke test
💾 3. PostgreSQL схема
На Mac:
timewoven_core_dev
timewoven_demo
На PROD:
timewoven_core
timewoven_bondarev
future:
timewoven_petrov
timewoven_sidorov
...
🔐 4. Safe migrations (золотое правило)
Любое изменение БД только так:
migration file in repo
↓
tested locally
↓
backup prod
↓
apply on server
Никогда:
ALTER TABLE ... directly in prod

если это не emergency hotfix.

🧰 5. Backup стратегия (обязательно)
Ежедневно:
PostgreSQL dumps:
timewoven_core
timewoven_bondarev
Хранить:
локально на сервере (7 дней)
отдельно offsite / cloud (30+ дней)
Перед каждым deploy:
pre-deploy snapshot
Перед каждой migration:
schema + data dump
🔥 6. Идеальный deploy script
git pull
python -m alembic upgrade head
systemctl restart timewoven
curl healthcheck

Если ошибка:

restore backup
rollback code
🧪 7. Local dev copy (очень важно)
Сделать anonymized copy production schema

На Mac:

same tables
fake people
fake memories
same structure

Это даст 10x скорость разработки.

🔐 8. Secrets модель
PROD:

.env

Mac:

.env.local

GitHub:

.env.example

---
### Ежедневный цикл работы (идеальный)

Утро
git checkout develop
git pull origin develop
git checkout -b feature/T-NEW-TASK

Дальше открываете в Cursor.
Работа в Cursor
код
тесты
docs
локальная проверка

Коммит
git add .
git commit -m "T-NEW-TASK: short summary"
git push -u origin feature/T-NEW-TASK

Merge

PR:

feature/T-NEW-TASK -> develop
Release (когда готово)

PR:

develop -> main

После merge:

deploy на production.

Что использовать Cursor для сервера

Cursor с SSH отлично подходит для:

Можно:
читать логи
inspect configs
read-only audit
deploy scripts
emergency fixes по ТЗ

Нельзя как норма:
жить кодом на сервере
писать фичи в prod repo
менять ветки хаотично


Настройка веток (очень рекомендую)
В локальном repo иметь всегда:

main
develop
feature/*

Naming standard

feature/T-VOICE-UPLOAD
feature/T-PERSON-PAGE
feature/T-TIMELINE-PERF
hotfix/T-LOGIN-FIX

Идеальный deploy flow

MacBook tested
→ merge develop
→ release to main
→ server git pull main
→ restart if needed
→ health check

---
### Architecture
MacBook = Factory
GitHub = Control Tower
Production Server = Runtime

---

TimeWoven SOLO FOUNDER OPERATING SYSTEM v1 (кратко)
Каждый день:
Утро (5 минут)
- git status
- git pull develop
- выбрать 1 главную задачу
- открыть Cursor
День
работа только в feature branch
Вечер
commit / push / note in PROJECT_LOG
Что запрещено себе теперь

❌ “быстро поправлю на сервере”
❌ “сделаю прямо в develop без ветки”
❌ “потом разберусь с git”
