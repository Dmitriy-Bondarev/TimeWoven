# 📋 Индекс архитектурных решений (ADR)

> Этот файл содержит реестр всех Architecture Decision Records проекта **TimeWoven**.

| ADR   | Заголовок                                      | Статус   | Дата       | Теги                               |
|-------|------------------------------------------------|----------|------------|------------------------------------|
| 001   | Миграция с SQLite на PostgreSQL                | Accepted | 2026-04-16 | `database` `infrastructure` `migration` |
| 002   | Temporal Normalization для PersonRelationship  | Accepted | 2026-04-17 | `database` `domain-model` `temporal`    |

---

### Статусы

- **Proposed** — решение предложено, ещё не принято  
- **Accepted** — решение принято и действует  
- **Deprecated** — решение устарело и больше не актуально  
- **Superseded** — решение заменено более новым ADR

### Как добавить новый ADR

1. Скопировать `ADR.template.md` → `ADR-{NNN}.md`  
2. Заполнить все секции  
3. Добавить запись в эту таблицу  
4. Закоммитить с сообщением: `docs: add ADR-{NNN} — {краткое описание}`