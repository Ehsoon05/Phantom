# Phantom VPN Bot Suite

Version: `1.0.1`

Phantom is an asynchronous dual-bot Telegram system for selling VPN subscription links.

- **Main bot:** user-facing shop, wallet balance, purchases, and purchase history.
- **Admin bot:** inventory, prices, wallet charging, user lookup, and sales reports for one or more configured admins.

The implementation uses Python, `python-telegram-bot`, async SQLAlchemy, and SQLite by default.

## Project Structure

```text
Phantom/
  bot_package/
    main_bot.py
    admin_bot.py
    config_loader.py
    database.py
    models.py
    auth.py
    handlers/
    services/
    utils/
    requirements.txt
    setup_all.sh
    run.py
  README.md
```

## Setup

Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r bot_package/requirements.txt
```

Create a `.env` file in the project root:

```dotenv
MAIN_BOT_TOKEN=123456:ABC-DEF1234
ADMIN_BOT_TOKEN=654321:XYZ-ABC9876
ADMIN_USER_ID=123456789
# Optional: comma-separated list for multiple admins. ADMIN_USER_ID still works for one admin.
ADMIN_USER_IDS=123456789,987654321
# Optional: owner IDs can manage other admins. Defaults to ADMIN_USER_ID.
OWNER_USER_IDS=123456789
ADMIN_PASSWORD=replace-with-a-strong-password
DB_URL=sqlite+aiosqlite:///vpn_shop.db
SUPPORT_URL=https://t.me/YourSupport
SUPPORT_HANDLE=@YourSupport
CHANNEL_HANDLE=@YourChannel
SESSION_TIMEOUT_MINUTES=30
LOG_LEVEL=INFO
```

Run both bots:

```bash
python -m bot_package.run
```

You can also run the helper script on Linux:

```bash
chmod +x bot_package/setup_all.sh
./bot_package/setup_all.sh
```

## Security Notes

- Do not commit `.env` files or bot tokens.
- Replace the admin password before running the bot.
- SQLite is the default for local and small deployments. Use PostgreSQL before running high-volume paid traffic.

## Verification

Run the test suite:

```bash
pytest -q
```

Run a syntax/import smoke check:

```bash
python -m compileall -q bot_package run.py tests
MAIN_BOT_TOKEN=123:abc ADMIN_BOT_TOKEN=456:def ADMIN_USER_IDS=123456,789012 ADMIN_PASSWORD=strong-password python -c "import bot_package.run; import bot_package.handlers.admin_handlers; import bot_package.handlers.user_handlers; print('imports ok')"
```

## Manual Smoke Test

Use test Telegram bots and a fresh SQLite database.

1. Start both bots with `python -m bot_package.run`.
2. Send `/start` to the admin bot and log in.
3. Add at least one config link for a volume.
4. Send `/start` to the main bot with a test user.
5. In the admin bot, charge the test user's wallet.
6. In the main bot, buy the matching volume.
7. Confirm wallet balance, purchase history, stock status, and sales report all match.

## Admin Management

Owners can manage admins from the admin bot after logging in:

```text
/admins
/addadmin <telegram_id> <permissions>
/removeadmin <telegram_id>
/setadminperms <telegram_id> <permissions>
```

Supported permissions are `inventory`, `prices`, `users`, and `reports`. Use `all` to grant every permission. Owners cannot be removed or downgraded through bot commands.

## Production Upgrade Notes

- SQLite can work for a small bot, but concurrent paid purchases should move to PostgreSQL.
- Add Alembic migrations before changing schemas in production.
- Put the bot behind process supervision such as systemd, Docker, or a managed worker service.
- Keep `LOG_LEVEL=INFO` in normal operation and use `DEBUG` only during troubleshooting.

## Auto Update From Git On Server

The repo includes a conservative polling updater for Linux servers. It fetches your Git branch, fast-forwards only when the server has no local changes, installs dependency updates when `bot_package/requirements.txt` changes, and restarts the bot service.

Example server layout:

```bash
sudo git clone https://github.com/matinz03/Phantom.git /opt/phantom
cd /opt/phantom
sudo git switch main
sudo python3 -m venv venv
sudo ./venv/bin/python -m pip install -r bot_package/requirements.txt
sudo cp deploy/systemd/phantom-bot.service /etc/systemd/system/phantom-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now phantom-bot.service
```

Install the auto-update timer:

```bash
cd /opt/phantom
sudo APP_DIR=/opt/phantom REMOTE=origin BRANCH=main SERVICE_NAME=phantom-bot.service bash scripts/install_auto_update.sh
```

Check logs:

```bash
systemctl status phantom-auto-update.timer
journalctl -u phantom-auto-update.service -n 100 --no-pager
```

Run one update manually:

```bash
sudo APP_DIR=/opt/phantom REMOTE=origin BRANCH=main SERVICE_NAME=phantom-bot.service /usr/local/bin/phantom-update-from-git
```

## Current Capabilities

- User registration on `/start`
- Wallet balance display
- Volume-based VPN purchase flow
- Purchase history
- Admin password session
- Admin stock loading from subscription links
- Admin price editing
- Admin wallet charging
- Basic sales and user reports
