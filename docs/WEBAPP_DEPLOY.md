# Deploying the Phantom Web Platform

Three new pieces sit alongside the bots, all sharing the bot's database:

| Piece | Tech | Serves | Port (local) |
|---|---|---|---|
| `webapi/` | FastAPI | both frontends | 8000 |
| `webapp/` | Next.js 16 | Telegram Mini App (users) | 3000 |
| `admin-panel/` | React + Vite | admin SPA (static files) | — |

## 1. Environment variables (add to `/opt/phantom/.env`)

```env
# REQUIRED — sign JWTs for the web API; generate with: openssl rand -hex 32
API_JWT_SECRET=<64 hex chars>

# Allowed browser origins (the Mini App and admin panel URLs)
API_CORS_ORIGINS=https://app.example.com,https://admin.example.com

# Optional tuning
API_USER_TOKEN_TTL_HOURS=24
API_ADMIN_TOKEN_TTL_MINUTES=60
API_INIT_DATA_MAX_AGE_SECONDS=3600
```

The API reuses everything else from the bot's `.env` (`MAIN_BOT_TOKEN` is used to
validate Mini App `initData`; `ADMIN_PASSWORD` backs admin panel logins).

## 2. Install & build

```bash
cd /opt/phantom
./venv/bin/python -m pip install -r webapi/requirements.txt

# Mini App
cd webapp
cp .env.example .env.local   # set NEXT_PUBLIC_API_URL=https://api.example.com
                             #     NEXT_PUBLIC_BOT_USERNAME=YourBot
npm ci && npm run build

# Admin panel (outputs static files to dist/)
cd ../admin-panel
echo "VITE_API_URL=https://api.example.com" > .env.production
npm ci && npm run build
```

## 3. Services & proxy

```bash
sudo cp deploy/systemd/phantom-api.service /etc/systemd/system/
sudo cp deploy/systemd/phantom-webapp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now phantom-api phantom-webapp

# nginx: adapt deploy/nginx/phantom.conf.example (TLS via certbot),
# admin panel is served directly from admin-panel/dist
```

## 4. Backups

```bash
chmod +x scripts/backup_db.sh
# crontab -e
# 30 3 * * * /opt/phantom/scripts/backup_db.sh >> /var/log/phantom-backup.log 2>&1
```

## 5. Telegram wiring (manual, one-time)

1. BotFather → `/newapp` on the main bot → URL `https://app.example.com`,
   short name e.g. `shop` (must match `NEXT_PUBLIC_MINIAPP_SHORT_NAME`).
2. BotFather → Bot Settings → Menu Button → set to the Mini App.
3. Referral deep links then work as `https://t.me/YourBot/shop?startapp=ref_<code>`.

## 6. Tests

```bash
./venv/bin/python -m pytest tests/ -q
```

Includes `tests/test_api_purchase_race.py`, which proves that two concurrent
buyers of the last config produce exactly one sale and the loser keeps their
wallet balance, and that `Idempotency-Key` prevents double-charging.

## Known limitations / next steps

- **SQLite + two writer processes** (bot + API) works via file locking but
  PostgreSQL is recommended once traffic grows — `DB_URL` is the only change.
- The purchase idempotency cache is in-process; keep `--workers 1` for the API
  (or move the cache to a DB table before scaling out).
- Admin panel uses the shared `ADMIN_PASSWORD`; consider per-admin passwords +
  TOTP before exposing it on the public internet (or restrict by IP in nginx).
