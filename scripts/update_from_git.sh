#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/phantom}"
REMOTE="${REMOTE:-origin}"
BRANCH="${BRANCH:-WIP}"
SERVICE_NAME="${SERVICE_NAME:-phantom-bot.service}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$APP_DIR/venv}"
LOCK_FILE="${LOCK_FILE:-/tmp/phantom-auto-update.lock}"

log() {
  printf '[%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
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
  exit 0
fi

merge_base="$(git merge-base HEAD FETCH_HEAD)"
if [ "$merge_base" != "$local_rev" ]; then
  log "Remote is not a fast-forward from local HEAD. Refusing to update."
  exit 1
fi

requirements_changed="false"
if git diff --name-only HEAD FETCH_HEAD -- bot_package/requirements.txt | grep -q .; then
  requirements_changed="true"
fi

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

if command -v systemctl >/dev/null 2>&1; then
  log "Restarting $SERVICE_NAME"
  systemctl restart "$SERVICE_NAME"
else
  log "systemctl not found. Restart $SERVICE_NAME manually."
fi

log "Update complete."
