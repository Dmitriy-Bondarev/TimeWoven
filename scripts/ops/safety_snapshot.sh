#!/usr/bin/env bash
# safety_snapshot.sh
# ────────────────────────────────────────────────────────────────────────────
# Назначение: создать ПОЛНЫЙ снапшот текущего состояния TimeWoven
# перед началом задания. В отличие от git/stash, сохраняет
# untracked-файлы тоже — это главная защита от инцидента 26.04.
#
# Снапшот содержит:
#   - worktree.tar.gz — всё рабочее дерево (incl. untracked)
#   - repo.bundle     — git bundle всех веток и тегов
#   - db.sql.gz       — pg_dump целевой БД
#   - service.status  — статус timewoven сервисов
#   - pip-freeze.txt  — состав python-окружения
#   - meta.txt        — git HEAD, branch, дата, hostname
#
# Использование:
#   bash scripts/ops/safety_snapshot.sh T-XXX-YYYY-MM-DD-NN
#   bash scripts/ops/safety_snapshot.sh T-XXX-YYYY-MM-DD-NN --protected
#   bash scripts/ops/safety_snapshot.sh T-XXX-YYYY-MM-DD-NN --no-db
#
# Флаги:
#   --protected   — сохранить в protected/ (без авто-удаления)
#   --no-db       — пропустить pg_dump (быстрее, без записи данных пользователей)
#
# Хранение: rolling 30 дней в основном каталоге. protected/ — навсегда.
#
# См. PROJECT_OPS_PROTOCOL.md, секция 4.
# ────────────────────────────────────────────────────────────────────────────

set -u
set -o pipefail

# --- Конфигурация ----------------------------------------------------------
PROJECT_DIR="${TW_PROJECT_DIR:-/root/projects/TimeWoven}"
SNAPSHOTS_ROOT="${TW_SNAPSHOTS_ROOT:-/root/projects/TimeWoven_snapshots}"
ENV_FILE="${TW_ENV_FILE:-$PROJECT_DIR/.env}"
ROLLING_DAYS="${TW_SNAPSHOT_TTL_DAYS:-30}"
SERVICES=( "${TW_SERVICE:-timewoven.service}" "timewoven-llm.service" "timewoven-whisper.service" )

# --- Аргументы -------------------------------------------------------------
TASK_ID="${1:-}"
PROTECTED=0
DUMP_DB=1
shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --protected) PROTECTED=1 ;;
    --no-db)     DUMP_DB=0 ;;
    *) echo "Unknown flag: $1"; exit 2 ;;
  esac
  shift
done

if [[ -z "$TASK_ID" ]]; then
  echo "Usage: $0 T-XXX-YYYY-MM-DD-NN [--protected] [--no-db]" >&2
  exit 2
fi

# Валидация TASK_ID
if [[ ! "$TASK_ID" =~ ^[A-Z][A-Z0-9_-]+$ ]]; then
  echo "Invalid TASK_ID: '$TASK_ID' (ожидался шаблон вида T-XXX-2026-04-27-01)" >&2
  exit 2
fi

# --- Цвета -----------------------------------------------------------------
if [[ -t 1 ]]; then
  C_RED=$'\e[31m'; C_GRN=$'\e[32m'; C_YLW=$'\e[33m'; C_DIM=$'\e[2m'; C_RST=$'\e[0m'; C_BLD=$'\e[1m'
else
  C_RED=""; C_GRN=""; C_YLW=""; C_DIM=""; C_RST=""; C_BLD=""
fi

log()  { echo "${C_DIM}[$(date +%H:%M:%S)]${C_RST} $*"; }
ok()   { echo "${C_GRN}[ OK ]${C_RST} $*"; }
warn() { echo "${C_YLW}[WARN]${C_RST} $*"; }
err()  { echo "${C_RED}[FAIL]${C_RST} $*"; }

# --- Подготовка пути снапшота ----------------------------------------------
if [[ ! -d "$PROJECT_DIR/.git" ]]; then
  err "Не найден git-репозиторий в $PROJECT_DIR"; exit 1
fi

if [[ $PROTECTED -eq 1 ]]; then
  SNAP_DIR="$SNAPSHOTS_ROOT/protected/$TASK_ID"
else
  SNAP_DIR="$SNAPSHOTS_ROOT/$TASK_ID"
fi

if [[ -e "$SNAP_DIR" ]]; then
  err "Снапшот с таким TASK_ID уже существует: $SNAP_DIR"
  err "Удалите вручную или используйте другой TASK_ID."
  exit 1
fi

mkdir -p "$SNAP_DIR"
chmod 700 "$SNAPSHOTS_ROOT"
chmod 700 "$SNAP_DIR"

echo "${C_BLD}╔══════════════════════════════════════════════════════════════╗${C_RST}"
echo "${C_BLD}║  SAFETY SNAPSHOT — TimeWoven                                 ║${C_RST}"
echo "${C_BLD}║  Task:     $TASK_ID${C_RST}"
echo "${C_BLD}║  Target:   $SNAP_DIR${C_RST}"
echo "${C_BLD}║  Mode:     $([[ $PROTECTED -eq 1 ]] && echo PROTECTED || echo rolling)${C_RST}"
echo "${C_BLD}║  Time:     $(date -Is)${C_RST}"
echo "${C_BLD}╚══════════════════════════════════════════════════════════════╝${C_RST}"
echo ""

cd "$PROJECT_DIR"

# --- 1. meta.txt ------------------------------------------------------------
log "Сохраняю meta..."
{
  echo "task_id=$TASK_ID"
  echo "timestamp=$(date -Is)"
  echo "hostname=$(hostname)"
  echo "project_dir=$PROJECT_DIR"
  echo "git_branch=$(git branch --show-current 2>/dev/null || echo detached)"
  echo "git_head=$(git rev-parse HEAD 2>/dev/null || echo none)"
  echo "git_head_short=$(git rev-parse --short HEAD 2>/dev/null || echo none)"
  echo "git_status_lines=$(git status --porcelain | wc -l)"
  echo "git_stash_count=$(git stash list | wc -l)"
  echo "snapshot_mode=$([[ $PROTECTED -eq 1 ]] && echo protected || echo rolling)"
  echo "dump_db=$DUMP_DB"
  echo ""
  echo "# --- git status --porcelain ---"
  git status --porcelain
  echo ""
  echo "# --- git stash list ---"
  git stash list
  echo ""
  echo "# --- last 10 commits ---"
  git log --oneline -10
} > "$SNAP_DIR/meta.txt"
ok "meta.txt"

# --- 2. worktree.tar.gz (включая untracked) ---------------------------------
log "Архивирую рабочее дерево (включая untracked)..."
TAR_EXCLUDES=(
  --exclude='./venv'
  --exclude='./.venv'
  --exclude='./.git'
  --exclude='./node_modules'
  --exclude='./__pycache__'
  --exclude='*.pyc'
  --exclude='./backups'
  --exclude='./data/raw'
  --exclude='./app/web/static/audio/raw'
  --exclude='./app/web/static/audio/processed'
  --exclude='./app/web/static/audio/uploads'
  --exclude='./app/web/static/images/uploads'
)
if tar "${TAR_EXCLUDES[@]}" -czf "$SNAP_DIR/worktree.tar.gz" -C "$PROJECT_DIR" . 2>"$SNAP_DIR/worktree.tar.errors"; then
  WT_SIZE="$(du -h "$SNAP_DIR/worktree.tar.gz" | awk '{print $1}')"
  WT_FILES="$(tar -tzf "$SNAP_DIR/worktree.tar.gz" | wc -l)"
  ok "worktree.tar.gz (size=$WT_SIZE, files=$WT_FILES)"
  rm -f "$SNAP_DIR/worktree.tar.errors"
else
  err "Не удалось создать worktree.tar.gz (см. worktree.tar.errors)"
  exit 1
fi

# --- 3. repo.bundle ---------------------------------------------------------
log "Создаю git bundle..."
if git bundle create "$SNAP_DIR/repo.bundle" --all 2>"$SNAP_DIR/repo.bundle.errors"; then
  RB_SIZE="$(du -h "$SNAP_DIR/repo.bundle" | awk '{print $1}')"
  ok "repo.bundle (size=$RB_SIZE)"
  rm -f "$SNAP_DIR/repo.bundle.errors"
else
  warn "git bundle не удался (см. repo.bundle.errors). Worktree всё равно сохранён."
fi

# --- 4. db.sql.gz -----------------------------------------------------------
if [[ $DUMP_DB -eq 1 ]]; then
  log "Дамплю БД..."
  DB_URL=""
  if [[ -f "$ENV_FILE" ]]; then
    DB_URL="$(grep -E '^DATABASE_URL=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
  fi
  if [[ -n "$DB_URL" ]] && command -v pg_dump >/dev/null 2>&1; then
    if pg_dump "$DB_URL" 2>"$SNAP_DIR/db.sql.errors" | gzip > "$SNAP_DIR/db.sql.gz"; then
      DB_SIZE="$(du -h "$SNAP_DIR/db.sql.gz" | awk '{print $1}')"
      ok "db.sql.gz (size=$DB_SIZE)"
      rm -f "$SNAP_DIR/db.sql.errors"
    else
      err "pg_dump упал (см. db.sql.errors)"
      rm -f "$SNAP_DIR/db.sql.gz"
    fi
  else
    warn "DATABASE_URL не найден или pg_dump недоступен — БД не сохранена"
  fi
else
  warn "флаг --no-db: БД пропущена"
fi

# --- 5. service.status ------------------------------------------------------
log "Снимаю статус сервисов..."
{
  for svc in "${SERVICES[@]}"; do
    echo "=== $svc ==="
    systemctl status "$svc" --no-pager -l 2>/dev/null || echo "(сервис не найден)"
    echo ""
  done
} > "$SNAP_DIR/service.status" 2>/dev/null || true
ok "service.status"

# --- 6. pip-freeze.txt ------------------------------------------------------
VENV_BIN=""
if   [[ -x "$PROJECT_DIR/venv/bin/pip" ]]; then VENV_BIN="$PROJECT_DIR/venv/bin/pip"
elif [[ -x "$PROJECT_DIR/.venv/bin/pip" ]]; then VENV_BIN="$PROJECT_DIR/.venv/bin/pip"
fi
if [[ -n "$VENV_BIN" ]]; then
  "$VENV_BIN" freeze > "$SNAP_DIR/pip-freeze.txt" 2>/dev/null && ok "pip-freeze.txt" || warn "pip freeze не удался"
else
  warn "venv не найден — pip-freeze пропущен"
fi

# --- 7. INDEX.log -----------------------------------------------------------
HEAD_HASH="$(git rev-parse HEAD 2>/dev/null || echo none)"
INDEX_FILE="$SNAPSHOTS_ROOT/INDEX.log"
echo "$TASK_ID	$HEAD_HASH	$(date -Is)	$([[ $PROTECTED -eq 1 ]] && echo protected || echo rolling)	$SNAP_DIR" >> "$INDEX_FILE"
chmod 600 "$INDEX_FILE"
ok "INDEX.log обновлён"

# --- 8. Авто-уборка старых rolling-снапшотов --------------------------------
if [[ $PROTECTED -eq 0 ]]; then
  log "Уборка снапшотов старше $ROLLING_DAYS дней..."
  DELETED=0
  if [[ -d "$SNAPSHOTS_ROOT" ]]; then
    while IFS= read -r -d '' old; do
      # Не трогаем protected/, INDEX.log и текущий снапшот
      case "$old" in
        "$SNAPSHOTS_ROOT/protected"*) continue ;;
        "$SNAPSHOTS_ROOT/INDEX.log") continue ;;
        "$SNAP_DIR") continue ;;
      esac
      if [[ -d "$old" ]]; then
        rm -rf "$old"
        DELETED=$((DELETED+1))
      fi
    done < <(find "$SNAPSHOTS_ROOT" -maxdepth 1 -mindepth 1 -type d -mtime "+$ROLLING_DAYS" -print0 2>/dev/null)
  fi
  if [[ $DELETED -gt 0 ]]; then
    ok "Удалено старых снапшотов: $DELETED"
  else
    log "Старых снапшотов нет"
  fi
fi

# --- Итог -------------------------------------------------------------------
chmod -R go-rwx "$SNAP_DIR"
TOTAL_SIZE="$(du -sh "$SNAP_DIR" | awk '{print $1}')"
echo ""
echo "${C_GRN}${C_BLD}✓ Snapshot создан${C_RST}"
echo "  Path:  $SNAP_DIR"
echo "  Size:  $TOTAL_SIZE"
echo "  Mode:  $([[ $PROTECTED -eq 1 ]] && echo PROTECTED || echo "rolling (TTL=$ROLLING_DAYS дней)")"
echo ""
echo "Откат при необходимости:"
echo "  bash scripts/ops/rollback_to_snapshot.sh $TASK_ID"
echo ""
exit 0
