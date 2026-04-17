# TimeWoven

> Семейное веб‑приложение для хранения и передачи воспоминаний через поколения: голос, истории и фото, связанные с людьми, событиями и эпохами.

[![Python](https://img.shields.io/badge/Python-3.11+-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688)]()
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-336791)]()
[![License](https://img.shields.io/badge/License-Private-green)]()

---

## 📖 О проекте

TimeWoven помогает семье собирать и осмыслять свои воспоминания: каждое воспоминание — это не просто факт, а субъективный фрагмент истории, привязанный к людям, событиям и местам.  
Проект строит живое семейное древо, где аудио, текст и фотографии становятся частью единого смыслового полотна.

### Ключевые возможности

- **Семейное древо** — визуальная структура семьи на основе персон, союзов и детей.
- **Воспоминания и таймлайн** — лента воспоминаний, событий и цитат, связанных с людьми.
- **История аватаров** — управление визуальной идентичностью персон во времени.
- **Подготовка к Telegram / ASR** — задел под «Импульс дня» и транскрибацию аудио (Whisper).

---

## ⚡ Быстрый старт

### Требования

- Python 3.11+
- PostgreSQL 14+
- Git

### Установка (локально, SQLite как архив)

```bash
# 1. Клонирование репозитория
git clone git@github.com:Dmitriy-Bondarev/TimeWoven.git
cd TimeWoven

# 2. Создание виртуального окружения
python3 -m venv .venv
source .venv/bin/activate

# 3. Установка зависимостей
pip install -r requirements.txt
```

### Запуск c SQLite (локальное ознакомление)

```bash
# Восстановление локальной SQLite (если есть дамп)
sqlite3 data/db/family.db < data/db/family.sql  # при наличии дампа

# Запуск dev-сервера
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Приложение будет доступно по адресу: `http://localhost:8000`.

### Подключение к PostgreSQL

Продовая БД описана в [TECH_PASSPORT.md](TECH_PASSPORT.md#6-инфраструктура-и-деплой) и [DB_CHANGELOG.md](DB_CHANGELOG.md).  
Базовые параметры:

- Host: `localhost:5432` (на сервере)
- Database: `timewoven`
- User: `timewoven_user`
- DSN: `postgresql+psycopg2://timewoven_user:***@localhost:5432/timewoven`

`DATABASE_URL` задаётся через `.env`, чтение реализовано в `app/config.py`.

---

## 🏗 Архитектура

```text
TimeWoven/
├── app/
│   ├── main.py          # Точка входа FastAPI (ASGI)
│   ├── config.py        # Конфигурация и .env
│   ├── models/          # SQLAlchemy модели (Person, Union, Memory, Relationship)
│   ├── routes/          # Эндпоинты: family, timeline, auth, admin
│   ├── services/        # Бизнес-логика
│   ├── repositories/    # Доступ к данным
│   ├── schemas/         # Pydantic-схемы
│   └── templates/       # Jinja2-шаблоны
├── static/
│   └── images/
│       ├── avatars/     # Аватары персон
│       └── uploads/     # Загруженные медиа
├── data/
│   └── db/              # Архивы SQLite / дампы
├── backups/             # Резервные копии БД
├── docs/
│   └── adr/             # Architecture Decision Records
├── temp/                # Временные файлы, дампы, экспорты
├── TECH_PASSPORT.md     # Технический паспорт
├── DB_CHANGELOG.md      # Журнал изменений БД
├── CHANGELOG.md         # Релизный changelog продукта
└── README.md            # ← вы здесь
```

Подробная архитектура и temporal‑модель связей описаны в [TECH_PASSPORT.md](TECH_PASSPORT.md).

---

## 🗄 База данных

Основная БД — PostgreSQL 14. Важные таблицы:

| Таблица               | Назначение                                        |
|-----------------------|---------------------------------------------------|
| `people`              | Персоны (люди в семейном графе)                   |
| `person_relationships`| Связи между людьми (родство, браки и др.)         |
| `unions`              | Союзы/браки (двое партнёров, даты начала/окончания) |
| `union_children`      | Привязка детей к союзам                           |
| `memories`            | Воспоминания (аудио, текст, фото)                 |
| `memory_people`       | Связи воспоминаний с персонами                    |
| `quotes`              | Цитаты / ключевые фразы                           |
| `avatar_history`      | История аватаров персон                           |

История изменений схемы и данных: [DB_CHANGELOG.md](DB_CHANGELOG.md).

---

## 🔧 Конфигурация

Параметры задаются через `.env`:

| Переменная      | Описание                               | Значение по умолчанию        |
|-----------------|----------------------------------------|------------------------------|
| `DATABASE_URL`  | Подключение к БД (PostgreSQL/SQLite)   | `sqlite:///data/db/family.db`|
| `SECRET_KEY`    | Секрет для сессий/подписей             | —                            |
| `DEBUG`         | Режим отладки FastAPI                  | `false`                      |

---

## 🧪 Тестирование

```bash
# Запуск всех тестов
pytest

# С покрытием
pytest --cov=app --cov-report=html

# Конкретный модуль
pytest tests/test_family.py -v
```

(Структура tests/ будет развиваться по мере роста проекта.)

---

## 🚀 Деплой

Продакшен-деплой подробно описан в [TECH_PASSPORT.md](TECH_PASSPORT.md#6-инфраструктура-и-деплой).

Кратко:

```bash
ssh root@193.187.95.221
cd /root/projects/TimeWoven
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
systemctl restart timewoven
```

---

## 📚 Документация

| Документ                               | Описание                                 |
|----------------------------------------|------------------------------------------|
| [TECH_PASSPORT.md](TECH_PASSPORT.md)   | Полный технический паспорт проекта       |
| [DB_CHANGELOG.md](DB_CHANGELOG.md)     | Журнал изменений базы данных             |
| `docs/adr/`                            | Архитектурные решения (ADR)              |
| `temp/project_docs/`                   | Пакет документации и шаблонов (на сервере)|

---

## 👤 Автор

**Дмитрий Бондарев** — архитектор и владелец продукта TimeWoven.  
- GitHub: [Dmitriy-Bondarev](https://github.com/Dmitriy-Bondarev)  
- Email: dmitriy.bondarev@gmail.com