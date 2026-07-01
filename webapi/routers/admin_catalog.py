"""Admin: inventory, shop plans/categories/prices, messages, buttons."""

import json
from urllib.parse import unquote, urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_package.models import Admin, Config, ProvisionPanel, ShopButton, ShopMessage, ShopPlan, ShopPlanCategory
from bot_package.services.inventory_service import InventoryService
from bot_package.services.price_service import PriceService
from bot_package.services.provisioning_service import ProvisioningService
from bot_package.services.shop_customization_service import ShopCustomizationService
from bot_package.services.subscription_link_service import SubscriptionLinkService

from ..deps import get_session, require_permission

router = APIRouter(prefix="/admin", tags=["admin"])


# --- Inventory ---------------------------------------------------------------

class ConfigsAddRequest(BaseModel):
    volume_gb: int = Field(ge=0)
    category_key: str = "default"
    plan_id: int | None = None
    links: list[str] = Field(min_length=1)


class ConfigUpdateRequest(BaseModel):
    sub_link: str | None = Field(default=None, min_length=8)
    subscription_device_limit: int | None = Field(default=None, ge=0)


def _config_name(sub_link: str) -> str:
    """A sub link's display name is the remark in its URL fragment
    (e.g. https://panel/sub/<token>#MyService -> "MyService")."""
    try:
        fragment = urlparse(sub_link).fragment
    except ValueError:
        return ""
    return unquote(fragment).strip()


def _config_out(config: Config) -> dict:
    return {
        "id": config.id,
        "plan_id": config.shop_plan_id,
        "volume_gb": config.volume_gb,
        "category_key": config.category_key,
        "name": _config_name(config.sub_link),
        "sub_link": config.sub_link,
        "public_sub_token": config.public_sub_token,
        "subscription_device_limit": config.subscription_device_limit,
        "created_at": config.created_at,
    }


async def _config_device_limit(session: AsyncSession, config: Config) -> int | None:
    if config.subscription_device_limit is not None:
        return max(0, int(config.subscription_device_limit or 0))
    if config.shop_plan_id:
        plan = await session.get(ShopPlan, config.shop_plan_id)
        if plan is not None:
            return max(0, int(plan.subscription_device_limit or 0))
    if config.panel_key:
        panel = (
            await session.execute(select(ProvisionPanel).where(ProvisionPanel.key == config.panel_key))
        ).scalar_one_or_none()
        return panel.hwid_limit if panel else None
    return None


@router.post("/inventory/configs")
async def add_configs(
    body: ConfigsAddRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("inventory")),
):
    plan = await ShopCustomizationService.get_plan(session, body.plan_id) if body.plan_id else None
    if plan is None and body.plan_id is None:
        plan = await ShopCustomizationService.get_plan_by_product(
            session, body.volume_gb, body.category_key
        )
    if body.plan_id and plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    added = await InventoryService.add_configs(
        session,
        plan.volume_gb if plan else body.volume_gb,
        body.links,
        plan.category_key if plan else body.category_key,
        plan.id if plan else None,
    )
    await session.commit()
    return {"added": added}


@router.get("/inventory/stock")
async def stock(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("inventory")),
):
    rows = await InventoryService.get_stock_status(session)
    return [
        {"plan_id": plan_id, "category_key": c, "volume_gb": v, "title": t, "available": n}
        for plan_id, c, v, t, n in rows
    ]


@router.get("/inventory/configs")
async def list_inventory_configs(
    category_key: str | None = None,
    volume_gb: int | None = None,
    q: str | None = None,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("inventory")),
):
    query = select(Config).where(Config.is_sold.is_(False))
    if category_key:
        query = query.where(Config.category_key == category_key)
    if volume_gb is not None:
        query = query.where(Config.volume_gb == volume_gb)
    if q:
        # The sub link contains both the URL and the #remark name, so a
        # substring match covers searching by link and by name.
        query = query.where(Config.sub_link.ilike(f"%{q.strip()}%"))
    configs = (
        await session.execute(query.order_by(Config.created_at.desc(), Config.id.desc()).limit(250))
    ).scalars().all()
    return [_config_out(config) for config in configs]


@router.patch("/inventory/configs/{config_id}")
async def replace_inventory_config(
    config_id: int,
    body: ConfigUpdateRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("inventory")),
):
    config = (
        await session.execute(select(Config).where(Config.id == config_id))
    ).scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="Config not found")
    if config.is_sold:
        raise HTTPException(status_code=409, detail="Sold configs cannot be replaced")

    if body.sub_link is not None:
        sub_link = body.sub_link.strip()
        parsed = urlparse(sub_link)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise HTTPException(status_code=400, detail="Subscription link must be a valid HTTP(S) URL")

        duplicate = (
            await session.execute(
                select(Config.id).where(Config.sub_link == sub_link, Config.id != config.id)
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="This subscription link already exists")

        config.sub_link = sub_link
    if body.subscription_device_limit is not None:
        config.subscription_device_limit = max(0, int(body.subscription_device_limit))
    await SubscriptionLinkService.ensure_public_token(session, config)
    device_limit = await _config_device_limit(session, config)
    await session.commit()
    await SubscriptionLinkService.sync_to_panel(config, device_limit=device_limit)
    return _config_out(config)


@router.delete("/inventory/configs/{config_id}")
async def delete_inventory_config(
    config_id: int,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("inventory")),
):
    config = (
        await session.execute(select(Config).where(Config.id == config_id))
    ).scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="Config not found")
    if config.is_sold:
        raise HTTPException(status_code=409, detail="Sold configs cannot be deleted from inventory")
    await session.delete(config)
    await session.commit()
    return {"deleted": True}


# --- Plans -------------------------------------------------------------------

def _plan_out(plan: ShopPlan, stock_count: int | None = None) -> dict:
    return {
        "id": plan.id,
        "volume_gb": plan.volume_gb,
        "category_key": plan.category_key,
        "title": plan.title,
        "price": plan.price,
        "emoji": plan.emoji,
        "style": plan.style,
        "display_order": plan.display_order,
        "duration_days": plan.duration_days,
        "provision_volume_gb": plan.provision_volume_gb,
        "provision_duration_days": plan.provision_duration_days,
        "provision_time_mode": plan.provision_time_mode,
        "subscription_device_limit": plan.subscription_device_limit,
        "show_subscription_configs": plan.show_subscription_configs,
        "name_prefix": plan.name_prefix,
        "provision_mode": plan.provision_mode,
        "provision_panel_key": plan.provision_panel_key,
        "provision_enabled": plan.provision_enabled,
        "renew_enabled": plan.renew_enabled,
        "is_active": plan.is_active,
        "stock": stock_count,
    }


class PlanUpsertRequest(BaseModel):
    volume_gb: int = Field(ge=0)
    title: str
    price: int | None = None
    category_key: str = "default"
    emoji: str | None = "📦"
    style: str | None = None
    duration_days: int = 30
    provision_volume_gb: int | None = None
    provision_duration_days: int | None = None
    provision_time_mode: str = "on_hold"
    subscription_device_limit: int = 0
    show_subscription_configs: bool = True
    name_prefix: str | None = None
    provision_mode: str = "inventory"
    provision_panel_key: str | None = None
    provision_enabled: bool = False
    renew_enabled: bool = True


class PlanUpdateRequest(BaseModel):
    title: str | None = None
    price: int | None = None
    emoji: str | None = None
    style: str | None = None
    category_key: str | None = None
    display_order: int | None = None
    duration_days: int | None = None
    provision_volume_gb: int | None = None
    provision_duration_days: int | None = None
    provision_time_mode: str | None = None
    subscription_device_limit: int | None = None
    show_subscription_configs: bool | None = None
    name_prefix: str | None = None
    provision_mode: str | None = None
    provision_panel_key: str | None = None
    provision_enabled: bool | None = None
    renew_enabled: bool | None = None
    is_active: bool | None = None


@router.get("/plans")
async def list_plans(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("prices")),
):
    plans = await ShopCustomizationService.list_plans(session, active_only=False)
    stock_rows = await InventoryService.get_stock_status(session)
    stock = {plan_id: count for plan_id, _c, _v, _t, count in stock_rows}
    return [_plan_out(p, stock.get(p.id, 0)) for p in plans]


@router.post("/plans")
async def upsert_plan(
    body: PlanUpsertRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("prices")),
):
    plan = await ShopCustomizationService.create_plan(
        session,
        volume_gb=body.volume_gb,
        title=body.title,
        price=body.price,
        category_key=body.category_key,
        emoji=body.emoji,
        style=body.style or "success",
    )
    plan.duration_days = body.duration_days
    plan.provision_volume_gb = body.provision_volume_gb
    plan.provision_duration_days = body.provision_duration_days
    plan.provision_time_mode = body.provision_time_mode
    plan.subscription_device_limit = max(0, int(body.subscription_device_limit or 0))
    plan.show_subscription_configs = bool(body.show_subscription_configs)
    plan.name_prefix = body.name_prefix
    plan.provision_mode = body.provision_mode
    plan.provision_panel_key = body.provision_panel_key
    plan.provision_enabled = body.provision_enabled
    plan.renew_enabled = body.renew_enabled
    await session.commit()
    return _plan_out(plan)


@router.patch("/plans/{plan_id}")
async def update_plan(
    plan_id: int,
    body: PlanUpdateRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("prices")),
):
    values = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
    if "subscription_device_limit" in values and values["subscription_device_limit"] is not None:
        values["subscription_device_limit"] = max(0, int(values["subscription_device_limit"]))
    plan = await ShopCustomizationService.update_plan(session, plan_id, **values)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return _plan_out(plan)


@router.delete("/plans/{plan_id}")
async def delete_plan(
    plan_id: int,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("prices")),
):
    result = await ShopCustomizationService.delete_plan(session, plan_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"deleted": True}


# --- Categories --------------------------------------------------------------

def _category_out(c: ShopPlanCategory) -> dict:
    return {
        "id": c.id,
        "key": c.key,
        "title": c.title,
        "emoji": c.emoji,
        "style": c.style,
        "provision_panel_key": c.provision_panel_key,
        "provision_enabled": c.provision_enabled,
        "display_order": c.display_order,
        "is_active": c.is_active,
    }


class CategoryUpsertRequest(BaseModel):
    key: str
    title: str | None = None


class CategoryUpdateRequest(BaseModel):
    title: str | None = None
    emoji: str | None = None
    style: str | None = None
    provision_panel_key: str | None = None
    provision_enabled: bool | None = None
    display_order: int | None = None
    is_active: bool | None = None


@router.get("/categories")
async def list_categories(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("prices")),
):
    return [_category_out(c) for c in await ShopCustomizationService.list_categories(session)]


# --- Provision panels --------------------------------------------------------

def _panel_out(panel: ProvisionPanel) -> dict:
    return {
        "key": panel.key,
        "title": panel.title,
        "panel_type": panel.panel_type,
        "base_url": panel.base_url,
        "group_ids": json.loads(panel.group_ids or "[]"),
        "inbounds": json.loads(panel.inbounds_json or "{}"),
        "protocols": json.loads(panel.protocols_json or "[]"),
        "hwid_limit": panel.hwid_limit,
        "is_enabled": panel.is_enabled,
    }


class PanelUpsertRequest(BaseModel):
    key: str
    title: str
    panel_type: str = "marzban"
    base_url: str
    username: str
    password: str
    group_ids: list[int] = []
    inbounds: dict[str, list[str]] = {}
    protocols: list[str] = []
    hwid_limit: int | None = None
    is_enabled: bool = True


@router.get("/provision/panels")
async def list_provision_panels(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    await ProvisioningService.ensure_env_panels(session)
    panels = (await session.execute(select(ProvisionPanel).order_by(ProvisionPanel.id))).scalars().all()
    return [_panel_out(panel) for panel in panels]


@router.put("/provision/panels/{key}")
async def upsert_provision_panel(
    key: str,
    body: PanelUpsertRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    panel = (
        await session.execute(select(ProvisionPanel).where(ProvisionPanel.key == key))
    ).scalar_one_or_none()
    if panel is None:
        panel = ProvisionPanel(key=key, title=body.title, base_url=body.base_url, username=body.username, password=body.password)
        session.add(panel)
    panel.title = body.title
    panel.panel_type = body.panel_type
    panel.base_url = body.base_url.rstrip("/")
    panel.username = body.username
    panel.password = body.password
    panel.group_ids = json.dumps(body.group_ids)
    panel.inbounds_json = json.dumps(body.inbounds)
    panel.protocols_json = json.dumps(body.protocols)
    panel.hwid_limit = body.hwid_limit
    panel.is_enabled = body.is_enabled
    await session.commit()
    return _panel_out(panel)


@router.post("/categories")
async def upsert_category(
    body: CategoryUpsertRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("prices")),
):
    category = await ShopCustomizationService.ensure_category(session, body.key, body.title)
    await session.commit()
    return _category_out(category)


@router.patch("/categories/{key}")
async def update_category(
    key: str,
    body: CategoryUpdateRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("prices")),
):
    category = await ShopCustomizationService.update_category(
        session, key, **body.model_dump(exclude_none=True)
    )
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return _category_out(category)


@router.delete("/categories/{key}")
async def delete_category(
    key: str,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("prices")),
):
    ok = await ShopCustomizationService.delete_category(session, key)
    if not ok:
        raise HTTPException(status_code=409, detail="Category not found or still in use")
    return {"deleted": True}


# --- Prices (legacy + plan price) -------------------------------------------

class PriceUpdateRequest(BaseModel):
    price: int = Field(ge=0)


@router.post("/plans/{plan_id}/price")
async def set_plan_price(
    plan_id: int,
    body: PriceUpdateRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("prices")),
):
    plan = await ShopCustomizationService.update_plan(session, plan_id, price=body.price)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return _plan_out(plan)


# --- Shop messages -----------------------------------------------------------

def _message_out(m: ShopMessage) -> dict:
    return {"key": m.key, "text": m.text, "parse_mode": m.parse_mode, "is_active": m.is_active}


class MessageUpdateRequest(BaseModel):
    text: str
    parse_mode: str = "Markdown"


@router.get("/shop/messages")
async def list_messages(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    return [_message_out(m) for m in await ShopCustomizationService.list_messages(session)]


@router.put("/shop/messages/{key}")
async def update_message(
    key: str,
    body: MessageUpdateRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    message = await ShopCustomizationService.update_message(session, key, body.text, body.parse_mode)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")
    return _message_out(message)


# --- Shop buttons ------------------------------------------------------------

def _button_out(b: ShopButton) -> dict:
    return {
        "id": b.id,
        "menu": b.menu,
        "action": b.action,
        "text": b.text,
        "emoji": b.emoji,
        "style": b.style,
        "row": b.row,
        "col": b.col,
        "is_enabled": b.is_enabled,
    }


class ButtonUpdateRequest(BaseModel):
    text: str | None = None
    emoji: str | None = None
    style: str | None = None
    row: int | None = None
    col: int | None = None
    is_enabled: bool | None = None


@router.get("/shop/buttons")
async def list_buttons(
    menu: str | None = None,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    return [_button_out(b) for b in await ShopCustomizationService.list_buttons(session, menu)]


@router.patch("/shop/buttons/{button_id}")
async def update_button(
    button_id: int,
    body: ButtonUpdateRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    button = await ShopCustomizationService.update_button(
        session, button_id, **body.model_dump(exclude_none=True)
    )
    if button is None:
        raise HTTPException(status_code=404, detail="Button not found")
    return _button_out(button)


@router.delete("/shop/buttons/{button_id}")
async def delete_button(
    button_id: int,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    ok = await ShopCustomizationService.delete_button(session, button_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Button not found")
    await session.commit()
    return {"deleted": True}


@router.post("/shop/reset")
async def reset_shop_defaults(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    await ShopCustomizationService.reset_defaults(session)
    return {"reset": True}
