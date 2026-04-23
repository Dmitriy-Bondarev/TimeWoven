# 📸 Технический паспорт проекта: {PROJECT_NAME} (v{VERSION})

> **Дата обновления:** {YYYY-MM-DD}
> **Автор:** {AUTHOR}
> **Статус:** {Draft | Active | Archived}

---

## 1. Обзор проекта

**{PROJECT_NAME}** — {краткое описание проекта в 1–2 предложениях: что делает, для кого, ключевая ценность}.

| Параметр            | Значение                           |
|---------------------|------------------------------------|
| Репозиторий         | `{git_repo_url}`                   |
| Продакшен URL       | `{production_url}`                 |
| Стейджинг URL       | `{staging_url}`                    |
| Документация        | `{docs_location}`                  |
| Баг-трекер          | `{issue_tracker_url}`              |
| Лицензия            | `{license_type}`                   |

---

## 2. Стек технологий

### 2.1 Ядро

| Слой              | Технология        | Версия   | Назначение                        |
|-------------------|-------------------|----------|-----------------------------------|
| Язык              | `{language}`      | `{ver}`  | {назначение}                      |
| Фреймворк         | `{framework}`     | `{ver}`  | {назначение}                      |
| ORM / Query Layer | `{orm}`           | `{ver}`  | {назначение}                      |
| База данных       | `{db}`            | `{ver}`  | {назначение}                      |
| Шаблонизатор      | `{template_eng}`  | `{ver}`  | {назначение}                      |

### 2.2 Инфраструктура

| Компонент          | Технология        | Назначение                        |
|--------------------|-------------------|-----------------------------------|
| Веб-сервер         | `{web_server}`    | {назначение}                      |
| ASGI-сервер        | `{asgi_server}`   | {назначение}                      |
| SSL/TLS            | `{ssl_tool}`      | {назначение}                      |
| Процесс-менеджер   | `{proc_manager}`  | {назначение}                      |
| CI/CD              | `{ci_cd}`         | {назначение}                      |

### 2.3 Внешние интеграции

| Сервис             | API / SDK         | Назначение                        |
|--------------------|-------------------|-----------------------------------|
| {service_name}     | `{api_or_sdk}`    | {назначение}                      |

---

## 3. Архитектура

### 3.1 Высокоуровневая схема

```
{ASCII-диаграмма или ссылка на draw.io / Mermaid-диаграмму}

Пример:
┌─────────┐    HTTPS    ┌─────────┐    proxy    ┌──────────┐
│ Browser  │ ──────────► │  Nginx  │ ──────────► │ Uvicorn  │
└─────────┘             └─────────┘             └──────────┘
                                                     │
                                                     ▼
                                              ┌──────────┐
                                              │ FastAPI   │
                                              │ (routes)  │
                                              └──────────┘
                                                     │
                                                     ▼
                                              ┌──────────┐
                                              │ PostgreSQL│
                                              └──────────┘
```

### 3.2 Структура каталогов

```
{project_root}/
├── app/
│   ├── main.py               # {описание}
│   ├── config.py             # {описание}
│   ├── models/               # {описание}
│   │   ├── __init__.py
│   │   ├── {model_a}.py
│   │   └── {model_b}.py
│   ├── routes/               # {описание}
│   │   ├── __init__.py
│   │   └── {route_module}.py
│   ├── services/             # {описание}
│   ├── repositories/         # {описание}
│   ├── schemas/              # {описание}
│   └── templates/            # {описание}
├── static/                   # {описание}
├── data/                     # {описание}
├── tests/                    # {описание}
├── docs/                     # {описание}
│   ├── adr/                  # Architecture Decision Records
│   └── changelog/            # DB и релизные changelog'и
├── .env                      # {описание}
├── requirements.txt
├── TECH_PASSPORT.md
├── README.md
└── DB_CHANGELOG.md
```

### 3.3 Модульная архитектура

| Модуль             | Файл(ы)                    | Ответственность                       |
|--------------------|-----------------------------|---------------------------------------|
| {module_name}      | `{file_path}`               | {что делает модуль}                   |

---

## 4. Доменная модель

### 4.1 Ключевые сущности

| Сущность           | Таблица БД         | Описание                               |
|--------------------|--------------------|-----------------------------------------|
| {entity_name}      | `{table_name}`     | {роль сущности в домене}                |

### 4.2 Связи между сущностями

```
{Текстовая ER-диаграмма или Mermaid}

Пример:
Person 1──* PersonRelationship *──1 Person
Person 1──* Union *──1 Person
Union  1──* PersonRelationship (child)
Memory 1──* Person (tagged)
```

### 4.3 Бизнес-правила

- **{rule_name}:** {описание правила, например: "Каждый Union связывает ровно двух Person с ролями partner_1 и partner_2"}
- **{rule_name}:** {описание}

---

## 5. Инфраструктура и деплой

### 5.1 Серверное окружение

| Параметр            | Значение                              |
|---------------------|---------------------------------------|
| Хостинг             | `{hosting_provider}`                  |
| ОС                  | `{os_version}`                        |
| IP / домен          | `{ip}` / `{domain}`                  |
| SSH доступ          | `{ssh_user}@{host} -p {port}`        |
| Путь к проекту      | `{server_project_path}`              |
| Путь к медиа        | `{media_path}`                        |

### 5.2 Процедура деплоя

```bash
# 1. Подключение к серверу
ssh {user}@{host}

# 2. Обновление кода
cd {project_path}
git pull origin main

# 3. Обновление зависимостей
source .venv/bin/activate
pip install -r requirements.txt

# 4. Применение миграций (если есть)
{migration_command}

# 5. Перезапуск сервиса
sudo systemctl restart {service_name}

# 6. Проверка
sudo systemctl status {service_name}
curl -s https://{domain}/health
```

### 5.3 Systemd Unit

```ini
# /etc/systemd/system/{service_name}.service
[Unit]
Description={project_name} FastAPI Application
After=network.target {db_service}.service

[Service]
User={run_user}
WorkingDirectory={project_path}
ExecStart={venv_path}/bin/uvicorn app.main:app --host {host} --port {port}
Restart=always
EnvironmentFile={env_path}

[Install]
WantedBy=multi-user.target
```

### 5.4 Nginx конфигурация

```nginx
# /etc/nginx/sites-available/{domain}
server {
    listen 443 ssl http2;
    server_name {domain};

    ssl_certificate     {cert_path};
    ssl_certificate_key {key_path};

    location / {
        proxy_pass http://127.0.0.1:{port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static/ {
        alias {static_path}/;
        expires 30d;
    }
}
```

---

## 6. Безопасность

| Аспект               | Решение                                |
|----------------------|----------------------------------------|
| Аутентификация       | {описание: PIN, JWT, OAuth и т.д.}     |
| Авторизация          | {описание ролевой модели}              |
| Шифрование данных    | {описание: at rest, in transit}        |
| Секреты              | {как хранятся: .env, Vault и т.д.}    |
| Бэкапы               | {стратегия: частота, хранение}         |

---

## 7. Текущий статус и Roadmap

### 7.1 Завершённые модули

- [x] {module_name} — {краткое описание, дата завершения}

### 7.2 В работе

- [ ] {task} — {ответственный}, ETA: {дата}

### 7.3 Backlog

| Приоритет | Задача                        | Описание                              |
|-----------|-------------------------------|---------------------------------------|
| P0        | {task_name}                   | {описание}                            |
| P1        | {task_name}                   | {описание}                            |
| P2        | {task_name}                   | {описание}                            |

---

## 8. Контакты и доступы

| Роль                 | Имя              | Контакт                   |
|----------------------|------------------|---------------------------|
| Архитектор / Owner   | {name}           | {email / tg}              |
| DevOps               | {name}           | {email / tg}              |
| Новый разработчик    | {name}           | {email / tg}              |

---

## 📎 Приложения

- [ADR Index](docs/adr/README.md)
- [DB Changelog](DB_CHANGELOG.md)
- [API Documentation](docs/api.md)

---

> **Конвенция обновления:** Этот документ обновляется при каждом значимом изменении архитектуры, инфраструктуры или стека. Версия в заголовке соответствует мажорной вехе проекта.
