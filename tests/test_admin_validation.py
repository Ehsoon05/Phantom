import importlib

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


def test_config_rejects_invalid_support_url(monkeypatch):
    monkeypatch.setenv("MAIN_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("ADMIN_BOT_TOKEN", "456:def")
    monkeypatch.setenv("ADMIN_USER_ID", "123456")
    monkeypatch.setenv("ADMIN_PASSWORD", "strong-password")
    monkeypatch.setenv("SUPPORT_URL", "not-a-url")

    import bot_package.config_loader as config_loader

    config_loader = importlib.reload(config_loader)

    with pytest.raises(RuntimeError, match="SUPPORT_URL"):
        config_loader.BotConfig.validate()


def test_config_rejects_invalid_log_level(monkeypatch):
    monkeypatch.setenv("MAIN_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("ADMIN_BOT_TOKEN", "456:def")
    monkeypatch.setenv("ADMIN_USER_ID", "123456")
    monkeypatch.setenv("ADMIN_PASSWORD", "strong-password")
    monkeypatch.setenv("LOG_LEVEL", "LOUD")

    import bot_package.config_loader as config_loader

    config_loader = importlib.reload(config_loader)

    with pytest.raises(RuntimeError, match="LOG_LEVEL"):
        config_loader.BotConfig.validate()


def test_config_accepts_multiple_admin_ids(monkeypatch):
    monkeypatch.delenv("ADMIN_USER_ID", raising=False)
    monkeypatch.setenv("MAIN_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("ADMIN_BOT_TOKEN", "456:def")
    monkeypatch.setenv("ADMIN_USER_IDS", "123456, 789012, invalid, 123456")
    monkeypatch.setenv("ADMIN_PASSWORD", "strong-password")

    import bot_package.config_loader as config_loader

    config_loader = importlib.reload(config_loader)

    assert config_loader.BotConfig.ADMIN_USER_IDS == (123456, 789012)
    assert config_loader.BotConfig.ADMIN_USER_ID == 123456
    assert config_loader.BotConfig.is_admin(789012) is True
    assert config_loader.BotConfig.is_admin(111111) is False
    config_loader.BotConfig.validate()


def test_config_keeps_legacy_single_admin_id(monkeypatch):
    monkeypatch.delenv("ADMIN_USER_IDS", raising=False)
    monkeypatch.setenv("MAIN_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("ADMIN_BOT_TOKEN", "456:def")
    monkeypatch.setenv("ADMIN_USER_ID", "123456")
    monkeypatch.setenv("ADMIN_PASSWORD", "strong-password")

    import bot_package.config_loader as config_loader

    config_loader = importlib.reload(config_loader)

    assert config_loader.BotConfig.ADMIN_USER_IDS == (123456,)
    assert config_loader.BotConfig.is_admin(123456) is True
    config_loader.BotConfig.validate()


@pytest.mark.asyncio
async def test_negative_wallet_charge_is_rejected(db):
    from bot_package.models import User
    from bot_package.services.user_service import UserService

    async with db.async_session() as session:
        user = User(telegram_id=1001, first_name="Test", wallet_balance=10_000)
        session.add(user)
        await session.commit()

        success = await UserService.charge_wallet(session, 1001, -5_000, 123456)

    assert success is False


@pytest.mark.asyncio
async def test_wallet_balance_can_be_set_exactly(db):
    from bot_package.models import Transaction, User
    from bot_package.services.user_service import UserService
    from sqlalchemy import select

    async with db.async_session() as session:
        user = User(telegram_id=1001, first_name="Test", wallet_balance=10_000)
        session.add(user)
        await session.commit()

        success = await UserService.set_wallet_balance(session, 1001, 2_500, 123456)

    async with db.async_session() as session:
        saved_user = (await session.execute(select(User).where(User.telegram_id == 1001))).scalar_one()
        transaction = (await session.execute(select(Transaction))).scalar_one()

    assert success is True
    assert saved_user.wallet_balance == 2_500
    assert transaction.amount == -7_500
    assert transaction.type == "wallet_set"


@pytest.mark.asyncio
async def test_negative_wallet_balance_set_is_rejected(db):
    from bot_package.models import User
    from bot_package.services.user_service import UserService

    async with db.async_session() as session:
        user = User(telegram_id=1001, first_name="Test", wallet_balance=10_000)
        session.add(user)
        await session.commit()

        success = await UserService.set_wallet_balance(session, 1001, -1, 123456)

    assert success is False


@pytest.mark.asyncio
async def test_zero_price_update_is_rejected(db):
    from bot_package.services.price_service import PriceService

    async with db.async_session() as session:
        await PriceService.init_default_prices(session)
        success = await PriceService.update_price(session, 1, 0)

    assert success is False
