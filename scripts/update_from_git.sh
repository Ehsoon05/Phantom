#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/phantom}"
REMOTE="${REMOTE:-origin}"
BRANCH="${BRANCH:-WIP}"
SERVICE_NAME="${SERVICE_NAME:-phantom-bot.service}"
API_SERVICE_NAME="${API_SERVICE_NAME:-phantom-api.service}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$APP_DIR/venv}"
LOCK_FILE="${LOCK_FILE:-/tmp/phantom-auto-update.lock}"
WEBAPP_DEPLOY_DIR="${WEBAPP_DEPLOY_DIR:-/var/www/phantom-app}"
ADMIN_DEPLOY_DIR="${ADMIN_DEPLOY_DIR:-/var/www/phantom-admin}"
SELLER_PANEL_DIR="${SELLER_PANEL_DIR:-/opt/seller-panel}"
SELLER_PANEL_REMOTE="${SELLER_PANEL_REMOTE:-origin}"
SELLER_PANEL_BRANCH="${SELLER_PANEL_BRANCH:-main}"

log() {
  printf '[%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

update_seller_panel() {
  if [ ! -d "$SELLER_PANEL_DIR/.git" ]; then
    return 0
  fi

  (
    cd "$SELLER_PANEL_DIR"

    if [ "$(git rev-parse --abbrev-ref HEAD)" != "$SELLER_PANEL_BRANCH" ]; then
      log "Seller panel is not on '$SELLER_PANEL_BRANCH'; skipping its update."
      return 0
    fi
    if ! git diff-index --quiet HEAD --; then
      log "Seller panel has local changes; skipping its update."
      return 0
    fi

    log "Fetching seller panel $SELLER_PANEL_REMOTE/$SELLER_PANEL_BRANCH"
    git fetch "$SELLER_PANEL_REMOTE" "$SELLER_PANEL_BRANCH"

    local seller_local_rev seller_remote_rev seller_merge_base
    seller_local_rev="$(git rev-parse HEAD)"
    seller_remote_rev="$(git rev-parse FETCH_HEAD)"
    if [ "$seller_local_rev" = "$seller_remote_rev" ]; then
      log "Seller panel is already up to date."
      return 0
    fi

    seller_merge_base="$(git merge-base HEAD FETCH_HEAD)"
    if [ "$seller_merge_base" != "$seller_local_rev" ]; then
      log "Seller panel update is not a fast-forward; skipping it."
      return 0
    fi

    log "Updating seller panel to $seller_remote_rev"
    git merge --ff-only FETCH_HEAD
    docker compose up -d --build
    log "Seller panel update complete."
  )
}

cd "$APP_DIR"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  log "Another update is already running. Exiting."
  exit 0
fi

current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [ "$current_branch" != "$BRANCH" ]; then
  log "Server is on branch '$current_branch', expected '$BRANCH'. Refusing to update."
  exit 1
fi

if ! git diff-index --quiet HEAD --; then
  log "Working tree has local changes. Refusing to update."
  exit 1
fi

log "Fetching $REMOTE/$BRANCH"
git fetch "$REMOTE" "$BRANCH"

local_rev="$(git rev-parse HEAD)"
remote_rev="$(git rev-parse FETCH_HEAD)"

if [ "$local_rev" = "$remote_rev" ]; then
  log "Already up to date."
  if ! update_seller_panel; then
    log "Seller panel update failed; the Phantom deployment remains active."
  fi
  exit 0
fi

merge_base="$(git merge-base HEAD FETCH_HEAD)"
if [ "$merge_base" != "$local_rev" ]; then
  log "Remote is not a fast-forward from local HEAD. Refusing to update."
  exit 1
fi

requirements_changed="false"
changed_files="$(git diff --name-only HEAD FETCH_HEAD)"
if grep -q '^bot_package/requirements\.txt$' <<<"$changed_files"; then
  requirements_changed="true"
fi
bot_changed="$(grep -Eq '^(bot_package/|run\.py$)' <<<"$changed_files" && printf true || printf false)"
api_changed="$(grep -Eq '^(webapi/|bot_package/)' <<<"$changed_files" && printf true || printf false)"
webapp_changed="$(grep -Eq '^webapp/' <<<"$changed_files" && printf true || printf false)"
admin_changed="$(grep -Eq '^admin-panel/' <<<"$changed_files" && printf true || printf false)"

log "Fast-forwarding to $remote_rev"
git merge --ff-only FETCH_HEAD

if [ "$requirements_changed" = "true" ]; then
  log "Dependencies changed. Updating virtual environment."
  if [ ! -d "$VENV_DIR" ]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi
  "$VENV_DIR/bin/python" -m pip install --upgrade pip
  "$VENV_DIR/bin/python" -m pip install -r bot_package/requirements.txt
fi

if [ "$webapp_changed" = "true" ]; then
  log "Building Telegram Mini App"
  (
    cd "$APP_DIR/webapp"
    npm ci
    npm run build
  )
  mkdir -p "$WEBAPP_DEPLOY_DIR"
  rsync -a --delete "$APP_DIR/webapp/out/" "$WEBAPP_DEPLOY_DIR/"
fi

if [ "$admin_changed" = "true" ]; then
  log "Building admin panel"
  (
    cd "$APP_DIR/admin-panel"
    npm ci
    npm run build
  )
  mkdir -p "$ADMIN_DEPLOY_DIR"
  rsync -a --delete "$APP_DIR/admin-panel/dist/" "$ADMIN_DEPLOY_DIR/"
fi

if command -v systemctl >/dev/null 2>&1; then
  if [ "$bot_changed" = "true" ]; then
    log "Restarting $SERVICE_NAME"
    systemctl restart "$SERVICE_NAME"
  fi
  if [ "$api_changed" = "true" ]; then
    log "Restarting $API_SERVICE_NAME"
    systemctl restart "$API_SERVICE_NAME"
  fi
else
  log "systemctl not found. Restart changed services manually."
fi

if ! update_seller_panel; then
  log "Seller panel update failed; the Phantom deployment remains active."
fi

log "Update complete."
