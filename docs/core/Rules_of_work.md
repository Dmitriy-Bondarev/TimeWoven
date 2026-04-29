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