# 📸 Технический паспорт проекта: TimeWoven (v1.3-postgres)

> **Дата обновления:** 2026-04-17  
> **Автор:** Дмитрий Бондарев  
> **Статус:** Active

---

## 1. Обзор проекта

**TimeWoven** — цифровая экосистема семейного наследия: вместо сухого генеалогического дерева в центре стоят «Воспоминания» как субъективные единицы смысла (аудио, текст, фото), привязанные к людям, событиям, местам и эпохам.

| Параметр            | Значение                                               |
|---------------------|--------------------------------------------------------|
| Репозиторий         | `git@github.com:Dmitriy-Bondarev/TimeWoven.git`        |
| Продакшен URL       | `https://app.timewoven.ru`                             |
| Лендинг URL         | `https://timewoven.ru`                                 |
| Документация        | `iCloud Drive/010_Business/020_TimeWoven/Docs/`        |
| Баг-трекер          | GitHub Issues                                          |
| Лицензия            | Private                                                |

---

## 2. Стек технологий

### 2.1 Ядро

| Слой              | Технология        | Версия        | Назначение                                     |
|-------------------|-------------------|---------------|-----------------------------------------------|
| Язык              | Python            | 3.11+         | Основной язык бэкенда                         |
| Фреймворк         | FastAPI           | 0.110+        | REST/HTML, маршрутизация, валидация           |
| ORM               | SQLAlchemy        | 2.0+          | Работа с БД, модели, запросы                  |
| База данных       | PostgreSQL        | 14+           | Основное хранилище данных                     |
| База данных (legacy) | SQLite         | —             | Архивная БД (старые дампы, family_actual.db)  |
| Шаблонизатор      | Jinja2            | 3.1+          | Серверный рендеринг HTML                      |

### 2.2 Инфраструктура

| Компонент          | Технология        | Назначение                                     |
|--------------------|-------------------|-----------------------------------------------|
| Веб-сервер         | Nginx             | Reverse proxy, статика, SSL termination       |
| ASGI-сервер        | Uvicorn           | Запуск FastAPI-приложения                     |
| SSL/TLS            | Certbot           | Let’s Encrypt сертификаты, автообновление     |
| Процесс-менеджер   | systemd           | Автозапуск и мониторинг сервиса timewoven     |
| CI/CD              | GitHub + manual   | Ручной деплой: git pull + restart             |

### 2.3 Внешние интеграции

| Сервис             | API / SDK             | Назначение                       |
|--------------------|-----------------------|----------------------------------|
| Telegram Bot       | python-telegram-bot   | Рассылка «Импульса дня» (backlog) |
| Whisper / ASR      | openai-whisper/CLI    | Транскрибация аудиовоспоминаний (backlog) |

---

## 3. Архитектура

### 3.1 Высокоуровневая схема

```text
┌─────────┐    HTTPS    ┌─────────┐    proxy    ┌──────────┐
│ Browser │ ───────────►│  Nginx  │────────────►│ Uvicorn  │
└─────────┘             └─────────┘            └──────────┘
                              │                     │
                              │ /static/            ▼
                              │ (отдача)      ┌──────────┐
                              ▼              │ FastAPI   │
                        ┌──────────┐         │ (routes/) │
                        │  Static  │         └──────────┘
                        └──────────┘               │
                                                   ▼
                                             ┌──────────┐
                                             │PostgreSQL│
                                             │   14+    │
                                             └──────────┘
```

### 3.2 Структура каталогов

```text
/root/projects/TimeWoven/
├── app/                          # FastAPI-приложение
│   ├── main.py                   # ASGI-приложение, точки входа
│   ├── config.py                 # Настройки, DATABASE_URL, .env
│   ├── models/                   # SQLAlchemy модели
│   ├── routes/                   # Эндпоинты (family, timeline, auth, admin)
│   ├── services/                 # Бизнес-логика
│   ├── repositories/             # Слой доступа к данным
│   ├── schemas/                  # Pydantic-схемы
│   └── templates/                # Jinja2-шаблоны
├── static/
│   └── images/
│       ├── avatars/              # Аватары персон
│       └── uploads/              # Загруженные медиа
├── data/
│   └── db/                       # Архивы SQLite (legacy)
├── backups/                      # Резервные копии БД/данных
├── docs/                         # Внутренняя документация (ADR, changelog)
├── temp/                         # Временные файлы, дампы, экспорты
├── TECH_PASSPORT.md              # Текущий документ
├── DB_CHANGELOG.md               # История изменений БД
├── CHANGELOG.md                  # Релизный changelog продукта
├── README.md                     # Обзор проекта
└── requirements.txt
```

### 3.3 Модульная архитектура

| Модуль              | Файл(ы)                     | Ответственность                                |
|---------------------|-----------------------------|------------------------------------------------|
| Family Tree         | `routes/family.py`          | Дерево семьи, профили персон                   |
| Timeline            | `routes/timeline.py`        | Лента событий и воспоминаний                   |
| Auth                | `routes/auth.py`            | PIN-аутентификация семейного доступа           |
| Admin               | `routes/admin.py`           | CRUD персон, связей, воспоминаний              |
| Unions              | `models/union.py`, services | Браки/партнёрства, их жизненный цикл           |
| Memories            | `models/memory.py`          | Воспоминания и их привязка к персон/событиям   |

---

## 4. Доменная модель

### 4.1 Ключевые сущности

| Сущность      | Таблица БД             | Описание                                          |
|---------------|------------------------|---------------------------------------------------|
| Person        | `people`               | Человек в семейном графе                         |
| Relationship  | `person_relationships` | Направленная связь между персонами               |
| Union         | `unions`               | Брак/партнёрство двух персон                     |
| UnionChild    | `union_children`       | Привязка ребёнка к союзу                         |
| Memory        | `memories`             | Воспоминание (аудио, текст, фото)                |
| MemoryPerson  | `memory_people`        | Связь воспоминания с персонами                   |
| Quote         | `quotes`               | Цитаты / ключевые фразы                          |
| AvatarHistory | `avatar_history`       | История аватаров персоны                         |

### 4.2 Связи между сущностями

```text
Person 1──* PersonRelationship *──1 Person
    │           (bioparent, child, spouse, etc.)
    │
    ├──* Union *──1 Person
    │    (partner_1, partner_2, start_date, end_date)
    │
    ├──* UnionChildren
    │       (child_id, union_id)
    │
    └──* Memory
         (через MemoryPeople: tagged persons, дата, тип)
```

### 4.3 Бизнес-правила (ключевые)

- **Golden Record:** у каждой персоны есть канонический профиль, к которому приводится вся информация (имена, даты, связи).
- **Temporal Relationships:** `PersonRelationship.valid_from/valid_to` описывают период действия связи в реальном времени, что позволяет восстанавливать состояние семьи на любую дату.
- **Union Integrity:** каждый `Union` связывает ровно двух `Person` с ролями partner_1 и partner_2; даты `start_date`/`end_date` отражают жизненный цикл союза.
- **Death Propagation:** смерть (`death_date` в `people`) ограничивает `valid_to` брачных связей, но не разрывает биологическое родство.

---

## 5. Временная модель связей (valid_from / valid_to)

### 5.1 Общая модель времени

- Используется **valid-time** модель: храним период, когда факт связи считается истинным в реальном мире.
- Интервал считается полуоткрытым: `[valid_from, valid_to)`, запрос на «актуальность на дату»:

```sql
WHERE valid_from <= :date
  AND valid_to   >  :date
```

- Открытый интервал всегда записывается как `valid_to = '9999-12-31'`, `NULL` не используется для конца периода.

### 5.2 Родительско-детские связи (bioparent / child)

- `relationship_type_id = 1` — `bioparent` (родитель → ребёнок).
- `relationship_type_id = 2` — `child` (ребёнок → родитель).

**valid_from**

- Для обоих типов связей `valid_from` синхронизирован с `People.birth_date` ребёнка:
  - в `bioparent` ребёнок = `person_to_id`;
  - в `child` ребёнок = `person_from_id`.
- Если у ребёнка нет `birth_date`, `valid_from` временно может быть пуст (требует доочистки данных).

**valid_to**

- Биологическое родство не прекращается во времени.
- Для всех `bioparent` и `child` используется константа `valid_to = '9999-12-31'`.
- Смерть отражается только в `People.death_date` и не обрезает родительско-детскую связь.

### 5.3 Браки и партнёрства (spouselegal / spousecommon)

- `relationship_type_id = 3` — `spouselegal` (официальный брак).
- `relationship_type_id = 4` — `spousecommon` (фактический союз; нормализация в процессе).

**valid_from**

- Для браков: дата свадьбы / регистрации (`spouselegal`), для `spousecommon` — дата начала фактических отношений.
- В дальнейшем будет синхронизация с `Unions.start_date` (когда данные будут заполнены).

**valid_to**

- `valid_to` больше не хранится как `NULL`; все открытые связи приведены к `9999-12-31`.
- Для `spouselegal` действует правило: при наличии `death_date` хотя бы у одного партнёра `valid_to` не может быть позже ранней даты смерти.
- Текущее `valid_to` рассчитывается как минимум из:
  - предыдущего `valid_to` (или `9999-12-31` при `NULL`),
  - `death_date` партнёра A,
  - `death_date` партнёра B.
- План: добавить `Unions.end_date` (развод/расставание) в расчёт, чтобы окончание брака = min(дата развода, дата смерти, текущее верхнее значение или `9999-12-31`).

---

## 6. Инфраструктура и деплой

### 6.1 Серверное окружение

| Параметр            | Значение                                  |
|---------------------|-------------------------------------------|
| Хостинг             | Hostkey VPS                               |
| ОС                  | Ubuntu 22.04 LTS                          |
| IP                  | 193.187.95.221                            |
| Домен (лендинг)     | `timewoven.ru`                            |
| Домен (приложение)  | `app.timewoven.ru`                        |
| SSH доступ          | `root@193.187.95.221` (по ключу)          |
| Путь к проекту      | `/root/projects/TimeWoven`                |
| Путь к статике      | `/root/projects/TimeWoven/static/`        |

### 6.2 PostgreSQL

- Host: `localhost:5432`  
- Database: `timewoven`  
- User: `timewoven_user`  
- DSN: `postgresql+psycopg2://timewoven_user:***@localhost:5432/timewoven`

### 6.3 Процедура деплоя

```bash
# 1. Подключение к серверу
ssh root@193.187.95.221

# 2. Обновление кода
cd /root/projects/TimeWoven
git pull origin main

# 3. Обновление зависимостей
source .venv/bin/activate
pip install -r requirements.txt

# 4. Миграции БД (когда появится механизм миграций)
# alembic upgrade head   # (планируется)

# 5. Перезапуск сервиса
systemctl restart timewoven

# 6. Проверка
systemctl status timewoven
curl -s https://app.timewoven.ru/health
```

### 6.4 Systemd Unit

```ini
# /etc/systemd/system/timewoven.service
[Unit]
Description=TimeWoven FastAPI Application
After=network.target postgresql.service

[Service]
User=root
WorkingDirectory=/root/projects/TimeWoven
ExecStart=/root/projects/TimeWoven/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
EnvironmentFile=/root/projects/TimeWoven/.env

[Install]
WantedBy=multi-user.target
```

### 6.5 Nginx конфигурация

```nginx
# /etc/nginx/sites-available/app.timewoven.ru
server {
    listen 443 ssl http2;
    server_name app.timewoven.ru;

    ssl_certificate     /etc/letsencrypt/live/app.timewoven.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.timewoven.ru/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /root/projects/TimeWoven/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

---

## 7. Текущий статус и Roadmap (v1.3-postgres)

### 7.1 Завершённые

- [x] Миграция SQLite → PostgreSQL 14 (основная БД).
- [x] Поднятие продовой PostgreSQL и подключение через SQLAlchemy.
- [x] Temporal normalization v1: `PersonRelationship.valid_from/valid_to`.
- [x] Ввод модели `Unions` и `UnionChildren` для модельки семьи.
- [x] SSL и лендинг на `timewoven.ru`.

### 7.2 В работе

- [ ] Temporal normalization v2 — полная интеграция `Unions.start_date/end_date` с брачными связями.
- [ ] Переключение всех участков кода FastAPI на PostgreSQL (db.py и репозитории).

### 7.3 Backlog

| Приоритет | Задача                               | Описание                                        |
|-----------|--------------------------------------|-------------------------------------------------|
| P0        | Telegram Bot: «Импульс дня»          | Рассылка воспоминаний/цитат в Telegram          |
| P0        | Визуальное дерево                    | Интерактивное древо вместо статического списка  |
| P1        | Whisper Pipeline                     | Транскрибация аудио из `data/raw/`              |
| P1        | Refactor main.py                     | Полный вынос в `routes/`                        |
| P2        | Автоматические бэкапы PostgreSQL     | Cron + pg_dump + ротация                        |
| P2        | Улучшение UI и брендинга             | Единый стиль для `timewoven.ru` и `app.*`       |

---

## 8. Безопасность и доступы

| Аспект               | Решение                                         |
|----------------------|-------------------------------------------------|
| Аутентификация       | PIN-доступ для семейного круга                  |
| Авторизация          | Роли: admin, family_member, viewer              |
| Шифрование           | HTTPS (Let’s Encrypt), планируется at-rest      |
| Секреты              | `.env` файл (DATABASE_URL, SECRET_KEY, и др.)   |
| Бэкапы               | Ручные pg_dump (планируется автоматизация)      |

**Контакты**

| Роль               | Имя               | Контакт                     |
|--------------------|-------------------|-----------------------------|
| Архитектор / Owner | Дмитрий Бондарев  | dmitriy.bondarev@gmail.com |

---

## 9. Управление зависимостями (requirements.txt / requirements.lock)

### 9.1 Файлы

- `requirements.txt` — **ручной, осмысленный список** зависимостей с комментариями и группировкой по смыслу (web, ORM, тесты, линтеры и т.д.).  
- `requirements.lock.txt` — **машинный снимок** (`pip freeze`), фиксирует точные версии всех установленных пакетов для повторяемых окружений.

Оба файла лежат в корне проекта.

### 9.2 Протокол обновления

1. Установить/обновить пакеты локально (в .venv) через `pip install ...`.  
2. Обновить `requirements.lock.txt`:

   ```bash
   pip freeze > requirements.lock.txt
   ```

3. Вручную актуализировать `requirements.txt`:
   - добавить новые пакеты в соответствующие блоки (web / ORM / dev и т.д.),
   - при необходимости обновить версии и комментарии.
4. Закоммитить оба файла с осмысленным сообщением:

   ```bash
   git add requirements.txt requirements.lock.txt
   git commit -m "deps: bump FastAPI and sync requirements.lock"
   ```

### 9.3 Использование на окружениях

- **Прод / staging:** использовать `requirements.txt` как основной источник (при необходимости можно установить строго по lock-файлу).  
- **Новые окружения / восстановление:** при точном воспроизведении среды сначала смотреть на `requirements.lock.txt`, затем при необходимости сводить различия в `requirements.txt`.