#!/usr/bin/env bash
# Nightly SQLite backup with 14-day rotation.
#
# Install:  crontab -e
#   30 3 * * * /opt/phantom/scripts/backup_db.sh >> /var/log/phantom-backup.log 2>&1
#
# Uses sqlite3 .backup (safe under concurrent writers, unlike cp).

set -euo pipefail

DB_FILE="${PHANTOM_DB_FILE:-/opt/phantom/vpn_shop.db}"
BACKUP_DIR="${PHANTOM_BACKUP_DIR:-/opt/phantom/backups}"
KEEP_DAYS="${PHANTOM_BACKUP_KEEP_DAYS:-14}"

mkdir -p "$BACKUP_DIR"
stamp="$(date +%Y%m%d-%H%M%S)"
target="$BACKUP_DIR/vpn_shop-$stamp.db"

sqlite3 "$DB_FILE" ".backup '$target'"
gzip "$target"
echo "$(date -Is) backed up to $target.gz"

find "$BACKUP_DIR" -name 'vpn_shop-*.db.gz' -mtime "+$KEEP_DAYS" -delete
