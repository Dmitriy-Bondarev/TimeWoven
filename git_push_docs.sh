#!/usr/bin/env bash
set -euo pipefail

cd /root/projects/TimeWoven
COMMIT_MSG="${1:-docs: sync project docs with production state}"
BRANCH="$(git branch --show-current)"

echo "==> Branch: $BRANCH"
echo
echo "==> git status"
git status --short
echo
echo "==> ignored check"
git check-ignore -v README.md TECH_PASSPORT.md DB_CHANGELOG.md CHANGELOG.md requirements.txt requirements.lock.txt .env venv .venv backups temp || true
echo

git add README.md TECH_PASSPORT.md DB_CHANGELOG.md CHANGELOG.md requirements.txt

if git diff --cached --quiet; then
  echo "ℹ️ Нет изменений для коммита"
  exit 0
fi

echo "==> staged diff"
git diff --cached --stat
echo

git commit -m "$COMMIT_MSG"

if git rev-parse --abbrev-ref --symbolic-full-name "@{u}" >/dev/null 2>&1; then
  git push
else
  git push -u origin "$BRANCH"
fi

echo
echo "✅ Готово"
