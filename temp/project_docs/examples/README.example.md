# TimeWoven

> Цифровая экосистема семейного наследия — сохраняй истории, голоса и артефакты своей семьи через поколения.

[![Python](https://img.shields.io/badge/Python-3.11+-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688)]()
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14+-336791)]()
[![License](https://img.shields.io/badge/License-Private-red)]()

---

## 📖 О проекте

**TimeWoven** — это не просто генеалогическое дерево. Центральный элемент экосистемы — «Воспоминание»: субъективная единица смысла (аудио, текст, фотография), привязанная к конкретным людям, местам и эпохам. Проект превращает семейный архив в живую, интерактивную память.

### Ключевые возможности

- **Семейное дерево** — интерактивное визуальное древо с кликабельными узлами и профилями
- **Временная шкала** — хронологическая лента воспоминаний семьи с привязкой к персонам
- **Союзы и связи** — моделирование браков, партнёрств и родственных связей с временным измерением
- **Аудио-воспоминания** — запись и транскрибация голосовых историй (Whisper pipeline)
- **Импульс дня** — ежедневная рассылка через Telegram-бота с фактом из семейной истории

---

## ⚡ Быстрый старт

### Требования

- Python `3.11+`
- PostgreSQL `14+`
- Git

### Установка

```bash
# 1. Клонирование репозитория
git clone git@github.com:Dmitriy-Bondarev/TimeWoven.git
cd TimeWoven

# 2. Создание виртуального окружения
python3 -m venv .venv
source .venv/bin/activate

# 3. Установка зависимостей
pip install -r requirements.txt

# 4. Настройка окружения
cp .env.example .env
# Отредактируйте .env:
#   DATABASE_URL=postgresql+psycopg2://timewoven_user:PASSWORD@localhost:5432/timewoven
#   SECRET_KEY=your-secret-key

# 5. Инициализация базы данных
python -c "from app.config import engine; from app.models import Base; Base.metadata.create_all(engine)"

# 6. Запуск dev-сервера
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Приложение будет доступно по адресу: `http://localhost:8000`

---

## 🏗 Архитектура

```
TimeWoven/
├── app/
│   ├── main.py          # Точка входа FastAPI
│   ├── config.py        # Конфигурация и .env
│   ├── models/          # SQLAlchemy модели (Person, Union, Memory)
│   ├── routes/          # API эндпоинты (family, timeline, admin, auth)
│   ├── services/        # Бизнес-логика
│   ├── repositories/    # Слой доступа к данным
│   ├── schemas/         # Pydantic-схемы
│   └── templates/       # Jinja2 шаблоны
├── static/              # CSS, JS, аватары, загрузки
├── data/raw/            # Необработанные аудио для Whisper
├── tests/
├── docs/adr/            # Architecture Decision Records
├── .env.example
├── requirements.txt
├── TECH_PASSPORT.md     # Полный технический паспорт
├── DB_CHANGELOG.md      # Журнал изменений БД
└── README.md            # ← Вы здесь
```

Подробная архитектура описана в [TECH_PASSPORT.md](TECH_PASSPORT.md).

---

## 🗄 База данных

| Таблица                  | Назначение                                              |
|--------------------------|---------------------------------------------------------|
| `people`                 | Персоны семейного дерева (ФИО, даты, биография)         |
| `person_relationships`   | Связи между персонами с temporal-полями                  |
| `unions`                 | Браки и партнёрства (partner_1, partner_2, даты)         |
| `memories`               | Воспоминания (аудио, текст, фото) привязанные к персонам |

История изменений схемы: [DB_CHANGELOG.md](DB_CHANGELOG.md)

---

## 🔧 Конфигурация

| Переменная            | Описание                                  | Значение по умолчанию             |
|-----------------------|-------------------------------------------|-----------------------------------|
| `DATABASE_URL`        | Строка подключения к PostgreSQL           | —                                 |
| `SECRET_KEY`          | Ключ для подписи сессий / токенов         | —                                 |
| `DEBUG`               | Режим отладки                             | `false`                           |
| `APP_HOST`            | Хост для Uvicorn                          | `127.0.0.1`                       |
| `APP_PORT`            | Порт для Uvicorn                          | `8000`                            |

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

---

## 🚀 Деплой

Продакшен-деплой описан в [TECH_PASSPORT.md](TECH_PASSPORT.md#5-инфраструктура-и-деплой).

```bash
ssh root@server
cd /root/projects/TimeWoven
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt
systemctl restart timewoven
```

---

## 📚 Документация

| Документ                                        | Описание                           |
|-------------------------------------------------|------------------------------------|
| [TECH_PASSPORT.md](TECH_PASSPORT.md)            | Полный технический паспорт         |
| [DB_CHANGELOG.md](DB_CHANGELOG.md)              | Журнал изменений базы данных       |
| [docs/adr/](docs/adr/README.md)                 | Архитектурные решения (ADR)        |

---

## 🤝 Контрибьюция

1. Создайте feature-ветку: `git checkout -b feature/{short-name}`
2. Коммитьте с осмысленными сообщениями: `feat: add union temporal fields`
3. Откройте Pull Request с описанием изменений

### Конвенция коммитов

```
{type}: {краткое описание}

Типы: feat | fix | docs | refactor | test | chore | infra
```

---

## 👤 Автор

**Дмитрий Бондарев** — Архитектор / Owner
- GitHub: [Dmitriy-Bondarev](https://github.com/Dmitriy-Bondarev)
- Email: dmitriy.bondarev@gmail.com
