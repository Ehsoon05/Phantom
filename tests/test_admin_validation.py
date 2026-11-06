import importlib
from types import SimpleNamespace

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
async def test_user_stats_include_purchase_totals(db):
    from bot_package.models import Config, Purchase, User
    from bot_package.services.user_service import UserService

    async with db.async_session() as session:
        user = User(telegram_id=1001, first_name="Test", wallet_balance=10_000)
        config_one = Config(volume_gb=5, sub_link="vless://one", is_sold=True, sold_to_user_id=1001)
        config_two = Config(volume_gb=10, sub_link="vless://two", is_sold=True, sold_to_user_id=1001)
        session.add_all([user, config_one, config_two])
        await session.flush()
        session.add_all(
            [
                Purchase(user_id=1001, config_id=config_one.id, volume_gb=5, price=50_000),
                Purchase(user_id=1001, config_id=config_two.id, volume_gb=10, price=90_000),
            ]
        )
        await session.commit()

        stats = await UserService.get_user_stats(session)

    assert stats["total_purchased_gb"] == 15
    assert stats["total_spent"] == 140_000


@pytest.mark.asyncio
async def test_user_purchase_summary_includes_history_and_totals(db):
    from bot_package.models import Config, Purchase, User
    from bot_package.services.user_service import UserService

    async with db.async_session() as session:
        user = User(telegram_id=1001, first_name="Test")
        config_one = Config(volume_gb=1, sub_link="vless://one", is_sold=True, sold_to_user_id=1001)
        config_two = Config(volume_gb=2, sub_link="vless://two", is_sold=True, sold_to_user_id=1001)
        session.add_all([user, config_one, config_two])
        await session.flush()
        session.add_all(
            [
                Purchase(user_id=1001, config_id=config_one.id, volume_gb=1, price=15_000),
                Purchase(user_id=1001, config_id=config_two.id, volume_gb=2, price=28_000),
            ]
        )
        await session.commit()

        summary = await UserService.get_user_purchase_summary(session, 1001)

    assert summary["total_count"] == 2
    assert summary["total_gb"] == 3
    assert summary["total_spent"] == 43_000
    assert len(summary["purchases"]) == 2


@pytest.mark.asyncio
async def test_zero_price_update_is_rejected(db):
    from bot_package.services.price_service import PriceService

    async with db.async_session() as session:
        await PriceService.init_default_prices(session)
        success = await PriceService.update_price(session, 1, 0)

    assert success is False


def test_add_config_plan_keyboard_paginates_all_services():
    from bot_package.handlers.admin_handlers import (
        ADD_CONFIG_PAGE_SIZE,
        _add_config_plan_keyboard,
    )

    plans = [
        SimpleNamespace(
            id=index,
            category_key=f"category-{index % 3}",
            title=f"Service {index}",
            volume_gb=index,
        )
        for index in range(1, ADD_CONFIG_PAGE_SIZE * 2 + 4)
    ]

    first_page = _add_config_plan_keyboard(plans, 0).inline_keyboard
    second_page = _add_config_plan_keyboard(plans, 1).inline_keyboard
    last_page = _add_config_plan_keyboard(plans, 2).inline_keyboard

    first_ids = [row[0].callback_data for row in first_page[:ADD_CONFIG_PAGE_SIZE]]
    second_ids = [row[0].callback_data for row in second_page[:ADD_CONFIG_PAGE_SIZE]]
    last_ids = [row[0].callback_data for row in last_page[:-2]]

    assert first_ids[0] == "admin_addcfg:select:1"
    assert second_ids[0] == f"admin_addcfg:select:{ADD_CONFIG_PAGE_SIZE + 1}"
    assert last_ids[-1] == f"admin_addcfg:select:{len(plans)}"
    assert any(button.callback_data == "admin_addcfg:page:1" for button in last_page[-2])


def test_shop_plan_management_keyboard_paginates_and_keeps_labels_compact():
    from bot_package.handlers.admin_handlers import (
        ADD_CONFIG_PAGE_SIZE,
        _shop_plan_management_keyboard,
    )

    plans = [
        SimpleNamespace(
            id=index,
            category_key=f"category-with-a-long-key-{index}",
            title=f"Service with a deliberately long title number {index}",
            volume_gb=index,
            is_active=index % 2 == 0,
        )
        for index in range(1, ADD_CONFIG_PAGE_SIZE + 3)
    ]
    first_page = _shop_plan_management_keyboard(plans, 0).inline_keyboard
    second_page = _shop_plan_management_keyboard(plans, 1).inline_keyboard

    assert len(first_page[0][0].text) <= 60
    assert first_page[0][0].callback_data == "admin_planmgr:select:1"
    assert second_page[0][0].callback_data == (
        f"admin_planmgr:select:{ADD_CONFIG_PAGE_SIZE + 1}"
    )
    assert any(button.callback_data == "admin_planmgr:page:1" for button in first_page[-3])
