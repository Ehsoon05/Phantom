from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Config, Purchase, ShopPlan, ShopPlanCategory, Transaction, User
from .coupon_service import CouponService
from .inventory_service import InventoryService
from .price_service import PriceService
from .provisioning_service import ProvisioningError, ProvisioningService
from .settings_service import SettingsService
from .shop_customization_service import ShopCustomizationService
from .subscription_link_service import SubscriptionLinkService


class PurchaseError(RuntimeError):
    status_code = 400


class PlanNotFound(PurchaseError):
    status_code = 404


class PlanUnavailable(PurchaseError):
    status_code = 409


class InsufficientBalance(PurchaseError):
    status_code = 402


class UserBlocked(PurchaseError):
    status_code = 403


@dataclass
class PurchaseResult:
    purchase: Purchase
    config: Config
    sub_link: str
    source: str


async def _public_or_raw_link(session: AsyncSession, config: Config, service_name: str | None) -> str:
    if await SettingsService.branded_links_enabled(session):
        sub_link = await SubscriptionLinkService.public_link_for_config(session, config)
        await SubscriptionLinkService.sync_to_panel(config, service_name)
        return sub_link
    return config.sub_link


async def _create_panel_config(
    session: AsyncSession,
    plan: ShopPlan,
    user_id: int,
    service_name: str | None,
) -> Config:
    try:
        provisioned = await ProvisioningService.create_for_plan(
            session,
            plan,
            service_name=service_name,
        )
    except ProvisioningError as exc:
        raise PlanUnavailable(str(exc)) from exc

    config = Config(
        shop_plan_id=plan.id,
        volume_gb=plan.volume_gb,
        category_key=plan.category_key,
        sub_link=provisioned.subscription_url,
        panel_key=provisioned.panel_key,
        panel_username=provisioned.username,
        provision_source="panel",
        is_sold=True,
        sold_to_user_id=user_id,
        sold_at=datetime.now(timezone.utc),
    )
    session.add(config)
    await session.flush()
    return config


async def purchase_plan(
    session: AsyncSession,
    *,
    telegram_id: int,
    plan_id: int,
    service_name: str | None,
    source_label: str,
) -> PurchaseResult:
    plan = await ShopCustomizationService.get_plan(session, plan_id)
    if plan is None or not plan.is_active:
        raise PlanNotFound("Plan not found")

    user = (
        await session.execute(
            select(User).where(User.telegram_id == telegram_id).with_for_update()
        )
    ).scalar_one()
    if user.is_blocked:
        raise UserBlocked("User is blocked")

    original_price = await PriceService.get_plan_price(session, plan)
    if not original_price:
        raise PlanUnavailable("Plan has no active price")

    coupon = await CouponService.get_active_coupon(session, user.telegram_id)
    final_price, discount_amount = CouponService.calculate_discount(original_price, coupon)
    if (user.wallet_balance or 0) < final_price:
        raise InsufficientBalance("موجودی کیف پول کافی نیست")

    category = (
        await session.execute(
            select(ShopPlanCategory).where(ShopPlanCategory.key == plan.category_key)
        )
    ).scalar_one_or_none()
    config = None
    source = "inventory"
    if plan.provision_mode != "panel_only":
        config = await InventoryService.get_available_config(
            session, plan.volume_gb, plan.category_key, plan.id
        )
    if config is not None:
        sold = await InventoryService.sell_config(session, config, user.telegram_id)
        if not sold:
            await session.rollback()
            raise PlanUnavailable("Plan is out of stock")
        config.provision_source = config.provision_source or "inventory"
        if not config.panel_username:
            config.panel_username = config.panel_username or None
    elif (
        plan.provision_mode in {"panel_only", "inventory_then_panel"}
        and ProvisioningService.plan_provision_enabled(plan, category)
    ):
        config = await _create_panel_config(session, plan, user.telegram_id, service_name)
        source = "panel"
    else:
        raise PlanUnavailable("Plan is out of stock")

    if not config.panel_username:
        from .provisioning_service import username_from_subscription_url

        config.panel_username = username_from_subscription_url(config.sub_link)
    if not config.panel_key:
        panel = await ProvisioningService.panel_for_plan(session, plan)
        config.panel_key = panel.key if panel else None

    user.wallet_balance -= final_price
    purchase = Purchase(
        user_id=user.telegram_id,
        config_id=config.id,
        volume_gb=plan.volume_gb,
        category_key=plan.category_key,
        price=final_price,
        original_price=original_price,
        discount_amount=discount_amount,
        coupon_id=coupon.id if coupon else None,
        coupon_code=coupon.code if coupon else None,
        service_name=service_name or plan.title,
        kind="purchase",
        provision_source=source,
    )
    session.add(purchase)
    await session.flush()
    await CouponService.mark_active_coupon_redeemed(session, user.telegram_id, purchase.id)
    session.add(
        Transaction(
            user_id=user.telegram_id,
            amount=-final_price,
            type="purchase",
            description=f"Purchase {plan.volume_gb}GB - {service_name or plan.title} ({source_label})",
        )
    )
    await session.commit()

    sub_link = await _public_or_raw_link(session, config, purchase.service_name)
    await session.commit()
    return PurchaseResult(purchase=purchase, config=config, sub_link=sub_link, source=source)


async def renew_purchase(
    session: AsyncSession,
    *,
    telegram_id: int,
    purchase_id: int,
    source_label: str,
) -> PurchaseResult:
    purchase = (
        await session.execute(
            select(Purchase)
            .options(selectinload(Purchase.config))
            .where(
                Purchase.id == purchase_id,
                Purchase.user_id == telegram_id,
                Purchase.kind == "purchase",
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if purchase is None or purchase.config is None:
        raise PlanNotFound("Purchase not found")

    plan = await ShopCustomizationService.get_plan(session, purchase.config.shop_plan_id)
    if plan is None or not plan.is_active or not plan.renew_enabled:
        raise PlanUnavailable("Renewal is not available for this service")

    user = (
        await session.execute(
            select(User).where(User.telegram_id == telegram_id).with_for_update()
        )
    ).scalar_one()
    if user.is_blocked:
        raise UserBlocked("User is blocked")

    original_price = await PriceService.get_plan_price(session, plan)
    if not original_price:
        raise PlanUnavailable("Plan has no active price")
    if (user.wallet_balance or 0) < original_price:
        raise InsufficientBalance("موجودی کیف پول کافی نیست")

    try:
        await ProvisioningService.renew_config(session, purchase.config, plan)
    except ProvisioningError as exc:
        raise PlanUnavailable(str(exc)) from exc

    user.wallet_balance -= original_price
    now = datetime.now(timezone.utc)
    purchase.renewed_at = now
    renewal = Purchase(
        user_id=user.telegram_id,
        config_id=purchase.config_id,
        volume_gb=plan.volume_gb,
        category_key=plan.category_key,
        price=original_price,
        original_price=original_price,
        discount_amount=0,
        service_name=purchase.service_name or plan.title,
        kind="renewal",
        provision_source=purchase.config.provision_source or "panel",
        renews_purchase_id=purchase.id,
    )
    session.add(renewal)
    session.add(
        Transaction(
            user_id=user.telegram_id,
            amount=-original_price,
            type="renewal",
            description=f"Renew {plan.volume_gb}GB - {purchase.service_name or plan.title} ({source_label})",
        )
    )
    await session.commit()
    sub_link = await _public_or_raw_link(session, purchase.config, purchase.service_name)
    await session.commit()
    return PurchaseResult(
        purchase=purchase,
        config=purchase.config,
        sub_link=sub_link,
        source=purchase.config.provision_source or "panel",
    )
