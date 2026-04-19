
Далее настраивается PostgreSQL (локальный или Docker) и переменные окружения.

### Настройка PostgreSQL и .env

Создать базу и пользователя (пример):

```sql
CREATE DATABASE timewoven;
CREATE USER timewoven_user WITH ENCRYPTED PASSWORD '***';
GRANT ALL PRIVILEGES ON DATABASE timewoven TO timewoven_user;
```

Создать файл `.env` в корне проекта:

```env
DATABASE_URL=postgresql+psycopg2://timewoven_user:***@localhost:5432/timewoven
SECRET_KEY=change_me
DEBUG=false
```

### Запуск dev-сервера

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Приложение будет доступно по адресу: `http://localhost:8000`  
Интерактивная документация FastAPI: `http://localhost:8000/docs` и `http://localhost:8000/redoc`.

---

## 🏗 Архитектура и структура проекта

Фактическая структура на сервере (`/root/projects/TimeWoven`) и в репозитории:

```text
TimeWoven/
├── app/                              # Исходный код FastAPI-приложения
│   ├── main.py                       # Точка входа (ASGI-приложение, подключение роутеров)
│   ├── config.py                     # Конфигурация и работа с .env / DATABASE_URL
│   ├── db/                           # Сессии и база (SessionLocal и др.)
│   ├── models/                       # SQLAlchemy модели (Person, PersonI18n, Union, Memory, Quote, Relationship и др.)
│   ├── schemas/                      # Pydantic-схемы запросов/ответов (в т.ч. GraphNode для семейного графа)
│   ├── api/
│   │   └── routes/                   # Эндпоинты (роутеры FastAPI)
│   │       ├── tree.py               # family routes + who-am-i + reply + person + timeline
│   │       ├── admin.py              # admin routes (login, people, transcriptions, avatars)
│   │       └── ...                   # прочие роутеры (healthcheck и т.д.)
│   ├── services/                     # Бизнес-логика (family_graph, вспомогательные сервисы)
│   │   └── family_graph.py           # Сборка графа семьи, преобразование Person → GraphNode
│   ├── security.py                   # Механизмы авторизации (require_admin() пока пропускает всех)
│   └── web/
│       ├── templates/                # Jinja2-шаблоны интерфейса
│       │   ├── family/
│       │   │   ├── home.html         # Главная: импульс дня
│       │   │   ├── profile.html      # Карточка человека
│       │   │   ├── timeline.html     # Таймлайн
│       │   │   ├── who_am_i.html     # Выбор пользователя
│       │   │   └── pin_form.html     # PIN-форма
│       │   └── admin/                # Шаблоны админки (login, people, transcriptions, avatars)
│       └── static/
│           ├── js/
│           │   └── family_graph.js   # D3.js граф семьи с click-навигацией по нодам
│           ├── css/                  # Стили фронтенда
│           └── images/               # Изображения (аватары и т.п.)
├── data/
│   └── db/                           # Архивы старых SQLite / вспомогательные дампы (исторический артефакт)
├── backups/                          # Резервные копии БД и важных файлов
├── temp/                             # Временные файлы (дампы, экспорты, черновики SQL)
│   └── project_docs/                 # Пакет документации, выгруженный с Mac
├── tech-docs/                        # Живущая рядом документация проекта
│   ├── adr/                          # Architecture Decision Records (ADR-001, ADR-002, ...)
│   └── README.md                     # Описание набора шаблонов и структуры docs
├── TECH_PASSPORT.md                  # Технический паспорт (high-level техническая карта)
├── DB_CHANGELOG.md                   # Журнал изменений схемы и данных БД
├── CHANGELOG.md                      # Релизный changelog продукта
├── requirements.txt                  # Осмысленный список зависимостей
├── requirements.lock.txt             # Полный снимок зависимостей (pip freeze)
└── README.md                         # ← вы здесь
```

Подробная архитектура и temporal‑модель связей описаны в [TECH_PASSPORT.md](TECH_PASSPORT.md).

---

## 🗄 База данных

Основная (и единственная рабочая) БД — PostgreSQL 14. Важные таблицы (логический уровень):

| Таблица                | Назначение                                        |
|------------------------|---------------------------------------------------|
| `people` / `Person`    | Персоны (люди в семейном графе)                   |
| `person_i18n`          | Локализованные имена и тексты персон              |
| `person_relationships` | Связи между людьми (родство, браки и др.)         |
| `unions`               | Союзы/браки (двое партнёров, даты начала/окончания) |
| `union_children`       | Привязка детей к союзам                           |
| `memories`             | Воспоминания (аудио, текст, фото)                 |
| `memory_people`        | Связи воспоминаний с персонами                    |
| `quotes`               | Ответы/цитаты на воспоминания (family replies)    |
| `avatar_history`       | История аватаров персон                           |

История изменений схемы и данных: [DB_CHANGELOG.md](DB_CHANGELOG.md).

---

## 🔧 Конфигурация

Параметры задаются через `.env`:

| Переменная      | Описание                             |
|-----------------|--------------------------------------|
| `DATABASE_URL`  | Подключение к БД (PostgreSQL)        |
| `SECRET_KEY`    | Секрет для сессий/подписей           |
| `DEBUG`         | Режим отладки FastAPI (`true/false`) |

`.env` загружается в `app/main.py` до инициализации подключения к БД и роутеров, чтобы и локально, и в проде использовать PostgreSQL.

---

## 🧪 Тестирование

```bash