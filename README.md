# TimeWoven

Семейное веб-приложение для хранения и передачи воспоминаний через поколения.

## Стек

- Python 3.9+
- FastAPI + Uvicorn
- SQLAlchemy
- PostgreSQL 14 (основная БД)
- SQLite (архив / локальная разработка)
- Jinja2
- python-multipart

## Структура проекта

- `app/` — FastAPI-приложение
- `app/main.py` — точка входа (ASGI)
- `app/db.py` — конфигурация подключения к БД
- `app/templates/` — Jinja2-шаблоны
- `app/static/` — статика (CSS, JS, изображения)
- `data/db/` — дампы и архивы БД (SQLite / PostgreSQL)
- `backups/` — резервные копии продовой БД
- `TECH_PASSPORT.md` — технический паспорт проекта
- `DB_CHANGELOG.md` — история изменений структуры и данных

## Установка и запуск (локально, SQLite)

```bash
# Клонировать репозиторий
git clone git@github.com:Dmitriy-Bondarev/TimeWoven.git
cd TimeWoven

# Создать виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Восстановить БД из дампа (локальная SQLite)
sqlite3 data/db/family.db < data/db/family.sql

# Запустить сервер (локально, dev-режим)
python -m uvicorn app.main:app --reload
```

Приложение будет доступно по адресу: http://127.0.0.1:8000

## Подключение к PostgreSQL (prod / staging)

Продовая БД работает на PostgreSQL 14 и описана в `TECH_PASSPORT.md` и `DB_CHANGELOG.md`.

Базовые параметры (см. TECH_PASSPORT для актуальных значений):

- Host: `localhost:5432` (при работе на сервере)
- Database: `timewoven`
- User: `timewoven_user`
- DSN: `postgresql+psycopg2://timewoven_user:***@localhost:5432/timewoven`

Переключение приложения на PostgreSQL выполняется через конфигурацию в `app/db.py` и переменные окружения (см. комментарии внутри файла).

## Основные экраны

| URL                   | Описание                             |
|-----------------------|--------------------------------------|
| `/`                   | Импульс дня — случайная цитата с аудио |
| `/family/reply/{id}`  | Ответ на послание                    |
| `/family/person/{id}` | Карточка человека                    |
| `/who-am-i`           | Выбор участника                      |
| `/admin/people`       | Контроль качества данных             |
| `/admin/avatars`      | Загрузка аватаров                    |
| `/family/tree`        | Дерево семьи (визуальный просмотр)   |

## Участники

9 человек семьи Бондаревых — 3 поколения.

## Roadmap

- [ ] Переключение FastAPI на PostgreSQL (db.py)
- [ ] PIN-авторизация
- [ ] Timeline событий
- [ ] Дерево семьи (улучшенный UI)
- [ ] Уведомления в Telegram
- [ ] Whisper pipeline для транскрипции аудио
- [ ] Мобильная версия (PWA)