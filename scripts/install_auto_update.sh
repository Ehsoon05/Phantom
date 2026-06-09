#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/phantom}"
REMOTE="${REMOTE:-origin}"
BRANCH="${BRANCH:-WIP}"
SERVICE_NAME="${SERVICE_NAME:-phantom-bot.service}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this installer as root: sudo APP_DIR=$APP_DIR BRANCH=$BRANCH bash scripts/install_auto_update.sh"
  exit 1
fi

install -m 0755 scripts/update_from_git.sh /usr/local/bin/phantom-update-from-git

sed \
  -e "s|/opt/phantom|$APP_DIR|g" \
  -e "s|REMOTE=origin|REMOTE=$REMOTE|g" \
  -e "s|BRANCH=WIP|BRANCH=$BRANCH|g" \
  -e "s|SERVICE_NAME=phantom-bot.service|SERVICE_NAME=$SERVICE_NAME|g" \
  deploy/systemd/phantom-auto-update.service > /etc/systemd/system/phantom-auto-update.service

cp deploy/systemd/phantom-auto-update.timer /etc/systemd/system/phantom-auto-update.timer

systemctl daemon-reload
systemctl enable --now phantom-auto-update.timer

echo "Installed phantom-auto-update.timer."
echo "Check status with: systemctl status phantom-auto-update.timer"
