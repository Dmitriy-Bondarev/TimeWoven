# CHANGELOG — TimeWoven

## [v1.3-postgres] — 2026-04-17
### Добавлено
- PostgreSQL установлен и настроен на сервере
- База timewoven создана, пользователь timewoven_user
- Схема 13 таблиц создана в PostgreSQL
- Все данные перенесены из SQLite в PostgreSQL
- SSH-доступ по ключу без пароля
- Резервные копии в /backups/2026-04-17/

### Перенесено в PostgreSQL
- People: 9, People_I18n: 18, Events: 6
- Memories: 3, MemoryPeople: 16, Quotes: 3
- AvatarHistory: 4, RelationshipType: 12
- PersonRelationship: 26, Unions: 2, UnionChildren: 5

### В работе
- Переключение FastAPI (db.py) с SQLite на PostgreSQL

## [v1.2-stable] — 2026-04-16
### Зафиксировано
- Лендинг www.timewoven.ru через Nginx + HTTPS
- Дамп SQLite сохранён в /backups/
- TECH_PASSPORT.md и CHANGELOG.md добавлены в репозиторий
- Тег v1.2-stable на GitHub

## [v1.1]
### Добавлено
- Модульная архитектура routes/
- Нормализованная графовая модель БД
- Union-модель для семейного древа

## [v1.0]
### Добавлено
- Первый запуск FastAPI + SQLite
- Базовая авторизация
- Первые шаблоны Jinja2
