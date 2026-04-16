#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/root/projects/TimeWoven"
SOURCE_DIR="$PROJECT_DIR/docs"
TARGET_DIR="/var/www/timewoven"

echo "==> TimeWoven landing deploy started"
cd "$PROJECT_DIR"

echo "==> Git status before deploy"
git status --short || true

echo "==> Copying landing files"
mkdir -p "$TARGET_DIR"
cp -f "$SOURCE_DIR"/index.html "$TARGET_DIR"/
cp -f "$SOURCE_DIR"/logo.png "$TARGET_DIR"/

if [ -f "$SOURCE_DIR/CNAME" ]; then
  cp -f "$SOURCE_DIR"/CNAME "$TARGET_DIR"/
fi

echo "==> Setting permissions"
chown -R www-data:www-data "$TARGET_DIR"
find "$TARGET_DIR" -type d -exec chmod 755 {} \;
find "$TARGET_DIR" -type f -exec chmod 644 {} \;

echo "==> Testing nginx"
nginx -t

echo "==> Deploy complete"
ls -la "$TARGET_DIR"
