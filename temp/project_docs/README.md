# 📦 Шаблоны документации — TimeWoven

Полный набор шаблонов для ведения проектной документации.
Каждый шаблон содержит структуру с плейсхолдерами `{...}` и сопровождается заполненным примером на основе реальных задач TimeWoven.

---

## Содержимое

| Шаблон                         | Пример                                   | Назначение                                    |
|--------------------------------|------------------------------------------|-----------------------------------------------|
| `TECH_PASSPORT.template.md`    | `examples/TECH_PASSPORT.example.md`      | Полный технический паспорт проекта             |
| `ADR.template.md`              | `examples/ADR-001.example.md`            | Architecture Decision Record                   |
| —                              | `examples/ADR-002.example.md`            | ADR: Temporal Normalization (пример #2)        |
| `README.template.md`           | `examples/README.example.md`             | README.md для корня репозитория                |
| `DB_CHANGELOG.template.md`     | `examples/DB_CHANGELOG.example.md`       | Журнал изменений базы данных                   |
| `requirements.template.txt`    | `examples/requirements.example.txt`      | Зависимости Python с группировкой и комментариями |
| `docs/adr/README.template.md`  | —                                        | Индекс ADR-документов                          |

---

## Быстрый старт

```bash
# 1. Скопировать шаблон в проект
cp TECH_PASSPORT.template.md ~/Projects/TimeWoven/TECH_PASSPORT.md

# 2. Заменить плейсхолдеры {..} на актуальные данные
# 3. Закоммитить
git add TECH_PASSPORT.md && git commit -m "docs: add tech passport v1.3"
```

---

## Структура каталогов в проекте

```
TimeWoven/
├── TECH_PASSPORT.md          # Технический паспорт (корень)
├── README.md                 # README проекта (корень)
├── DB_CHANGELOG.md           # Журнал БД (корень)
├── requirements.txt          # Зависимости (корень)
└── docs/
    └── adr/
        ├── README.md         # Индекс ADR
        ├── ADR-001.md        # Миграция SQLite → PostgreSQL
        ├── ADR-002.md        # Temporal Normalization
        └── ADR.template.md   # Шаблон для новых ADR
```

---

## Конвенции

- **Язык:** Русский (документация проекта), English для кода и комментариев в коде
- **Формат дат:** `YYYY-MM-DD`
- **Версионирование:** Семантическое (`v1.3-postgres`), в DB Changelog — `{major}.{minor}`
- **Коммиты:** `docs: {описание}` для документации
