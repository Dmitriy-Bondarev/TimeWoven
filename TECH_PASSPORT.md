# Технический паспорт: TimeWoven v1.2

## Стек
- Backend: Python 3.x, FastAPI, Uvicorn
- Database: SQLite (family.db) → PostgreSQL (в процессе миграции)
- Frontend: Jinja2 Templates
- Инфраструктура: Ubuntu 22.04, Nginx, Certbot, Systemd
- Сервер: 193.187.95.221
- Git: github.com/Dmitriy-Bondarev/TimeWoven

## Структура проекта
- /root/projects/TimeWoven — код на сервере
- /static/images/avatars/ — аватары
- /static/images/uploads/ — загрузки
- Документация: iCloud Drive → 010_Business/020_TimeWoven/Docs/

## Доменная модель
- Графовая модель связей (PersonRelationship)
- Union-модель семьи
- Золотая запись (Source of Truth) — только через администратора
- ИИ как гипотеза (Review Dashboard)

## Текущий функционал (v1.2)
- Timeline: интерактивная лента событий и воспоминаний
- Family Tree Viewer: /family/tree на базе Unions
- PIN-авторизация участников
- Личный кабинет с историей аватаров (AvatarHistory)
- Лендинг: www.timewoven.ru (Nginx, статический HTML, HTTPS)

## Backlog
- [ ] Telegram Bot: Импульс дня
- [ ] UI Дерева: интерактивное визуальное древо
- [ ] Whisper Pipeline: транскрибация аудио из /data/raw/
- [ ] Refactoring: перенос эндпоинтов из main.py в routes/
- [ ] Миграция SQLite → PostgreSQL

## Сервер
- OS: Ubuntu 22.04
- IP: 193.187.95.221
- Nginx: reverse proxy + static landing
- SSL: Certbot (автообновление через systemd)
- Сервис: timewoven.service (systemd)
