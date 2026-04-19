# CHANGELOG — TimeWoven

## [v1.3-postgres] — 2026-04-19

### Инфраструктура и БД

- PostgreSQL 14 установлен и настроен на сервере Hostkey VPS. [cite:21]  
- Создана база `timewoven`, пользователь `timewoven_user` с доступом к БД. [cite:21]  
- Схема 13+ таблиц развёрнута в PostgreSQL, данные перенесены из SQLite.  
- Резервные копии схемы/данных зафиксированы в `/backups/2026-04-17/`. [cite:29]  
- `DATABASE_URL` перенесён в `.env`, загрузка через `load_dotenv` до инициализации приложения. [cite:29]

### Перенос данных в PostgreSQL (состояние на 2026‑04‑17)

- People: 9, People_I18n: 18, Events: 6  
- Memories: 3 → впоследствии дополнены до 9 (фактический count на 2026‑04‑19). [cite:29]  
- MemoryPeople: 16, Quotes: 3  
- AvatarHistory: 4, RelationshipType: 12  
- PersonRelationship: 26, Unions: 2, UnionChildren: 5

### Нормализация временной модели (PersonRelationship)

- Убраны `NULL` из `valid_to` для связей: открытые интервалы приведены к `9999-12-31`. [cite:31]  
- Для `bioparent` (`relationship_type_id = 1`) и `child` (`relationship_type_id = 2`) `valid_from` заполнен из даты рождения ребёнка (`People.birth_date`). [cite:31]  
- Для `bioparent`/`child` `valid_to` зафиксирован как `9999-12-31` (родство не обрезается по смерти). [cite:31]  
- Для `spouselegal` (`relationship_type_id = 3`) `valid_to` обрезан по дате смерти одного из супругов (если есть `People.death_date`), с учётом кастов `::date`. [cite:31]  
- Таблица `Unions` зафиксирована как источник дат начала/окончания браков (`start_date`/`end_date`); полная синхронизация `valid_from`/`valid_to` с `Unions` запланирована в следующей версии. [cite:31]

### Веб-инфраструктура и HTTPS

- Подняты HTTPS‑сертификаты Let’s Encrypt для доменов: `timewoven.ru`, `www.timewoven.ru`, `app.timewoven.ru`. [cite:22][cite:29]  
- Настроен единый Nginx‑конфиг:
  - HTTP → HTTPS редиректы для всех доменов.
  - `timewoven.ru` / `www.timewoven.ru` → статический лендинг (`/var/www/timewoven`). [cite:29]
  - `app.timewoven.ru` → `proxy_pass http://127.0.0.1:8000` (Uvicorn). [cite:29]
- Добавлены `X-Forwarded-Proto`, `X-Real-IP`, `X-Forwarded-For`, `Host` в proxy headers. [cite:29]

### Приложение: FastAPI / маршруты / фронтенд

- `app/main.py`:
  - Загрузка `.env` через `python-dotenv` перенесена до импорта роутеров и подключения к БД. [cite:29]
  - Инициализированы `Jinja2Templates` и подключены web‑шаблоны из `app/web/templates`. [cite:29]
- Корневой маршрут `/`:
  - Переведён с JSON‑заглушки на `TemplateResponse("family/home.html", ...)`. [cite:29]
  - Теперь выбирает последнюю `Memory` с непустым `author_id` и текстом, подтягивает `Person`, `PersonI18n` и `avatar_url`. [cite:29]
- Маршруты семьи и дерева (`app/api/routes/tree.py`): [cite:29]
  - `GET /` — импульс дня с реальным человеком из БД.
  - `GET /family/person/{person_id}` — карточка человека (`profile.html`).
  - `GET /family/tree?root_person_id=1&depth=2` — интерактивный граф семьи.
  - `GET /family/timeline` — таймлайн (воспоминания + события).
  - `GET /who-am-i` / `POST /who-am-i` — выбор пользователя и redirect на PIN‑форму.
  - `GET /who-am-i/pin` / `POST /who-am-i/pin` — PIN‑верификация и redirect на `next?person_id=...`.
  - `GET /family/reply/{memory_id}` / `POST /family/reply/{memory_id}` — просмотр и сохранение ответов семьи (`Quotes`).
- Админ-маршруты (`app/api/routes/admin.py`): [cite:29]
  - `GET /admin` → redirect на `/admin/transcriptions`.
  - `GET /admin/transcriptions` — список транскрипций с именами/аватарами.
  - `POST /admin/transcriptions/{id}/publish` — публикация транскрипции.
  - `GET /admin/people` — список людей (исправлен путь, был `/admin/admin/people`).
  - `GET /admin/login` / `POST /admin/login` — форма входа и временный login‑flow.
  - `GET /admin/avatars` — форма для загрузки аватаров.
- Legacy‑роутер `family_tree.py` убран из подключения в `main.py`, но оставлен в проекте как рез