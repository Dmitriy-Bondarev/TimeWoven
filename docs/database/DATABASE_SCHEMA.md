# 🗄 Технический паспорт базы данных TimeWoven

**Версия схемы:** 1.1 (актуально на 21.04.2026)  
**СУБД:** PostgreSQL  
**Синхронизировано с DDL:** ✅ Актуально

---

## 🧩 1. Ядро системы (Персоны и Родство)

### Таблица `People`
Центральный справочник всех участников древа.

| Столбец | Тип | Описание | Ограничения |
|---------|-----|----------|----------|
| `person_id` | serial4 | PK | NOT NULL |
| `maiden_name` | varchar | Девичья фамилия (для женщин) | |
| `gender` | varchar | M, F, Unknown | CHECK constraint |
| `birth_date` | varchar | Дата рождения | |
| `birth_date_prec` | varchar | Точность: EXACT, ABOUT, YEARONLY, DECADE | |
| `death_date` | varchar | Дата смерти | |
| `death_date_prec` | varchar | Точность: EXACT, ABOUT, YEARONLY, DECADE | |
| `is_alive` | int4 | 1/0 (по умолчанию 1) | NOT NULL |
| `is_user` | int4 | Доступ к системе (0/1, по умолчанию 0) | NOT NULL |
| `role` | varchar | Роль в системе (по умолчанию 'placeholder') | NOT NULL |
| `successor_id` | int4 | FK -> People(person_id) | |
| `default_lang` | varchar | Язык по умолчанию (по умолчанию 'ru') | NOT NULL |
| `phone` | varchar | Телефон | |
| `preferred_ch` | varchar | Канал общения: Max, TG, Email, Push, None | CHECK constraint |
| `messenger_max_id` | varchar | Идентификатор пользователя в Max Messenger (sender.user_id) | UNIQUE |
| `messenger_tg_id` | varchar | Идентификатор пользователя в Telegram | UNIQUE |
| `contact_email` | varchar | Email для связи | |
| `avatar_url` | varchar | URL аватара | |
| `pin` | varchar | PIN-код доступа | |
| `record_status` | varchar | Статус записи: active, archived, test_archived | NOT NULL, DEFAULT 'active', CHECK constraint |

### Таблица `People_I18n`
Локализация имен и биографий.

| Столбец | Тип | Описание | Ограничения |
|---------|-----|----------|----------|
| `person_id` | int4 | FK -> People | Composite PK |
| `lang_code` | varchar | Код языка | Composite PK |
| `first_name` | varchar | Имя на конкретном языке | NOT NULL |
| `last_name` | varchar | Фамилия на конкретном языке | |
| `patronymic` | varchar | Отчество (для кириллицы) | |
| `biography` | text | Биография на конкретном языке | |

---

## 🧬 2. Генеалогические связи

### Таблица `RelationshipType`
Типы отношений между персонами (справочник).

| Столбец | Тип | Описание |
|---------|-----|----------|
| `id` | serial4 | PK |
| `code` | varchar | Код типа (например, 'parent', 'sibling') | NOT NULL |
| `symmetry_type` | varchar | Тип симметрии отношения | NOT NULL |
| `category` | varchar | Категория (например, 'blood', 'legal') | NOT NULL |
| `inverse_type_id` | int4 | FK -> RelationshipType(id) для обратного типа | |

### Таблица `Unions`
Связка (брак, партнерство) между двумя людьми.

| Столбец | Тип | Описание |
|---------|-----|----------|
| `id` | serial4 | PK |
| `partner1_id` | int4 | FK -> People(person_id) |
| `partner2_id` | int4 | FK -> People(person_id) |
| `start_date` | varchar | Дата начала союза |
| `end_date` | varchar | Дата конца союза (развод/смерть) |

### Таблица `UnionChildren`
Связка родительской пары (Union) с детьми.

| Столбец | Тип | Описание |
|---------|-----|----------|
| `id` | serial4 | PK |
| `union_id` | int4 | FK -> Unions(id) |
| `child_id` | int4 | FK -> People(person_id) |

### Таблица `PersonRelationship`
Произвольные (не парные) связи между персонами.

| Столбец | Тип | Описание |
|---------|-----|----------|
| `rel_id` | serial4 | PK |
| `person_from_id` | int4 | FK -> People(person_id) | NOT NULL |
| `person_to_id` | int4 | FK -> People(person_id) | NOT NULL |
| `relationship_type_id` | int4 | FK -> RelationshipType(id) | NOT NULL |
| `is_primary` | int4 | Основное ли это отношение (по умолчанию 1) | NOT NULL |
| `valid_from` | varchar | Начало периода действия отношения | |
| `valid_to` | varchar | Конец периода действия отношения | |
| `comment` | varchar | Комментарий к отношению | |

---

## 🎙 3. Контент и Воспоминания

### Таблица `Memories`
Воспоминания, записи, истории от членов семьи.

| Столбец | Тип | Описание |
|---------|-----|----------|
| `id` | serial4 | PK |
| `author_id` | int4 | FK -> People (рассказчик) | |
| `event_id` | int4 | FK -> Events (связанное событие) | |
| `parent_memory_id` | int4 | FK -> Memories(id) для ответов/комментариев | |
| `content_text` | text | Текст воспоминания | |
| `audio_url` | varchar | Ссылка на аудиофайл | |
| `transcript_verbatim` | text | Дословная транскрипция | |
| `transcript_readable` | text | Читаемая версия транскрипции | |
| `emotional_tone` | varchar | Эмоциональный тон (positive, negative, neutral, mixed) | |
| `intimacy_level` | int4 | Уровень приватности (1-5, по умолчанию 1) | |
| `sensitivity_flag` | int4 | Флаг чувствительного контента (0/1, по умолчанию 0) | |
| `confidence_score` | float8 | Уверенность в транскрипции | |
| `created_at` | varchar | Дата/время создания | |
| `created_by` | int4 | FK -> People (кто создал запись) | |
| `source_type` | varchar | Источник (voice, text, imported) | |
| `transcription_status` | varchar | Статус: pending, published, archived, draft, pending_manual_text (по умолчанию 'pending') | |
| `is_archived` | bool | Архивный флаг записи (по умолчанию false) | NOT NULL |

### Таблица `MemoryPeople`
Связь воспоминания с участвующими в нем людьми.

| Столбец | Тип | Описание |
|---------|-----|----------|
| `memory_id` | int4 | FK -> Memories(id) | Composite PK |
| `person_id` | int4 | FK -> People(person_id) | Composite PK |
| `role` | varchar | Роль: author, mentioned, addressee, subject | Composite PK, CHECK constraint |

### Таблица `Quotes`
Избранные цитаты из Memories.

| Столбец | Тип | Описание |
|---------|-----|----------|
| `id` | serial4 | PK |
| `author_id` | int4 | FK -> People (автор цитаты) | NOT NULL |
| `content_text` | text | Текст цитаты | NOT NULL |
| `source_memory_id` | int4 | FK -> Memories(id) (исходное воспоминание) | |
| `created_at` | varchar | Дата создания цитаты | |

---

## 📍 4. География и События

### Таблица `Places`
Географические места (города, дома, памятные сайты).

| Столбец | Тип | Описание |
|---------|-----|----------|
| `place_id` | serial4 | PK |
| `country` | varchar | Страна | |
| `region` | varchar | Регион/область | |
| `city` | varchar | Город | |
| `coordinates` | varchar | GPS-координаты (широта,долгота) | |
| `address_raw` | varchar | Полный адрес | |
| `metadata` | text | Дополнительная информация (JSON) | |

### Таблица `Events`
Временная шкала событий в семейной истории.

| Столбец | Тип | Описание |
|---------|-----|----------|
| `event_id` | serial4 | PK |
| `author_id` | int4 | FK -> People (создатель события) | |
| `location_id` | int4 | FK -> Places (место события) | |
| `event_type` | varchar | Тип события (birth, death, wedding, etc.) | NOT NULL |
| `date_start` | varchar | Дата/время начала | |
| `date_start_prec` | varchar | Точность начальной даты | |
| `date_end` | varchar | Дата/время окончания | |
| `date_end_prec` | varchar | Точность конечной даты | |
| `is_private` | int4 | Приватное событие (0/1, по умолчанию 0) | |
| `cover_asset_id` | int4 | ID обложки события | |

### Таблица `EventParticipants`
Участники событий.

| Столбец | Тип | Описание |
|---------|-----|----------|
| `event_id` | int4 | FK -> Events(event_id) | Composite PK |
| `person_id` | int4 | FK -> People(person_id) | Composite PK |
| `participant_role` | varchar | Роль участника (главный герой, гость, и т.д.) | Composite PK |
| `is_featured` | int4 | Выделенный участник (0/1, по умолчанию 0) | |
| `added_at` | varchar | Дата добавления участника | |

---

## 🛠 5. Служебные таблицы

### Таблица `AvatarHistory`
История аватаров персон (фото по годам/периодам).

| Столбец | Тип | Описание |
|---------|-----|----------|
| `avatar_id` | serial4 | PK |
| `person_id` | int4 | FK -> People(person_id) | NOT NULL |
| `storage_path` | varchar | Путь до файла в хранилище | NOT NULL |
| `target_year` | int4 | Год, на который относится фото | |
| `is_current` | int4 | Текущий аватар (0/1, по умолчанию 0) | |
| `source_type` | varchar | Источник (upload, scan, external) | NOT NULL |
| `created_at` | varchar | Дата загрузки | |
| `metadata` | text | Дополнительные данные | |

### Таблица `MaxContactEvents`
Минимальный inbox для входящих contact attachments из Max без авто-создания людей.

| Столбец | Тип | Описание | Ограничения |
|---------|-----|----------|----------|
| `id` | serial4 | PK | NOT NULL |
| `created_at` | varchar | Время фиксации contact event | NOT NULL |
| `sender_max_user_id` | varchar | MAX user id отправителя | NOT NULL, INDEX |
| `contact_max_user_id` | varchar | MAX user id переданного контакта | INDEX |
| `contact_name` | varchar | Полное имя из `payload.max_info.name` | |
| `contact_first_name` | varchar | Имя из `payload.max_info.first_name` | |
| `contact_last_name` | varchar | Фамилия из `payload.max_info.last_name` | |
| `raw_payload` | text | Полный compact JSON входящего payload | NOT NULL |
| `matched_person_id` | int4 | FK -> People(person_id), nullable для будущего review/merge | FK |
| `status` | varchar | new, matched, merged, archived | NOT NULL, DEFAULT 'new', CHECK, INDEX |

---

## 📋 Справочные Таблицы

### Соглашения об именовании
- **PK** = Primary Key (первичный ключ)
- **FK** = Foreign Key (внешний ключ)
- **serial4** = Auto-increment 32-bit integer
- **varchar** = Переменная строка
- **text** = Текст без ограничения длины
- **int4** = 32-bit целое число
- **float8** = 64-bit число с плавающей точкой

### Стандартные CHECK Constraints
- `gender`: 'M', 'F', 'Unknown'
- `birth_date_prec`, `death_date_prec`: 'EXACT', 'ABOUT', 'YEARONLY', 'DECADE'
- `preferred_ch`: 'Max', 'TG', 'Email', 'Push', 'None'
- `record_status`: 'active', 'archived', 'test_archived'
- `MemoryPeople.role`: 'author', 'mentioned', 'addressee', 'subject'

---

## ⚙️ Инструкция для VS Code

**Этот файл является единственным источником истины (Single Source of Truth) для всех SQL-запросов и моделей SQLAlchemy.**

### 📌 Правила использования:
1. **Перед добавлением новой таблицы** — обнови этот файл ДО создания в БД
2. **Перед изменением структуры таблицы** — обнови этот файл ДО миграции
3. **При изменении схемы** — заполняй [DB_CHANGELOG.md](../DB_CHANGELOG.md) и увеличивай version
4. **При расхождении кода с этим файлом** — приоритет у этого файла
5. **Все модели SQLAlchemy** должны соответствовать определениям в этом файле
6. **При любом изменении SQLAlchemy-моделей** (поля, типы, связи, ограничения) — немедленно синхронизируй этот файл в той же рабочей сессии
7. **Изменения не считаются завершенными**, пока не подтверждено обновление релевантных журналов (`CHANGELOG.md`, `docs/PROJECT_LOG.md`, `DB_CHANGELOG.md` при schema/data патчах)

### 🔄 Синхронизация
Последняя проверка DDL: **21.04.2026**  
При наличии расхождений между кодом и PostgreSQL — БД содержит актуальную схему.
