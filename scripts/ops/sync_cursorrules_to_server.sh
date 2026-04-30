#!/usr/bin/env bash
set -euo pipefail

# Sync .cursorrules to the server repo directory.
# This script is intentionally non-interactive and does not modify server services.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RULES_FILE="${ROOT_DIR}/.cursorrules"

if [[ ! -f "$RULES_FILE" ]]; then
  echo "ERROR: .cursorrules not found at repo root"
  exit 1
fi

TW_SERVER_USER="${TW_SERVER_USER:-root}"
TW_SERVER_HOST="${TW_SERVER_HOST:-193.187.95.221}"
TW_SERVER_REPO_DIR="${TW_SERVER_REPO_DIR:-/root/projects/TimeWoven}"

REMOTE="${TW_SERVER_USER}@${TW_SERVER_HOST}"
REMOTE_PATH="${TW_SERVER_REPO_DIR}/.cursorrules"

echo "Syncing .cursorrules -> ${REMOTE}:${REMOTE_PATH}"
scp -q "$RULES_FILE" "${REMOTE}:${REMOTE_PATH}"

echo "Done."

