# 📸 Технический паспорт проекта: TimeWoven (v1.3-postgres)

> **Дата обновления:** 2026-04-17
> **Автор:** Дмитрий Бондарев
> **Статус:** Active

---

## 1. Обзор проекта

**TimeWoven** — цифровая экосистема семейного наследия. В отличие от обычных генеалогических архивов, центральным элементом является «Воспоминание» — субъективная единица смысла (аудио, текст, фото), привязанная к конкретным людям, местам и эпохам.

| Параметр            | Значение                                               |
|---------------------|--------------------------------------------------------|
| Репозиторий         | `git@github.com:Dmitriy-Bondarev/TimeWoven.git`        |
| Продакшен URL       | `https://app.timewoven.ru`                              |
| Лендинг URL         | `https://timewoven.ru`                                  |
| Документация        | `iCloud Drive/020_TimeWoven/Docs/`                      |
| Баг-трекер          | GitHub Issues                                           |
| Лицензия            | Private                                                 |

---

## 2. Стек технологий

### 2.1 Ядро

| Слой              | Технология        | Версия   | Назначение                             |
|-------------------|-------------------|----------|----------------------------------------|
| Язык              | `Python`          | `3.11+`  | Основной язык бэкенда                  |
| Фреймворк         | `FastAPI`         | `0.110+` | REST API, маршрутизация, валидация     |
| ORM               | `SQLAlchemy`      | `2.0+`   | Работа с БД, модели, миграции          |
| База данных       | `PostgreSQL`      | `14+`    | Основное хранилище данных              |
| Шаблонизатор      | `Jinja2`          | `3.1+`   | Серверный рендеринг HTML               |

### 2.2 Инфраструктура

| Компонент          | Технология        | Назначение                              |
|--------------------|-------------------|-----------------------------------------|
| Веб-сервер         | `Nginx`           | Reverse proxy, статика, SSL termination |
| ASGI-сервер        | `Uvicorn`         | Запуск FastAPI приложения               |
| SSL/TLS            | `Certbot`         | Автоматическое получение Let's Encrypt  |
| Процесс-менеджер   | `systemd`         | Автозапуск и мониторинг сервиса         |
| CI/CD              | `GitHub + manual` | Деплой через git pull + restart         |

### 2.3 Внешние интеграции

| Сервис             | API / SDK              | Назначение                          |
|--------------------|------------------------|-------------------------------------|
| Telegram Bot       | `python-telegram-bot`  | Рассылка «Импульса дня»            |
| Whisper            | `openai-whisper`       | Транскрибация аудиовоспоминаний     |

---

## 3. Архитектура

### 3.1 Высокоуровневая схема

```
┌─────────┐    HTTPS    ┌─────────┐    proxy    ┌──────────┐
│ Browser  │ ──────────► │  Nginx  │ ──────────► │ Uvicorn  │
└─────────┘             └─────────┘             └──────────┘
                              │                      │
                              │ /static/             ▼
                              │ (прямая          ┌──────────┐
                              │  отдача)         │ FastAPI   │
                              ▼                  │ (routes/) │
                        ┌──────────┐             └──────────┘
                        │ Static   │                  │
                        │ Files    │                  ▼
                        └──────────┘             ┌──────────┐
                                                 │PostgreSQL│
                                                 │ (v14+)   │
                                                 └──────────┘
```

### 3.2 Структура каталогов

```
TimeWoven/
├── app/
│   ├── main.py               # Точка входа, ASGI app instance
│   ├── config.py             # DATABASE_URL, SECRET_KEY, .env
│   ├── models/               # SQLAlchemy модели
│   │   ├── __init__.py
│   │   ├── person.py         # Person — ядро графа
│   │   ├── relationship.py   # PersonRelationship — связи
│   │   ├── union.py          # Union — браки/партнёрства
│   │   └── memory.py         # Memory — воспоминания
│   ├── routes/               # Модульные эндпоинты
│   │   ├── __init__.py
│   │   ├── family.py         # /family/* — дерево, профили
│   │   ├── timeline.py       # /timeline/* — лента
│   │   ├── admin.py          # /admin/* — управление
│   │   └── auth.py           # /auth/* — PIN-логин
│   ├── services/             # Бизнес-логика
│   ├── repositories/         # Слой доступа к данным
│   ├── schemas/              # Pydantic-схемы
│   └── templates/            # Jinja2 HTML-шаблоны
├── static/
│   ├── css/
│   ├── js/
│   └── images/
│       ├── avatars/          # Аватары персон
│       └── uploads/          # Загруженные медиа
├── data/
│   └── raw/                  # Необработанные аудио (Whisper)
├── tests/
├── docs/
│   ├── adr/                  # Architecture Decision Records
│   └── changelog/
├── .env
├── requirements.txt
├── TECH_PASSPORT.md
├── DB_CHANGELOG.md
└── README.md
```

### 3.3 Модульная архитектура

| Модуль              | Файл(ы)                     | Ответственность                                |
|---------------------|------------------------------|------------------------------------------------|
| Family Tree         | `routes/family.py`           | Построение дерева, профили персон, навигация    |
| Timeline            | `routes/timeline.py`         | Хронологическая лента воспоминаний              |
| Auth                | `routes/auth.py`             | PIN-код аутентификация семейного доступа        |
| Admin               | `routes/admin.py`            | CRUD персон, связей, воспоминаний               |
| Union Management    | `services/union_service.py`  | Логика браков, разводов, партнёрств             |

---

## 4. Доменная модель

### 4.1 Ключевые сущности

| Сущность            | Таблица БД              | Описание                                        |
|---------------------|-------------------------|-------------------------------------------------|
| Персона             | `people`                | Человек в семейном дереве (живой или ушедший)    |
| Связь               | `person_relationships`  | Направленная связь между двумя персонами         |
| Союз                | `unions`                | Брак или партнёрство с датами и статусом         |
| Воспоминание        | `memories`              | Аудио, текст или фото, привязанные к персонам    |

### 4.2 Связи между сущностями

```
Person 1──* PersonRelationship *──1 Person
    │           (parent→child, sibling, etc.)
    │
    ├──* Union *──1 Person
    │    (partner_1, partner_2, start_date, end_date)
    │
    └──* Memory
         (tagged persons, date, type, content)
```

### 4.3 Бизнес-правила

- **Temporal Relationships:** PersonRelationship содержит `valid_from` и `valid_to` для моделирования изменений связей во времени (усыновление, развод)
- **Union Integrity:** Каждый Union связывает ровно двух Person (partner_1, partner_2) с обязательными `start_date` и опциональным `end_date`
- **Death Propagation:** При указании `death_date` у Person — `valid_to` всех активных связей обновляется автоматически
- **Golden Record:** Каждая персона имеет одну «золотую запись» — канонический профиль, к которому привязаны все вариации имени

---

## 5. Инфраструктура и деплой

### 5.1 Серверное окружение

| Параметр            | Значение                                  |
|---------------------|-------------------------------------------|
| Хостинг             | Hostkey (VPS)                             |
| ОС                  | Ubuntu 22.04 LTS                          |
| Домен (лендинг)     | `timewoven.ru`                            |
| Домен (приложение)  | `app.timewoven.ru`                        |
| SSH доступ          | `root@{server_ip}`                        |
| Путь к проекту      | `/root/projects/TimeWoven`                |
| Путь к медиа        | `/root/projects/TimeWoven/static/images/` |

### 5.2 Процедура деплоя

```bash
# 1. Подключение к серверу
ssh root@{server_ip}

# 2. Обновление кода
cd /root/projects/TimeWoven
git pull origin main

# 3. Обновление зависимостей
source .venv/bin/activate
pip install -r requirements.txt

# 4. Перезапуск сервиса
systemctl restart timewoven

# 5. Проверка
systemctl status timewoven
curl -s https://app.timewoven.ru/health
```

### 5.3 Systemd Unit

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

### 5.4 Nginx конфигурация

```nginx
# /etc/nginx/sites-available/app.timewoven.ru
server {
    listen 443 ssl http2;
    server_name app.timewoven.ru;

    ssl_certificate     /etc/letsencrypt/live/app.timewoven.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.timewoven.ru/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /root/projects/TimeWoven/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}

# Лендинг на основном домене
server {
    listen 443 ssl http2;
    server_name timewoven.ru;

    ssl_certificate     /etc/letsencrypt/live/timewoven.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/timewoven.ru/privkey.pem;

    root /var/www/timewoven-landing;
    index index.html;
}
```

---

## 6. Безопасность

| Аспект               | Решение                                         |
|----------------------|-------------------------------------------------|
| Аутентификация       | PIN-код для семейного доступа                    |
| Авторизация          | Ролевая модель (admin, family_member, viewer)    |
| Шифрование           | HTTPS (Let's Encrypt), будущее: шифрование воспоминаний at rest |
| Секреты              | `.env` файл (DATABASE_URL, SECRET_KEY)           |
| Бэкапы               | pg_dump ежедневно (планируется автоматизация)    |

---

## 7. Текущий статус и Roadmap

### 7.1 Завершённые модули

- [x] Модульная архитектура routes/ — 2026-04-16
- [x] Миграция SQLite → PostgreSQL — 2026-04-16
- [x] Union модель для семейного дерева — 2026-04-16
- [x] SSL + лендинг на основном домене — 2026-04-16
- [x] Temporal normalization v1 (valid_from/valid_to) — 2026-04-17

### 7.2 В работе

- [ ] Temporal normalization v2 — заполнение valid_from/valid_to для unions → spouse relationships

### 7.3 Backlog

| Приоритет | Задача                               | Описание                                              |
|-----------|--------------------------------------|-------------------------------------------------------|
| P0        | Telegram Bot                         | Интеграция бота для рассылки «Импульса дня»           |
| P0        | Визуальное дерево                    | Интерактивное древо вместо HTML-списка                |
| P1        | Whisper Pipeline                     | Автотранскрибация аудио из /data/raw/                 |
| P1        | Branding / Favicon                   | Единый брендинг для timewoven.ru и app.timewoven.ru   |
| P2        | Автоматические бэкапы                | Cron + pg_dump + ротация                              |
| P2        | Рефакторинг main.py                  | Перенос оставшихся эндпоинтов в routes/               |

---

## 8. Контакты и доступы

| Роль                 | Имя                 | Контакт                              |
|----------------------|---------------------|--------------------------------------|
| Архитектор / Owner   | Дмитрий Бондарев    | dmitriy.bondarev@gmail.com           |

---

## 📎 Приложения

- [ADR Index](docs/adr/README.md)
- [DB Changelog](DB_CHANGELOG.md)

---

> **Конвенция обновления:** Этот документ обновляется при каждом значимом изменении архитектуры, инфраструктуры или стека. Версия в заголовке (v1.3-postgres) соответствует мажорной вехе проекта.
