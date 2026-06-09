import importlib

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload


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
async def test_purchase_flow_commits_wallet_stock_purchase_and_transaction(db):
    from bot_package.models import Config, Purchase, Transaction, User
    from bot_package.services.inventory_service import InventoryService
    from bot_package.services.price_service import PriceService

    async with db.async_session() as session:
        user = User(telegram_id=1001, first_name="Test", wallet_balance=20_000)
        config = Config(volume_gb=1, sub_link="vless://one")
        session.add_all([user, config])
        await PriceService.init_default_prices(session)

        price = await PriceService.get_price(session, 1)
        available = await InventoryService.get_available_config(session, 1)

        user.wallet_balance -= price
        sold = await InventoryService.sell_config(session, available, user.telegram_id)
        session.add(Purchase(user_id=user.telegram_id, config_id=available.id, volume_gb=1, price=price))
        session.add(Transaction(user_id=user.telegram_id, amount=-price, type="purchase"))
        await session.commit()

    async with db.async_session() as session:
        saved_user = (await session.execute(select(User))).scalar_one()
        saved_config = (await session.execute(select(Config))).scalar_one()
        purchases = (await session.execute(select(Purchase))).scalars().all()
        transactions = (await session.execute(select(Transaction))).scalars().all()

    assert sold is True
    assert saved_user.wallet_balance == 5_000
    assert saved_config.is_sold is True
    assert saved_config.sold_to_user_id == 1001
    assert len(purchases) == 1
    assert len(transactions) == 1


@pytest.mark.asyncio
async def test_purchase_can_store_coupon_code_snapshot(db):
    from bot_package.models import Config, Coupon, Purchase, User

    async with db.async_session() as session:
        user = User(telegram_id=1001, first_name="Test")
        config = Config(volume_gb=1, sub_link="vless://one", is_sold=True, sold_to_user_id=1001)
        coupon = Coupon(code="SAVE10", discount_type="percent", amount=10, created_by=123456)
        session.add_all([user, config, coupon])
        await session.flush()
        session.add(
            Purchase(
                user_id=1001,
                config_id=config.id,
                volume_gb=1,
                price=13_500,
                original_price=15_000,
                discount_amount=1_500,
                coupon_id=coupon.id,
                coupon_code=coupon.code,
            )
        )
        await session.commit()

    async with db.async_session() as session:
        purchase = (await session.execute(select(Purchase))).scalar_one()

    assert purchase.coupon_id == coupon.id
    assert purchase.coupon_code == "SAVE10"


@pytest.mark.asyncio
async def test_sold_config_cannot_be_sold_again(db):
    from bot_package.models import Config
    from bot_package.services.inventory_service import InventoryService

    async with db.async_session() as session:
        config = Config(volume_gb=1, sub_link="vless://one", is_sold=True)
        session.add(config)
        await session.commit()

        sold = await InventoryService.sell_config(session, config, 1001)
        await session.rollback()

    assert sold is False


@pytest.mark.asyncio
async def test_purchase_history_can_load_config_link(db):
    from bot_package.models import Config, Purchase, User

    async with db.async_session() as session:
        user = User(telegram_id=1001, first_name="Test")
        config = Config(volume_gb=1, sub_link="vless://one", is_sold=True, sold_to_user_id=1001)
        session.add_all([user, config])
        await session.flush()
        session.add(Purchase(user_id=1001, config_id=config.id, volume_gb=1, price=15_000))
        await session.commit()

    async with db.async_session() as session:
        result = await session.execute(select(Purchase).options(selectinload(Purchase.config)))
        purchase = result.scalar_one()

    assert purchase.config.sub_link == "vless://one"


@pytest.mark.asyncio
async def test_shop_category_can_be_fully_customized(db):
    from bot_package.services.shop_customization_service import ShopCustomizationService

    async with db.async_session() as session:
        category = await ShopCustomizationService.ensure_category(session, "vip", "VIP")
        updated = await ShopCustomizationService.update_category(
            session,
            category.key,
            title="سرورهای ویژه",
            emoji="🚀",
            premium_emoji_id="5373141891321699086",
            emoji_position="right",
            style="danger",
            display_order=7,
            is_active=False,
        )

    assert updated.title == "سرورهای ویژه"
    assert updated.emoji == "🚀"
    assert updated.premium_emoji_id == "5373141891321699086"
    assert updated.emoji_position == "right"
    assert updated.style == "danger"
    assert updated.display_order == 7
    assert updated.is_active is False


def test_admin_category_button_label_is_short_and_hides_internal_key():
    from types import SimpleNamespace

    from bot_package.handlers.admin_handlers import _category_label

    category = SimpleNamespace(
        key="reality_servers_internal",
        title="سرورهای Reality",
        emoji="🌐",
        is_active=True,
    )

    label = _category_label(category)

    assert label == "✅ 🌐 سرورهای Reality"
    assert category.key not in label


@pytest.mark.asyncio
async def test_shop_category_delete_is_blocked_while_in_use(db):
    from bot_package.models import Config
    from bot_package.services.shop_customization_service import ShopCustomizationService

    async with db.async_session() as session:
        category = await ShopCustomizationService.ensure_category(session, "vip", "VIP")
        session.add(Config(volume_gb=10, category_key=category.key, sub_link="vless://vip"))
        await session.commit()

        plan_count, config_count = await ShopCustomizationService.category_usage(session, category.key)
        deleted = await ShopCustomizationService.delete_category(session, category.key)

    assert (plan_count, config_count) == (0, 1)
    assert deleted is False


@pytest.mark.asyncio
async def test_unused_shop_category_can_be_deleted(db):
    from bot_package.services.shop_customization_service import ShopCustomizationService

    async with db.async_session() as session:
        category = await ShopCustomizationService.ensure_category(session, "unused", "Unused")
        await session.commit()
        deleted = await ShopCustomizationService.delete_category(session, category.key)
        saved = await ShopCustomizationService.get_category(session, category.key)

    assert deleted is True
    assert saved is None


@pytest.mark.asyncio
async def test_shop_message_renders_premium_emoji_and_keeps_markdown_formatting(db):
    from bot_package.services.shop_customization_service import ShopCustomizationService

    async with db.async_session() as session:
        await ShopCustomizationService.init_defaults(session)
        await ShopCustomizationService.update_message_settings(
            session,
            "account_info",
            premium_emoji_id="5373141891321699086",
            premium_emoji_position="right",
        )
        rendered = await ShopCustomizationService.get_message(
            session,
            "account_info",
            telegram_id=1001,
            first_name="Test",
            username="@test",
            wallet_balance="1,000",
            total_count=1,
            total_gb=10,
            total_spent="15,000",
            referral_count=2,
        )

    assert rendered.parse_mode == "HTML"
    assert '<tg-emoji emoji-id="5373141891321699086">' in rendered
    assert "<b>اطلاعات حساب</b>" in rendered
    assert rendered.endswith("</tg-emoji>")


@pytest.mark.asyncio
async def test_shop_message_preserves_inline_premium_emojis(db):
    from bot_package.services.shop_customization_service import ShopCustomizationService

    inline_emoji = '<tg-emoji emoji-id="5373141891321699086">🔥</tg-emoji>'
    async with db.async_session() as session:
        await ShopCustomizationService.init_defaults(session)
        await ShopCustomizationService.update_message(
            session,
            "account_info",
            f"{inline_emoji} سلام {{first_name}}",
            parse_mode="HTML",
        )
        rendered = await ShopCustomizationService.get_message(
            session,
            "account_info",
            first_name="<Ehsan>",
        )

    assert rendered.parse_mode == "HTML"
    assert inline_emoji in rendered
    assert "&lt;Ehsan&gt;" in rendered


def test_admin_message_storage_uses_telegram_html_for_custom_emoji():
    from types import SimpleNamespace

    from bot_package.handlers.admin_handlers import _message_text_for_storage

    message = SimpleNamespace(
        text="🔥 پیام",
        text_html='<tg-emoji emoji-id="5373141891321699086">🔥</tg-emoji> پیام',
        entities=[
            SimpleNamespace(
                type="custom_emoji",
                custom_emoji_id="5373141891321699086",
            )
        ],
    )

    text, parse_mode = _message_text_for_storage(message)

    assert parse_mode == "HTML"
    assert 'emoji-id="5373141891321699086"' in text


@pytest.mark.asyncio
async def test_branded_subscription_link_setting_can_be_toggled(db):
    from bot_package.services.settings_service import SettingsService

    async with db.async_session() as session:
        assert await SettingsService.branded_links_enabled(session) is True
        await SettingsService.set_branded_links_enabled(session, False)
        assert await SettingsService.branded_links_enabled(session) is False


def test_purchase_flow_locks_user_row_with_for_update():
    """Regression for the wallet double-spend race: the purchase handler must
    request a row-level lock on the user when reading the wallet, so two
    concurrent buys cannot both observe the pre-deduction balance. The lock is
    a no-op on SQLite and emits ``FOR UPDATE`` on PostgreSQL.
    """
    import inspect as _inspect

    from sqlalchemy.dialects import postgresql

    from bot_package.handlers import user_handlers

    source = _inspect.getsource(user_handlers.process_purchase)
    assert ".with_for_update()" in source, (
        "process_purchase must call .with_for_update() on the user select "
        "to prevent concurrent purchases from double-spending the wallet."
    )

    # Sanity: the call act
