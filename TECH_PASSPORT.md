# Технический паспорт: TimeWoven v1.3

## Стек
- Backend: Python 3.x, FastAPI, Uvicorn
- Database: PostgreSQL 14 (основная БД с 2026-04-17)
- Database legacy: SQLite (family_actual.db — архивная копия)
- Frontend: Jinja2 Templates
- Инфраструктура: Ubuntu 22.04, Nginx, Certbot, Systemd
- Сервер: 193.187.95.221
- Git: github.com/Dmitriy-Bondarev/TimeWoven

## Структура проекта
- /root/projects/TimeWoven — корень проекта
- /root/projects/TimeWoven/app/ — FastAPI приложение
- /root/projects/TimeWoven/data/db/ — SQLite архивы
- /root/projects/TimeWoven/backups/ — резервные копии
- /static/images/avatars/ — аватары
- /static/images/uploads/ — загрузки
- Документация: iCloud Drive -> 010_Business/020_TimeWoven/Docs/

## PostgreSQL
- Host: localhost:5432
- Database: timewoven
- User: timewoven_user
- URL: postgresql+psycopg2://timewoven_user:***@localhost:5432/timewoven

## Таблицы (13)
- People: 9 записей
- People_I18n: 18 записей
- Events: 6 записей
- Memories: 3 записи
- MemoryPeople: 16 записей
- Quotes: 3 записи
- AvatarHistory: 4 записи
- RelationshipType: 12 записей
- PersonRelationship: 26 записей
- Unions: 2 записи
- UnionChildren: 5 записей
- Places: пусто
- EventParticipants: пусто

## Доменная модель
- Графовая модель связей (PersonRelationship)
- Union-модель семьи (Unions + UnionChildren)
- Золотая запись (Source of Truth) через администратора
- ИИ как гипотеза (Review Dashboard)

## Текущий функционал (v1.3)
- Timeline: интерактивная лента событий и воспоминаний
- Family Tree Viewer: /family/tree на базе Unions
- PIN-авторизация участников
- Личный кабинет с историей аватаров (AvatarHistory)
- Лендинг: www.timewoven.ru (Nginx, HTTPS)

## Следующий шаг
- Переключить app/db.py на PostgreSQL
- Перезапустить timewoven.service
- Протестировать все роуты

## Backlog
- [ ] Переключение FastAPI на PostgreSQL (db.py)
- [ ] Telegram Bot: Импульс дня
- [ ] UI Дерева: интерактивное визуальное древо
- [ ] Whisper Pipeline: транскрибация аудио из /data/raw/
- [ ] Refactoring: перенос эндпоинтов из main.py в routes/

## Сервер
- OS: Ubuntu 22.04
- IP: 193.187.95.221
- Nginx: reverse proxy + static landing
- SSL: Certbot (автообновление через systemd)
- Сервис: timewoven.service (systemd)
- SSH: по ключу (без пароля)
