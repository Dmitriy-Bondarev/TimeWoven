# CHANGELOG — TimeWoven

## [v1.2-stable] — 2026-04-16
### Зафиксировано
- Стабильная версия на SQLite перед миграцией на PostgreSQL
- Лендинг www.timewoven.ru поднят через Nginx + HTTPS (Certbot)
- Дамп БД сохранён в /backups/ (схема + данные + физическая копия)
- TECH_PASSPORT.md и CHANGELOG.md добавлены в репозиторий

### Текущий функционал
- Timeline, Family Tree Viewer, PIN-авторизация, AvatarHistory

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
