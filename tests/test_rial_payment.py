import importlib

import pytest
import pytest_asyncio
from sqlalchemy import select


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


def test_iran_phone_normalization():
    from bot_package.handlers.rial_user import _normalize_iran_phone

    assert _normalize_iran_phone("0912 123 4567") == "+989121234567"
    assert _normalize_iran_phone("+98 912 123 4567") == "+989121234567"
    assert _normalize_iran_phone("۰۹۱۲۱۲۳۴۵۶۷") == "+989121234567"
    assert _normalize_iran_phone("+1 202 555 0100") is None


def test_iran_card_validation():
    from bot_package.handlers.rial_user import _normalize_card

    assert _normalize_card("6219-8619-3157-3371") == "6219861931573371"
    assert _normalize_card("6219861931573372") is None
    assert _normalize_card("1111111111111111") is None


@pytest.mark.asyncio
async def test_rial_request_is_persisted_with_numeric_tracking_code(db):
    from bot_package.models import RialPaymentRequest, User
    from bot_package.services.rial_payment_service import RialPaymentService

    async with db.async_session() as session:
        session.add(User(telegram_id=1001, first_name="Test"))
        await session.commit()
        request = await RialPaymentService.create_request(
            session,
            user_id=1001,
            amount_toman=100_000,
            phone_number="+989121234567",
            source_card="6219861931573371",
            support_handle="@PhantomHubsSupport",
            request_text="",
        )
        await RialPaymentService.update_request_text(session, request, "payment draft")

    async with db.async_session() as session:
        saved = (await session.execute(select(RialPaymentRequest))).scalar_one()

    assert saved.amount_toman == 100_000
    assert saved.tracking_code.isdigit()
    assert len(saved.tracking_code) == 19
    assert saved.request_text == "payment draft"
    assert saved.status == "pending"


def test_current_shop_snapshot_is_the_code_default():
    from bot_package.services.shop_customization_service import DEFAULT_BUTTONS, DEFAULT_CATEGORIES, DEFAULT_PLANS

    actions = {(button.menu, button.action) for button in DEFAULT_BUTTONS}
    categories = {category.key for category in DEFAULT_CATEGORIES}
    plans = {(plan.category_key, plan.volume_gb, plan.price) for plan in DEFAULT_PLANS}

    assert ("shop_main", "custom_message:shop_main:1780731124") in actions
    assert ("shop_main", "trial_config") in actions
    assert ("shop_wallet", "charge_rial") in actions
    main_positions = {
        button.action: (button.row, button.col)
        for button in DEFAULT_BUTTONS
        if button.menu == "shop_main"
    }
    assert main_positions["buy_subscription"] == (0, 1)
    assert main_positions["purchase_history"] == (2, 1)
    assert "___phantom_express_-_فانتوم_اکسپرس" in categories
    assert ("___phantom_express_-_فانتوم_اکسپرس", 10, 89_000) in plans
