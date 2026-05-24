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


@pytest.mark.asyncio
async def test_referral_code_and_attribution_are_stable(db):
    from bot_package.models import User
    from bot_package.services.referral_service import ReferralService

    async with db.async_session() as session:
        referrer = User(telegram_id=1001, first_name="Referrer")
        referred = User(telegram_id=2002, first_name="Referred")
        session.add_all([referrer, referred])
        await session.flush()

        code = await ReferralService.ensure_referral_code(session, referrer)
        applied = await ReferralService.apply_start_payload(session, referred, f"ref_{code}")
        reapplied = await ReferralService.apply_start_payload(session, referred, f"ref_{code}")
        await session.commit()

    async with db.async_session() as session:
        count = await ReferralService.count_referrals(session, 1001)
        saved = (await session.execute(select(User).where(User.telegram_id == 2002))).scalar_one()

    assert applied is True
    assert reapplied is False
    assert saved.referred_by_user_id == 1001
    assert count == 1


@pytest.mark.asyncio
async def test_self_referral_is_ignored(db):
    from bot_package.models import User
    from bot_package.services.referral_service import ReferralService

    async with db.async_session() as session:
        user = User(telegram_id=1001, first_name="User")
        session.add(user)
        await session.flush()
        code = await ReferralService.ensure_referral_code(session, user)
        applied = await ReferralService.apply_start_payload(session, user, f"ref_{code}")
        await session.commit()

    assert applied is False


@pytest.mark.asyncio
async def test_coupon_percent_fixed_targeting_and_replacement(db):
    from bot_package.services.coupon_service import CouponError, CouponService

    async with db.async_session() as session:
        percent = await CouponService.create_coupon(
            session,
            code="save25",
            discount_type="percent",
            amount=25,
            created_by=123456,
        )
        fixed = await CouponService.create_coupon(
            session,
            code="vip",
            discount_type="fixed",
            amount=5_000,
            created_by=123456,
            target_user_ids=[1001],
        )

        final_price, discount = CouponService.calculate_discount(20_000, percent)
        assert (final_price, discount) == (15_000, 5_000)

        with pytest.raises(CouponError):
            await CouponService.apply_coupon(session, 2002, "vip")

        applied = await CouponService.apply_coupon(session, 1001, "save25")
        assert applied.code == "SAVE25"
        applied = await CouponService.apply_coupon(session, 1001, "vip")
        active = await CouponService.get_active_coupon(session, 1001)

    assert fixed.code == "VIP"
    assert active.id == applied.id


@pytest.mark.asyncio
async def test_coupon_redeemed_cannot_be_reused_by_same_user(db):
    from bot_package.models import Config, Purchase, User
    from bot_package.services.coupon_service import CouponError, CouponService

    async with db.async_session() as session:
        user = User(telegram_id=1001, first_name="User")
        config = Config(volume_gb=1, sub_link="vless://one", is_sold=True, sold_to_user_id=1001)
        session.add_all([user, config])
        coupon = await CouponService.create_coupon(
            session,
            code="once",
            discount_type="fixed",
            amount=5_000,
            created_by=123456,
        )
        await CouponService.apply_coupon(session, 1001, "once")
        purchase = Purchase(
            user_id=1001,
            config_id=config.id,
            volume_gb=1,
            price=10_000,
            original_price=15_000,
            discount_amount=5_000,
            coupon_id=coupon.id,
        )
        session.add(purchase)
        await session.flush()
        await CouponService.mark_active_coupon_redeemed(session, 1001, purchase.id)
        await session.commit()

        with pytest.raises(CouponError):
            await CouponService.apply_coupon(session, 1001, "once")


def test_new_keyboard_labels_are_persian():
    from bot_package.utils import keyboards

    assert keyboards.APPLY_COUPON == "🎁 کد تخفیف"
    assert keyboards.REFERRALS == "👥 دعوت دوستان"
    assert keyboards.ADMIN_COUPONS == "🎟 مدیریت تخفیف‌ها"


@pytest.mark.asyncio
async def test_schema_service_adds_new_columns_to_existing_sqlite_database(tmp_path, monkeypatch):
    monkeypatch.setenv("MAIN_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("ADMIN_BOT_TOKEN", "456:def")
    monkeypatch.setenv("ADMIN_USER_ID", "123456")
    monkeypatch.setenv("ADMIN_PASSWORD", "strong-password")
    monkeypatch.setenv("DB_URL", f"sqlite+aiosqlite:///{tmp_path / 'old.db'}")

    import bot_package.config_loader as config_loader
    import bot_package.database as database
    from sqlalchemy import inspect, text

    importlib.reload(config_loader)
    database = importlib.reload(database)

    async with database.engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE users ("
                "id INTEGER PRIMARY KEY, telegram_id BIGINT UNIQUE NOT NULL, "
                "username VARCHAR, first_name VARCHAR NOT NULL, wallet_balance INTEGER, "
                "is_blocked BOOLEAN, created_at DATETIME)"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE purchases ("
                "id INTEGER PRIMARY KEY, user_id BIGINT NOT NULL, config_id INTEGER NOT NULL, "
                "volume_gb INTEGER NOT NULL, price INTEGER NOT NULL, purchased_at DATETIME)"
            )
        )

    from bot_package.services.schema_service import SchemaService

    await SchemaService.ensure_schema(database.engine)

    async with database.engine.begin() as conn:
        users_columns = await conn.run_sync(lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("users")})
        purchase_columns = await conn.run_sync(
            lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("purchases")}
        )

    await database.engine.dispose()

    assert {"referral_code", "referred_by_user_id", "referred_at"} <= users_columns
    assert {"original_price", "discount_amount", "coupon_id"} <= purchase_columns
