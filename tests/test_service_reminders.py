import importlib
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio


@pytest_asyncio.fixture()
async def db(tmp_path, monkeypatch):
    monkeypatch.setenv("MAIN_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("ADMIN_BOT_TOKEN", "456:def")
    monkeypatch.setenv("ADMIN_USER_ID", "123456")
    monkeypatch.setenv("ADMIN_PASSWORD", "strong-password")
    monkeypatch.setenv("DB_URL", f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")

    import bot_package.config_loader as config_loader
    import bot_package.database as database
    from bot_package.models import Base

    importlib.reload(config_loader)
    database = importlib.reload(database)
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield database
    finally:
        await database.engine.dispose()


@pytest.mark.asyncio
async def test_service_reminder_selects_most_urgent_rules_once(db):
    from bot_package.models import Config, Purchase, ServiceReminderLog, User
    from bot_package.services.service_reminder_service import ServiceReminderService

    expire = int((datetime.now(timezone.utc) + timedelta(hours=12)).timestamp())
    async with db.async_session() as session:
        user = User(telegram_id=1001, first_name="Active")
        config = Config(
            volume_gb=10,
            sub_link="https://example.com/sub/token",
            public_sub_token="token",
            is_sold=True,
            sold_to_user_id=1001,
        )
        purchase = Purchase(
            user_id=1001,
            config=config,
            volume_gb=10,
            category_key="express",
            price=1000,
            service_name="Express",
        )
        session.add_all([user, config, purchase])
        await session.commit()
        purchase_id = purchase.id
        config_id = config.id

    async with db.async_session() as session:
        purchase = await session.get(Purchase, purchase_id)
        config = await session.get(Config, config_id)
        rules, values = await ServiceReminderService._due_rules(
            purchase,
            config,
            {"total": 1000, "remaining": 90, "expire": expire},
            [20, 10],
            [3, 1],
        )
        session.add(ServiceReminderLog(purchase_id=purchase_id, config_id=config_id, user_id=1001, rule_key="volume_10"))
        await session.commit()

    assert rules == ["volume_10", "time_1d"]
    assert values["remaining_percent"] == "9٪"

    async with db.async_session() as session:
        purchase = await session.get(Purchase, purchase_id)
        config = await session.get(Config, config_id)
        rules, _ = await ServiceReminderService._due_rules(
            purchase,
            config,
            {"total": 1000, "remaining": 90, "expire": expire},
            [20, 10],
            [3, 1],
        )

    assert rules == ["time_1d"]


def test_admin_shop_settings_keyboard_contains_service_reminders():
    from bot_package.utils.keyboards import ADMIN_SERVICE_REMINDERS, admin_shop_settings_keyboard

    labels = [button.text for row in admin_shop_settings_keyboard().keyboard for button in row]
    assert ADMIN_SERVICE_REMINDERS in labels


@pytest.mark.asyncio
async def test_service_reminder_handles_volume_only_and_finished_services(db):
    from bot_package.models import Config, Purchase, User
    from bot_package.services.service_reminder_service import ServiceReminderService

    expired = int((datetime.now(timezone.utc) - timedelta(minutes=5)).timestamp())
    async with db.async_session() as session:
        user = User(telegram_id=1002, first_name="Active")
        config = Config(
            volume_gb=30,
            sub_link="https://example.com/sub/volume-only",
            public_sub_token="volume-only",
            is_sold=True,
            sold_to_user_id=1002,
        )
        purchase = Purchase(
            user_id=1002,
            config=config,
            volume_gb=30,
            category_key="nolimits",
            price=1000,
            service_name="Volume Only",
        )
        session.add_all([user, config, purchase])
        await session.commit()
        purchase_id = purchase.id
        config_id = config.id

    async with db.async_session() as session:
        purchase = await session.get(Purchase, purchase_id)
        config = await session.get(Config, config_id)
        rules, values = await ServiceReminderService._due_rules(
            purchase,
            config,
            {"total": 1000, "remaining": 150, "expire": 0},
            [20, 10],
            [3, 1],
        )

    assert rules == ["volume_20"]
    assert values["expiry_text"] == "نامحدود"

    async with db.async_session() as session:
        purchase = await session.get(Purchase, purchase_id)
        config = await session.get(Config, config_id)
        rules, values = await ServiceReminderService._due_rules(
            purchase,
            config,
            {"total": 1000, "remaining": 0, "expire": expired},
            [20, 10],
            [3, 1],
        )

    assert rules == ["volume_empty", "time_expired"]
    assert "تمام شده" in values["reason_lines"]
    assert "پایان رسیده" in values["reason_lines"]
