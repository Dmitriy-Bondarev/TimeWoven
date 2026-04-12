# TimeWoven

Семейное веб-приложение для хранения и передачи воспоминаний через поколения.

## Стек

- Python 3.9+
- FastAPI + Uvicorn
- SQLAlchemy + SQLite
- Jinja2
- python-multipart

## Структура проекта


## Установка и запуск

```bash
# Клонировать репозиторий
git clone git@github.com:Dmitriy-Bondarev/TimeWoven.git
cd TimeWoven

# Создать виртуальное окружение
python3 -m venv .venv
source .venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Восстановить БД из дампа
sqlite3 data/db/family.db < data/db/family.sql

# Запустить сервер
python -m uvicorn app.main:app --reload
```

Приложение доступно по адресу: http://127.0.0.1:8000

## Основные экраны

| URL | Описание |
|-----|----------|
| `/` | Импульс дня — случайная цитата с аудио |
| `/family/reply/{id}` | Ответ на послание |
| `/family/person/{id}` | Карточка человека |
| `/who-am-i` | Выбор участника |
| `/admin/people` | Контроль качества данных |
| `/admin/avatars` | Загрузка аватаров |

## Участники

9 человек семьи Бондаревых — 3 поколения.

## Roadmap

- [ ] PIN-авторизация
- [ ] Timeline событий
- [ ] Дерево семьи
- [ ] Уведомления в Telegram
- [ ] Whisper pipeline для транскрипции аудио
- [ ] Мобильная версия (PWA)
