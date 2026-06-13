from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_package.models import Config, Purchase, Transaction, User
from bot_package.services.coupon_service import CouponError, CouponService
from bot_package.services.inventory_service import InventoryService
from bot_package.services.price_service import PriceService
from bot_package.services.referral_service import ReferralService
from bot_package.services.settings_service import SettingsService
from bot_package.services.shop_customization_service import ShopCustomizationService
from bot_package.services.subscription_link_service import SubscriptionLinkService

from ..deps import get_current_user, get_session
from ..schemas import (
    ApplyCouponRequest,
    CategoryOut,
    CouponOut,
    PlanOut,
    PurchaseOut,
    PurchaseRequest,
)

router = APIRouter(prefix="/shop", tags=["shop"])

# In-process idempotency guard: maps key -> purchase id. Replace with a DB
# table if the API ever runs multi-process.
_idempotency_cache: dict[str, int] = {}


async def _stock_counts(session: AsyncSession) -> dict[tuple[str, int], int]:
    rows = (
        await session.execute(
            select(Config.category_key, Config.volume_gb, func.count(Config.id))
            .where(Config.is_sold.is_(False))
            .group_by(Config.category_key, Config.volume_gb)
        )
    ).all()
    return {(category, volume): count for category, volume, count in rows}


@router.get("/plans", response_model=list[CategoryOut])
async def list_plans(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    categories = await ShopCustomizationService.list_categories(session, active_only=True)
    plans = await ShopCustomizationService.list_plans(session, active_only=True)
    coupon = await CouponService.get_active_coupon(session, user.telegram_id)
    stock = await _stock_counts(session)

    by_category: dict[str, list[PlanOut]] = {}
    for plan in plans:
        price = await PriceService.get_plan_price(session, plan)
        final_price, discount = (
            CouponService.calculate_discount(price, coupon) if price else (price, 0)
        )
        by_category.setdefault(plan.category_key, []).append(
            PlanOut(
                id=plan.id,
                volume_gb=plan.volume_gb,
                category_key=plan.category_key,
                title=plan.title,
                price=price,
                final_price=final_price,
                discount_amount=discount,
                emoji=plan.emoji,
                style=plan.style,
                display_order=plan.display_order,
                in_stock=stock.get((plan.category_key, plan.volume_gb), 0) > 0,
            )
        )

    result = []
    for category in categories:
        result.append(
            CategoryOut(
                key=category.key,
                title=category.title,
                emoji=category.emoji,
                display_order=category.display_order,
                plans=sorted(by_category.get(category.key, []), key=lambda p: p.display_order),
            )
        )
    # Plans whose category row is missing/inactive still belong to "default".
    orphan_keys = set(by_category) - {c.key for c in categories}
    for key in sorted(orphan_keys):
        result.append(
            CategoryOut(key=key, title=key, emoji=None, display_order=999, plans=by_category[key])
        )
    return result


@router.post("/coupons/apply", response_model=CouponOut)
async def apply_coupon(
    body: ApplyCouponRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        coupon = await CouponService.apply_coupon(session, user.telegram_id, body.code)
        await session.commit()
    except CouponError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return CouponOut(code=coupon.code, discount_type=coupon.discount_type, amount=coupon.amount)


@router.post("/purchases", response_model=PurchaseOut)
async def purchase(
    body: PurchaseRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    cache_key = f"{user.telegram_id}:{idempotency_key}" if idempotency_key else None
    if cache_key and cache_key in _idempotency_cache:
        existing = (
            await session.execute(
                select(Purchase).where(Purchase.id == _idempotency_cache[cache_key])
            )
        ).scalar_one_or_none()
        if existing is not None:
            return await _purchase_out(session, existing)

    plan = await ShopCustomizationService.get_plan(session, body.plan_id)
    if plan is None or not plan.is_active:
        raise HTTPException(status_code=404, detail="Plan not found")

    # Same flow as the bot's purchase handler: lock user row, price with
    # coupon, take one unsold config, debit wallet, record purchase.
    db_user = (
        await session.execute(
            select(User).where(User.telegram_id == user.telegram_id).with_for_update()
        )
    ).scalar_one()
    if db_user.is_blocked:
        raise HTTPException(status_code=403, detail="User is blocked")

    original_price = await PriceService.get_plan_price(session, plan)
    if not original_price:
        raise HTTPException(status_code=409, detail="Plan has no active price")

    coupon = await CouponService.get_active_coupon(session, db_user.telegram_id)
    final_price, discount_amount = CouponService.calculate_discount(original_price, coupon)

    if (db_user.wallet_balance or 0) < final_price:
        raise HTTPException(status_code=402, detail="Insufficient wallet balance")

    config = await InventoryService.get_available_config(session, plan.volume_gb, plan.category_key)
    if config is None:
        raise HTTPException(status_code=409, detail="Plan is out of stock")

    db_user.wallet_balance -= final_price
    sold = await InventoryService.sell_config(session, config, db_user.telegram_id)
    if not sold:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Plan is out of stock")

    purchase_row = Purchase(
        user_id=db_user.telegram_id,
        config_id=config.id,
        volume_gb=plan.volume_gb,
        category_key=plan.category_key,
        price=final_price,
        original_price=original_price,
        discount_amount=discount_amount,
        coupon_id=coupon.id if coupon else None,
        coupon_code=coupon.code if coupon else None,
        service_name=plan.title,
    )
    session.add(purchase_row)
    await session.flush()
    await CouponService.mark_active_coupon_redeemed(session, db_user.telegram_id, purchase_row.id)
    session.add(
        Transaction(
            user_id=db_user.telegram_id,
            amount=-final_price,
            type="purchase",
            description=f"Purchase {plan.volume_gb}GB - {plan.title} (webapp)",
        )
    )
    await session.commit()

    if await SettingsService.branded_links_enabled(session):
        await SubscriptionLinkService.public_link_for_config(session, config)
        await SubscriptionLinkService.sync_to_panel(config, plan.title)
        await session.commit()

    rewards = await ReferralService.evaluate_referred_user(session, db_user.telegram_id)
    await session.commit()
    for reward in rewards:
        if reward.get("config") is not None:
            await SubscriptionLinkService.sync_to_panel(reward["config"], reward["service_name"])

    if cache_key:
        _idempotency_cache[cache_key] = purchase_row.id
    return await _purchase_out(session, purchase_row)


@router.get("/purchases", response_model=list[PurchaseOut])
async def list_purchases(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    purchases = (
        (
            await session.execute(
                select(Purchase)
                .where(Purchase.user_id == user.telegram_id)
                .order_by(Purchase.purchased_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [await _purchase_out(session, p) for p in purchases]


async def _purchase_out(session: AsyncSession, purchase_row: Purchase) -> PurchaseOut:
    config = (
        await session.execute(select(Config).where(Config.id == purchase_row.config_id))
    ).scalar_one_or_none()
    sub_link = None
    if config is not None:
        if await SettingsService.branded_links_enabled(session):
            sub_link = await SubscriptionLinkService.public_link_for_config(session, config)
            await session.commit()
        else:
            sub_link = config.sub_link
    return PurchaseOut(
        id=purchase_row.id,
        volume_gb=purchase_row.volume_gb,
        category_key=purchase_row.category_key,
        price=purchase_row.price,
        original_price=purchase_row.original_price,
        discount_amount=purchase_row.discount_amount,
        coupon_code=purchase_row.coupon_code,
        service_name=purchase_row.service_name,
        purchased_at=purchase_row.purchased_at,
        sub_link=sub_link,
    )
