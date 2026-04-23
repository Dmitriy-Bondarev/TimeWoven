#!/bin/bash

# SINGLE SOURCE OF TRUTH:
# app/web/templates/site/landing.html

SOURCE="/root/projects/TimeWoven/app/web/templates/site/landing.html"
DEST="/var/www/timewoven/index.html"
ICON_SOURCE="/root/projects/TimeWoven/app/web/static/logo-128.png"
ICON_DEST="/var/www/timewoven/logo-128.png"

echo "Deploying landing..."

sudo cp -f $SOURCE $DEST
sudo chown www-data:www-data $DEST
sudo chmod 644 $DEST

sudo cp -f $ICON_SOURCE $ICON_DEST
sudo chown www-data:www-data $ICON_DEST
sudo chmod 644 $ICON_DEST

echo "Reloading nginx..."
sudo systemctl reload nginx

echo "Done."

echo "Checking result:"
curl -I https://timewoven.ru
curl -I https://timewoven.ru/logo-128.png
