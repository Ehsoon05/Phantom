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


@pytest.mark.asyncio
async def test_broadcast_recipients_exclude_blocked_users(db):
    from bot_package.models import User
    from bot_package.services.broadcast_service import BroadcastService

    async with db.async_session() as session:
        session.add_all(
            [
                User(telegram_id=1001, first_name="Active"),
                User(telegram_id=1002, first_name="Blocked", is_blocked=True),
                User(telegram_id=1003, first_name="Active 2"),
            ]
        )
        await session.commit()
        recipients = await BroadcastService.recipient_ids(session)

    assert recipients == [1001, 1003]


@pytest.mark.asyncio
async def test_wallet_charge_notification_is_customizable(db):
    from bot_package.services.shop_customization_service import ShopCustomizationService

    async with db.async_session() as session:
        await ShopCustomizationService.init_defaults(session)
        message = await ShopCustomizationService.get_message(
            session,
            "wallet_charge_notification",
            amount="25,000",
            wallet_balance="80,000",
        )

    assert "25,000" in message
    assert "80,000" in message
    assert "شارژ شد" in message


@pytest.mark.asyncio
async def test_wallet_charge_notification_sends_rendered_message(db):
    from bot_package.services.shop_customization_service import ShopCustomizationService
    from bot_package.services.wallet_notification_service import WalletNotificationService

    sent = []

    class FakeBot:
        async def send_message(self, **kwargs):
            sent.append(kwargs)

    async with db.async_session() as session:
        await ShopCustomizationService.init_defaults(session)
        success = await WalletNotificationService.send_charge_notification(
            session,
            telegram_id=1001,
            amount=25_000,
            wallet_balance=80_000,
            bot=FakeBot(),
        )

    assert success is True
    assert sent[0]["chat_id"] == 1001
    assert "25,000" in sent[0]["text"]
    assert "80,000" in sent[0]["text"]
    assert sent[0]["reply_markup"] is not None


def test_admin_main_keyboard_contains_broadcast():
    from bot_package.utils.keyboards import ADMIN_BROADCAST, admin_main_keyboard

    labels = [
        button.text
        for row in admin_main_keyboard().keyboard
        for button in row
    ]
    assert ADMIN_BROADCAST in labels


def test_broadcast_preserves_telegram_html_entities():
    from types import SimpleNamespace

    from bot_package.handlers.admin_handlers import _broadcast_text

    message = SimpleNamespace(
        text="پیام ویژه",
        text_html='<b>پیام</b> <tg-emoji emoji-id="5373141891321699086">🔥</tg-emoji>',
        entities=[SimpleNamespace(type="bold")],
    )
    text, parse_mode = _broadcast_text(message)

    assert "<tg-emoji" in text
    assert parse_mode == "HTML"
