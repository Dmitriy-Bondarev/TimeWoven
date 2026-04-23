#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/root/projects/TimeWoven"
BACKUP_ROOT="$PROJECT_ROOT/backups/daily"
ARCHIVE_DIR="$BACKUP_ROOT/archive"
TMP_DIR="$BACKUP_ROOT/.tmp"
TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"

DB_DUMP_FILE="$BACKUP_ROOT/postgres_dump_${TIMESTAMP}.sql.gz"
PROJECT_ARCHIVE_FILE="$BACKUP_ROOT/project_${TIMESTAMP}.tar.gz"
UPLOADS_ARCHIVE_FILE="$BACKUP_ROOT/uploads_${TIMESTAMP}.tar.gz"

UPLOAD_DIRS=(
  "app/web/static/audio/uploads"
  "app/web/static/images/uploads"
)

mkdir -p "$BACKUP_ROOT" "$ARCHIVE_DIR" "$TMP_DIR"

# Load env from project .env when present (for DATABASE_URL)
if [[ -f "$PROJECT_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL is not set" >&2
  exit 1
fi

PG_DUMP_BIN="$(command -v pg_dump || true)"
if [[ -z "$PG_DUMP_BIN" ]]; then
  echo "ERROR: pg_dump not found in PATH" >&2
  exit 1
fi

# 1) PostgreSQL backup
"$PG_DUMP_BIN" "$DATABASE_URL" | gzip -9 > "$DB_DUMP_FILE"

# 2) Project archive (excluding generated backups and common heavy dirs)
tar \
  --exclude="./backups/daily" \
  --exclude="./.git" \
  --exclude="./.venv" \
  --exclude="./venv" \
  -C "$PROJECT_ROOT" \
  -czf "$PROJECT_ARCHIVE_FILE" .

# 3) Uploads archive (only existing upload folders)
UPLOADS_LIST_FILE="$TMP_DIR/uploads_${TIMESTAMP}.txt"
: > "$UPLOADS_LIST_FILE"
for rel in "${UPLOAD_DIRS[@]}"; do
  if [[ -d "$PROJECT_ROOT/$rel" ]]; then
    echo "$rel" >> "$UPLOADS_LIST_FILE"
  fi
done

if [[ -s "$UPLOADS_LIST_FILE" ]]; then
  tar -C "$PROJECT_ROOT" -czf "$UPLOADS_ARCHIVE_FILE" -T "$UPLOADS_LIST_FILE"
else
  # Keep a marker file so the run is traceable even if upload folders are absent
  echo "No upload directories found at backup time: $(date -u +%Y-%m-%dT%H:%M:%SZ)" | gzip -9 > "$UPLOADS_ARCHIVE_FILE"
fi

rm -f "$UPLOADS_LIST_FILE"

# Weekly/Archive promotion (Sunday UTC): copy daily artifacts into archive zone
if [[ "$(date -u +%u)" == "7" ]]; then
  cp -f "$DB_DUMP_FILE" "$ARCHIVE_DIR/"
  cp -f "$PROJECT_ARCHIVE_FILE" "$ARCHIVE_DIR/"
  cp -f "$UPLOADS_ARCHIVE_FILE" "$ARCHIVE_DIR/"
fi

# 4) Daily rotation: remove files older than 60 days, except Sunday-created files.
# Linux does not always provide creation time, so mtime is used as creation proxy.
while IFS= read -r -d '' file; do
  mtime_epoch="$(stat -c %Y "$file")"
  mtime_weekday="$(date -u -d "@$mtime_epoch" +%u)"
  if [[ "$mtime_weekday" != "7" ]]; then
    rm -f "$file"
  fi
done < <(find "$BACKUP_ROOT" -maxdepth 1 -type f -mtime +60 -print0)

# 5) Archive rotation: remove files older than 1 year from archive zone
find "$ARCHIVE_DIR" -type f -mtime +365 -delete

echo "Backup completed at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
