# scripts/ops — Операционные скрипты TimeWoven

Реализация PROJECT_OPS_PROTOCOL.md.

## Содержимое

| Скрипт | Назначение |
|--------|------------|
| `clean_state_gate.sh` | Уровень 1. Проверяет, что репо/сервис чистые перед началом задания. |
| `safety_snapshot.sh`  | Уровень 2. Создаёт полный снапшот (incl. untracked) перед работой. |
| `rollback_to_snapshot.sh` | Откат к ранее созданному снапшоту. |

## Быстрый старт

```bash
cd "$(git rev-parse --show-toplevel)"

# 1. Перед стартом задания
bash scripts/ops/clean_state_gate.sh
bash scripts/ops/safety_snapshot.sh T-XXX-2026-04-27-01

# 2. Делаем задание...

# 3. После завершения (закрытие задания)
git add .
git commit -m "T-XXX: <описание>"
bash scripts/ops/clean_state_gate.sh   # должен снова отдать PASS

# 4. Если что-то пошло не так
bash scripts/ops/rollback_to_snapshot.sh T-XXX-2026-04-27-01
```

## Переменные окружения (опциональные)

| Переменная | По умолчанию | Назначение |
|------------|--------------|------------|
| `TW_PROJECT_DIR` | `$(git rev-parse --show-toplevel)` | Путь к проекту |
| `TW_SNAPSHOTS_ROOT` | `${TW_PROJECT_DIR}_snapshots` | Корень снапшотов |
| `TW_SERVICE` | `timewoven.service` | Имя systemd-сервиса |
| `TW_HEALTH_LOCAL` | `http://127.0.0.1:8000/health` | Локальный health |
| `TW_HEALTH_PUBLIC` | `https://app.timewoven.ru/health` | Публичный health |
| `TW_ENV_FILE` | `$TW_PROJECT_DIR/.env` | Файл с DATABASE_URL |
| `TW_SNAPSHOT_TTL_DAYS` | `30` | Срок хранения rolling-снапшотов |

## Хранилище снапшотов

```
${TW_PROJECT_DIR}_snapshots/
├── INDEX.log                      # Журнал всех снапшотов
├── T-XXX-2026-04-27-01/           # Rolling (TTL 30 дней)
│   ├── meta.txt
│   ├── worktree.tar.gz            # Включая untracked!
│   ├── repo.bundle
│   ├── db.sql.gz
│   ├── service.status
│   └── pip-freeze.txt
└── protected/                     # Без авто-удаления
    └── BASELINE-2026-04-27/
```

## Что важно знать

1. **`worktree.tar.gz` включает untracked файлы** — это главное отличие от git-stash и главная защита от инцидента 26.04.
2. **БД восстанавливается только по флагу `--with-db`** — по умолчанию rollback не трогает БД, чтобы не потерять данные пользователей, появившиеся после снапшота.
3. **`rollback_to_snapshot.sh` сначала делает свой собственный pre-rollback snapshot** — если откат пойдёт не так, всегда есть путь обратно.
4. **Снапшоты в `protected/` не удаляются автоматически** — туда складываются якорные состояния (раз в неделю, перед крупными изменениями).

## Установка

См. `INSTALL.md` в корне пакета.
