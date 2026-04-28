#!/usr/bin/env bash
# clean_state_gate.sh
# ────────────────────────────────────────────────────────────────────────────
# Назначение: проверить, что система TimeWoven находится в "чистом" состоянии,
# в котором безопасно начинать новое задание.
#
# Возвращает exit code:
#   0  — PASS, можно стартовать
#   1  — FAIL, есть незакрытые долги (см. отчёт)
#
# Использование:
#   bash scripts/ops/clean_state_gate.sh
#   bash scripts/ops/clean_state_gate.sh --quiet   # без цветов, только итог
#
# См. PROJECT_OPS_PROTOCOL.md, секция 3.
# ────────────────────────────────────────────────────────────────────────────

set -u

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
HEALTH_URL_LOCAL="${TW_HEALTH_LOCAL:-http://127.0.0.1:8000/health}"
# PUBLIC health:
# - on server (systemctl available) default to app.timewoven.ru
# - on local (no systemctl) skip unless TW_HEALTH_PUBLIC set explicitly
if [[ -n "${TW_HEALTH_PUBLIC:-}" ]]; then
  HEALTH_URL_PUBLIC="$TW_HEALTH_PUBLIC"
else
  if command -v systemctl >/dev/null 2>&1; then
    HEALTH_URL_PUBLIC="https://app.timewoven.ru/health"
  else
    HEALTH_URL_PUBLIC=""
  fi
fi
SERVICE_NAME="${TW_SERVICE:-timewoven.service}"
EXPECTED_BRANCH_PATTERN='^(main|T-[A-Z0-9._-]+)$'

# --- Цвета (отключаются при --quiet) ---------------------------------------
QUIET=0
if [[ "${1:-}" == "--quiet" ]]; then
  QUIET=1
fi

if [[ -t 1 ]] && [[ $QUIET -eq 0 ]]; then
  C_RED=$'\e[31m'; C_GRN=$'\e[32m'; C_YLW=$'\e[33m'; C_DIM=$'\e[2m'; C_RST=$'\e[0m'; C_BLD=$'\e[1m'
else
  C_RED=""; C_GRN=""; C_YLW=""; C_DIM=""; C_RST=""; C_BLD=""
fi

# --- Состояние --------------------------------------------------------------
FAILS=0
WARNINGS=0
REPORT=()

pass()  { REPORT+=("${C_GRN}[PASS]${C_RST} $*"); }
warn()  { REPORT+=("${C_YLW}[WARN]${C_RST} $*"); WARNINGS=$((WARNINGS+1)); }
fail()  { REPORT+=("${C_RED}[FAIL]${C_RST} $*"); FAILS=$((FAILS+1)); }
skip()  { REPORT+=("${C_DIM}[SKIP]${C_RST} $*"); }

# --- 0. Проект на месте -----------------------------------------------------
if [[ -z "$PROJECT_DIR" ]]; then
  echo "${C_RED}[FATAL]${C_RST} Не удалось определить корень git-репозитория (git rev-parse --show-toplevel)"
  exit 1
fi
if [[ ! -d "$PROJECT_DIR/.git" ]]; then
  echo "${C_RED}[FATAL]${C_RST} Не найден git-репозиторий в $PROJECT_DIR"
  exit 1
fi
cd "$PROJECT_DIR"

echo "${C_BLD}╔══════════════════════════════════════════════════════════════╗${C_RST}"
echo "${C_BLD}║  CLEAN STATE GATE — TimeWoven                                ║${C_RST}"
echo "${C_BLD}║  Project: $PROJECT_DIR${C_RST}"
echo "${C_BLD}║  Time:    $(iso_now)${C_RST}"
echo "${C_BLD}╚══════════════════════════════════════════════════════════════╝${C_RST}"
echo ""

# --- 1. git status --porcelain должен быть пуст -----------------------------
DIRTY="$(git status --porcelain)"
if [[ -z "$DIRTY" ]]; then
  pass "git status: рабочее дерево чистое"
else
  fail "git status: есть незакрытые изменения"
  while IFS= read -r line; do
    REPORT+=("        ${C_DIM}$line${C_RST}")
  done <<< "$DIRTY"
fi

# --- 2. git stash list должен быть пустым -----------------------------------
STASHES="$(git stash list)"
if [[ -z "$STASHES" ]]; then
  pass "git stash: пусто"
else
  fail "git stash: есть незакрытые stash (по протоколу — недопустимо)"
  while IFS= read -r line; do
    REPORT+=("        ${C_DIM}$line${C_RST}")
  done <<< "$STASHES"
fi

# --- 3. Текущая ветка должна соответствовать паттерну -----------------------
BRANCH="$(git branch --show-current)"
if [[ -z "$BRANCH" ]]; then
  fail "git branch: detached HEAD (нет ветки)"
elif [[ "$BRANCH" =~ $EXPECTED_BRANCH_PATTERN ]]; then
  pass "git branch: '$BRANCH' (валидное имя)"
else
  warn "git branch: '$BRANCH' не соответствует паттерну main|T-XXX-..."
fi

# --- 4. Локальные неотправленные коммиты -----------------------------------
if [[ -n "$BRANCH" ]]; then
  if git ls-remote --exit-code --heads origin "$BRANCH" > /dev/null 2>&1; then
    UNPUSHED="$(git log "origin/$BRANCH..HEAD" --oneline 2>/dev/null || true)"
    if [[ -z "$UNPUSHED" ]]; then
      pass "git log: ветка синхронизирована с origin/$BRANCH"
    else
      # Разрешено иметь подписанные коммиты T-XXX:
      BAD_COMMITS="$(echo "$UNPUSHED" | grep -vE ' T-[A-Z0-9._-]+:' || true)"
      if [[ -z "$BAD_COMMITS" ]]; then
        warn "git log: есть локальные коммиты T-XXX, не отправленные в origin"
        while IFS= read -r line; do
          REPORT+=("        ${C_DIM}$line${C_RST}")
        done <<< "$UNPUSHED"
      else
        fail "git log: есть локальные коммиты без префикса T-XXX:"
        while IFS= read -r line; do
          REPORT+=("        ${C_DIM}$line${C_RST}")
        done <<< "$BAD_COMMITS"
      fi
    fi
  else
    warn "git log: ветка '$BRANCH' не существует в origin"
  fi
fi

# --- 5. systemd сервис должен быть active -----------------------------------
if command -v systemctl >/dev/null 2>&1; then
  SVC_STATE="$(systemctl is-active "$SERVICE_NAME" 2>/dev/null | head -1 || echo unknown)"
  SVC_STATE="${SVC_STATE:-unknown}"
  if [[ "$SVC_STATE" == "active" ]]; then
    pass "systemctl: $SERVICE_NAME active"
  else
    fail "systemctl: $SERVICE_NAME = $SVC_STATE (ожидалось active)"
  fi
else
  skip "systemctl check (not available)"
fi

# --- 6. /health endpoint ----------------------------------------------------
check_health() {
  local url="$1"
  local label="$2"
  local resp
  resp="$(curl -sS --max-time 5 "$url" 2>/dev/null || true)"
  if echo "$resp" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
    pass "health $label: 200 OK"
  else
    fail "health $label: $url не отдал {\"status\":\"ok\"} (got: ${resp:0:80})"
  fi
}
check_health "$HEALTH_URL_LOCAL" "(local)"
if [[ -n "$HEALTH_URL_PUBLIC" ]]; then
  check_health "$HEALTH_URL_PUBLIC" "(public)"
else
  skip "health (public): URL not set"
fi

# --- Итог -------------------------------------------------------------------
echo ""
echo "${C_BLD}── Отчёт ─────────────────────────────────────────────────────${C_RST}"
for line in "${REPORT[@]}"; do
  echo "  $line"
done
echo "${C_BLD}──────────────────────────────────────────────────────────────${C_RST}"

if [[ $FAILS -eq 0 ]]; then
  echo ""
  echo "${C_GRN}${C_BLD}✓ PASS — clean state${C_RST} (warnings: $WARNINGS)"
  echo "Можно начинать новое задание."
  exit 0
else
  echo ""
  echo "${C_RED}${C_BLD}✗ FAIL — есть незакрытые долги${C_RST} (failures: $FAILS, warnings: $WARNINGS)"
  echo ""
  echo "Что делать:"
  echo "  1. Закрыть текущие изменения коммитом T-XXX или явным rollback."
  echo "  2. Очистить stash (закоммитить в feature-ветку или drop с записью в PROJECT_LOG)."
  echo "  3. Поднять сервис, если он лежит."
  echo "  4. Снова запустить: bash scripts/ops/clean_state_gate.sh"
  echo ""
  exit 1
fi
