#!/usr/bin/env bash
# rollback_to_snapshot.sh
# ────────────────────────────────────────────────────────────────────────────
# Назначение: откатить TimeWoven к ранее сохранённому safety-снапшоту.
#
# Поведение:
#   1) Создаёт новый safety_snapshot текущего состояния под именем
#      <TASK_ID>-PRE-ROLLBACK-<timestamp> (на случай, если откат пойдёт не так)
#   2) Останавливает timewoven.service
#   3) Восстанавливает рабочее дерево из worktree.tar.gz
#   4) (опционально, --with-git) восстанавливает .git из repo.bundle
#   5) (опционально, --with-db)  восстанавливает БД из db.sql.gz
#   6) Запускает timewoven.service
#   7) Проверяет /health
#
# Использование:
#   bash scripts/ops/rollback_to_snapshot.sh T-XXX-YYYY-MM-DD-NN
#   bash scripts/ops/rollback_to_snapshot.sh T-XXX-YYYY-MM-DD-NN --with-git
#   bash scripts/ops/rollback_to_snapshot.sh T-XXX-YYYY-MM-DD-NN --with-db
#   bash scripts/ops/rollback_to_snapshot.sh T-XXX-YYYY-MM-DD-NN --yes  (без интерактивного подтверждения)
#
# По умолчанию: восстанавливается ТОЛЬКО рабочее дерево.
# БД и git restore — только по явным флагам.
#
# См. PROJECT_OPS_PROTOCOL.md, секция 8.
# ────────────────────────────────────────────────────────────────────────────

set -u
set -o pipefail

# --- Время (portable ISO-8601) ---------------------------------------------
iso_now() {
  if date -Is >/dev/null 2>&1; then
    date -Is
  else
    date +"%Y-%m-%dT%H:%M:%S%z"
  fi
}

# --- Конфигурация ----------------------------------------------------------
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
PROJECT_DIR="${TW_PROJECT_DIR:-$PROJECT_ROOT}"
SNAPSHOTS_ROOT="${TW_SNAPSHOTS_ROOT:-${PROJECT_DIR}_snapshots}"
ENV_FILE="${TW_ENV_FILE:-$PROJECT_DIR/.env}"
SERVICE_NAME="${TW_SERVICE:-timewoven.service}"
HEALTH_LOCAL="${TW_HEALTH_LOCAL:-http://127.0.0.1:8000/health}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Аргументы -------------------------------------------------------------
TASK_ID="${1:-}"
WITH_GIT=0
WITH_DB=0
ASSUME_YES=0
shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-git) WITH_GIT=1 ;;
    --with-db)  WITH_DB=1 ;;
    --yes|-y)   ASSUME_YES=1 ;;
    *) echo "Unknown flag: $1"; exit 2 ;;
  esac
  shift
done

if [[ -z "$TASK_ID" ]]; then
  echo "Usage: $0 T-XXX-YYYY-MM-DD-NN [--with-git] [--with-db] [--yes]" >&2
  echo "" >&2
  echo "Доступные снапшоты:" >&2
  if [[ -f "$SNAPSHOTS_ROOT/INDEX.log" ]]; then
    cat "$SNAPSHOTS_ROOT/INDEX.log" >&2
  else
    echo "  (журнал INDEX.log не найден)" >&2
  fi
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

# --- 0. Проект на месте -----------------------------------------------------
if [[ -z "$PROJECT_DIR" ]]; then
  err "Не удалось определить корень git-репозитория (git rev-parse --show-toplevel)"
  exit 1
fi

# --- Поиск снапшота --------------------------------------------------------
SNAP_DIR=""
for cand in "$SNAPSHOTS_ROOT/$TASK_ID" "$SNAPSHOTS_ROOT/protected/$TASK_ID"; do
  if [[ -d "$cand" ]]; then
    SNAP_DIR="$cand"
    break
  fi
done

if [[ -z "$SNAP_DIR" ]]; then
  err "Снапшот не найден: $TASK_ID"
  echo "Искали в:"
  echo "  $SNAPSHOTS_ROOT/$TASK_ID"
  echo "  $SNAPSHOTS_ROOT/protected/$TASK_ID"
  exit 1
fi

if [[ ! -f "$SNAP_DIR/worktree.tar.gz" ]]; then
  err "В снапшоте нет worktree.tar.gz: $SNAP_DIR"
  exit 1
fi

# --- Шапка / подтверждение -------------------------------------------------
echo "${C_BLD}╔══════════════════════════════════════════════════════════════╗${C_RST}"
echo "${C_BLD}║  ROLLBACK TO SNAPSHOT — TimeWoven                            ║${C_RST}"
echo "${C_BLD}║  Task:        $TASK_ID${C_RST}"
echo "${C_BLD}║  Snapshot:    $SNAP_DIR${C_RST}"
echo "${C_BLD}║  Project:     $PROJECT_DIR${C_RST}"
echo "${C_BLD}║  With git:    $([[ $WITH_GIT -eq 1 ]] && echo YES || echo no)${C_RST}"
echo "${C_BLD}║  With DB:     $([[ $WITH_DB  -eq 1 ]] && echo YES || echo no)${C_RST}"
echo "${C_BLD}║  Time:        $(iso_now)${C_RST}"
echo "${C_BLD}╚══════════════════════════════════════════════════════════════╝${C_RST}"
echo ""

if [[ -f "$SNAP_DIR/meta.txt" ]]; then
  echo "${C_BLD}── Метаданные снапшота ──────────────────────────────────────${C_RST}"
  head -15 "$SNAP_DIR/meta.txt" | sed 's/^/  /'
  echo "${C_BLD}─────────────────────────────────────────────────────────────${C_RST}"
  echo ""
fi

if [[ $ASSUME_YES -eq 0 ]]; then
  echo "${C_YLW}ВНИМАНИЕ:${C_RST} это перезапишет содержимое $PROJECT_DIR"
  if [[ $WITH_DB -eq 1 ]]; then
    echo "${C_RED}${C_BLD}+ восстановление БД${C_RST} — все данные после снапшота будут ПОТЕРЯНЫ"
  fi
  read -r -p "Продолжить? (yes/no): " CONFIRM
  if [[ "$CONFIRM" != "yes" ]]; then
    echo "Отменено."
    exit 1
  fi
fi

# --- Шаг 1. Pre-rollback safety snapshot -----------------------------------
PRE_ID="${TASK_ID}-PRE-ROLLBACK-$(date +%Y%m%d-%H%M%S)"
log "Создаю pre-rollback snapshot: $PRE_ID..."
if [[ -x "$SCRIPT_DIR/safety_snapshot.sh" ]]; then
  if "$SCRIPT_DIR/safety_snapshot.sh" "$PRE_ID" --no-db >/dev/null 2>&1; then
    ok "pre-rollback snapshot готов: $SNAPSHOTS_ROOT/$PRE_ID"
  else
    warn "pre-rollback snapshot не удался (продолжаем по флагу --yes)"
    if [[ $ASSUME_YES -eq 0 ]]; then
      read -r -p "Продолжить откат БЕЗ pre-rollback snapshot? (yes/no): " CONFIRM
      [[ "$CONFIRM" == "yes" ]] || exit 1
    fi
  fi
else
  warn "safety_snapshot.sh не найден рядом — pre-rollback пропущен"
fi

# --- Шаг 2. Stop service ---------------------------------------------------
log "Останавливаю $SERVICE_NAME..."
if command -v systemctl >/dev/null 2>&1; then
  if systemctl stop "$SERVICE_NAME" 2>/dev/null; then
    ok "$SERVICE_NAME остановлен"
  else
    warn "Не удалось остановить $SERVICE_NAME (возможно, уже не работает)"
  fi
else
  warn "[SKIP] systemctl check (not available)"
fi

# --- Шаг 3. Restore worktree -----------------------------------------------
log "Восстанавливаю рабочее дерево из worktree.tar.gz..."

# Сохраняем .git отдельно, если не --with-git
if [[ $WITH_GIT -eq 0 ]] && [[ -d "$PROJECT_DIR/.git" ]]; then
  GIT_BACKUP="/tmp/.git.backup.$$.$(date +%s)"
  log "Временно сохраняю текущий .git в $GIT_BACKUP"
  mv "$PROJECT_DIR/.git" "$GIT_BACKUP"
fi

# Чистим рабочее дерево (но сохраняем venv и backups)
log "Очищаю рабочее дерево (venv/backups сохраняются)..."
find "$PROJECT_DIR" -mindepth 1 -maxdepth 1 \
  -not -name 'venv' -not -name '.venv' \
  -not -name 'backups' \
  -not -name '.git' \
  -exec rm -rf {} + 2>/dev/null || true

if tar -xzf "$SNAP_DIR/worktree.tar.gz" -C "$PROJECT_DIR"; then
  ok "Рабочее дерево восстановлено"
else
  err "tar extract упал"
  # Возвращаем .git, если откладывали
  if [[ -n "${GIT_BACKUP:-}" ]] && [[ -d "$GIT_BACKUP" ]]; then
    mv "$GIT_BACKUP" "$PROJECT_DIR/.git"
  fi
  exit 1
fi

# Возвращаем .git
if [[ -n "${GIT_BACKUP:-}" ]] && [[ -d "$GIT_BACKUP" ]]; then
  rm -rf "$PROJECT_DIR/.git"
  mv "$GIT_BACKUP" "$PROJECT_DIR/.git"
  ok "Текущий .git сохранён без изменений"
fi

# --- Шаг 4. (опц.) Restore git --------------------------------------------
if [[ $WITH_GIT -eq 1 ]]; then
  if [[ -f "$SNAP_DIR/repo.bundle" ]]; then
    log "Восстанавливаю git из repo.bundle..."
    TMP_REPO="/tmp/tw-repo-restore.$$"
    if git clone --mirror "$SNAP_DIR/repo.bundle" "$TMP_REPO" >/dev/null 2>&1; then
      rm -rf "$PROJECT_DIR/.git"
      mkdir -p "$PROJECT_DIR/.git"
      cp -a "$TMP_REPO/." "$PROJECT_DIR/.git/"
      # Превращаем bare в обычный
      git -C "$PROJECT_DIR" config --bool core.bare false
      git -C "$PROJECT_DIR" reset --hard 2>/dev/null || true
      rm -rf "$TMP_REPO"
      ok "git восстановлен из bundle"
    else
      err "git clone из bundle не удался"
    fi
  else
    warn "repo.bundle отсутствует в снапшоте — пропускаем git restore"
  fi
fi

# --- Шаг 5. (опц.) Restore DB ----------------------------------------------
if [[ $WITH_DB -eq 1 ]]; then
  if [[ -f "$SNAP_DIR/db.sql.gz" ]] && [[ -f "$ENV_FILE" ]]; then
    log "Восстанавливаю БД из db.sql.gz..."
    DB_URL="$(grep -E '^DATABASE_URL=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
    if [[ -n "$DB_URL" ]] && command -v psql >/dev/null 2>&1; then
      # Безопасный подход: НЕ дропаем БД, восстанавливаем поверх как pg_restore-like
      if gunzip -c "$SNAP_DIR/db.sql.gz" | psql "$DB_URL" >/tmp/db-restore.log 2>&1; then
        ok "БД восстановлена (см. /tmp/db-restore.log)"
      else
        err "psql restore упал. Лог: /tmp/db-restore.log"
      fi
    else
      err "DATABASE_URL или psql недоступны"
    fi
  else
    warn "db.sql.gz или .env отсутствуют — пропускаем DB restore"
  fi
fi

# --- Шаг 6. Start service --------------------------------------------------
log "Запускаю $SERVICE_NAME..."
if command -v systemctl >/dev/null 2>&1; then
  if systemctl start "$SERVICE_NAME"; then
    ok "$SERVICE_NAME запускается..."
  else
    err "Не удалось запустить $SERVICE_NAME"
  fi
else
  warn "[SKIP] systemctl check (not available)"
fi

sleep 3

# --- Шаг 7. Health check ---------------------------------------------------
log "Проверяю /health..."
HEALTH="$(curl -sS --max-time 5 "$HEALTH_LOCAL" 2>/dev/null || true)"
if echo "$HEALTH" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
  ok "Local /health = ok"
else
  err "Local /health не отвечает или не ok (got: ${HEALTH:0:100})"
  warn "Посмотрите: journalctl -u $SERVICE_NAME -n 80 --no-pager"
fi

# --- Итог ------------------------------------------------------------------
echo ""
echo "${C_GRN}${C_BLD}✓ Откат завершён${C_RST}"
echo "  Восстановлен снапшот: $TASK_ID"
echo "  Pre-rollback snapshot: $SNAPSHOTS_ROOT/$PRE_ID"
echo ""
echo "Дальнейшие шаги:"
echo "  1) Проверить bash scripts/ops/clean_state_gate.sh"
echo "  2) Зафиксировать факт отката в PROJECT_LOG.md (T-ROLLBACK-...)"
echo "  3) Если откат не помог — pre-rollback snapshot выше позволит вернуться"
echo ""
exit 0
