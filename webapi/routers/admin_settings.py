"""Admin: crypto / rial / trial settings, required channels, branded links."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bot_package.models import Admin, RequiredChannel
from bot_package.services.required_channel_service import RequiredChannelService
from bot_package.services.settings_service import SettingsService
from bot_package.services.subscription_link_service import SubscriptionLinkService

from ..deps import get_session, require_permission

router = APIRouter(prefix="/admin", tags=["admin"])


# --- Crypto settings ---------------------------------------------------------

@router.get("/settings/crypto")
async def get_crypto_settings(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    return {
        "rate_mode": await SettingsService.get_rate_mode(session),
        "margin_percent": await SettingsService.get_margin(session),
        "manual_rate_usdt": await SettingsService.get_manual_rate(session, "USDT"),
        "manual_rate_ton": await SettingsService.get_manual_rate(session, "TON"),
    }


class RateModeRequest(BaseModel):
    mode: str  # online | manual


class MarginRequest(BaseModel):
    percent: float = Field(ge=0)


class ManualRateRequest(BaseModel):
    coin: str  # USDT | TON
    toman_per_unit: int = Field(gt=0)


@router.put("/settings/crypto/rate-mode")
async def set_rate_mode(
    body: RateModeRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    if body.mode not in {"online", "manual"}:
        raise HTTPException(status_code=400, detail="mode must be online or manual")
    await SettingsService.set_rate_mode(session, body.mode)
    return {"rate_mode": body.mode}


@router.put("/settings/crypto/margin")
async def set_margin(
    body: MarginRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    await SettingsService.set_margin(session, body.percent)
    return {"margin_percent": body.percent}


@router.put("/settings/crypto/manual-rate")
async def set_manual_rate(
    body: ManualRateRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    coin = body.coin.upper()
    if coin not in {"USDT", "TON"}:
        raise HTTPException(status_code=400, detail="coin must be USDT or TON")
    await SettingsService.set_manual_rate(session, coin, body.toman_per_unit)
    return {"coin": coin, "toman_per_unit": body.toman_per_unit}


# --- Rial settings -----------------------------------------------------------

@router.get("/settings/rial")
async def get_rial_settings(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    return {
        "min_amount_toman": await SettingsService.get_rial_min_amount(session),
        "phone_required": await SettingsService.rial_phone_required(session),
        "support_handle": await SettingsService.get_rial_support_handle(session),
        "payment_mode": await SettingsService.get_rial_payment_mode(session),
        "destination_card_number": await SettingsService.get_rial_destination_card_number(session),
        "destination_card_holder": await SettingsService.get_rial_destination_card_holder(session),
        "receipt_valid_minutes": await SettingsService.get_rial_receipt_valid_minutes(session),
        "receipt_bot_username": await SettingsService.get_rial_receipt_bot_username(session),
        "receipt_admin_ids": await SettingsService.get_rial_receipt_admin_ids(session),
    }


@router.get("/settings/hooshpay")
async def get_hooshpay_settings(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    api_key = await SettingsService.get_hooshpay_api_key(session)
    api_secret = await SettingsService.get_hooshpay_api_secret(session)
    return {
        "enabled": await SettingsService.hooshpay_enabled(session),
        "min_amount_toman": await SettingsService.get_hooshpay_min_amount(session),
        "fee_mode": await SettingsService.get_hooshpay_fee_mode(session),
        "api_base_url": await SettingsService.get_hooshpay_api_base_url(session),
        "callback_base_url": await SettingsService.get_hooshpay_callback_base_url(session),
        "title": await SettingsService.get_hooshpay_title(session),
        "subtitle": await SettingsService.get_hooshpay_subtitle(session),
        "amount_label": await SettingsService.get_hooshpay_amount_label(session),
        "create_button": await SettingsService.get_hooshpay_create_button(session),
        "pay_button": await SettingsService.get_hooshpay_pay_button(session),
        "preset_amounts": await SettingsService.get_hooshpay_preset_amounts(session),
        "api_key_configured": bool(api_key),
        "api_secret_configured": bool(api_secret),
    }


class HooshPaySettingsRequest(BaseModel):
    enabled: bool | None = None
    min_amount_toman: int | None = Field(default=None, ge=1000)
    fee_mode: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    api_base_url: str | None = None
    callback_base_url: str | None = None
    title: str | None = None
    subtitle: str | None = None
    amount_label: str | None = None
    create_button: str | None = None
    pay_button: str | None = None
    preset_amounts: list[int] | None = None


@router.put("/settings/hooshpay")
async def set_hooshpay_settings(
    body: HooshPaySettingsRequest,
    session: AsyncSession = Depends(get_session),
    admin: Admin = Depends(require_permission("shop")),
):
    if body.enabled is not None:
        await SettingsService.set_hooshpay_enabled(session, body.enabled)
    if body.min_amount_toman is not None:
        await SettingsService.set_hooshpay_min_amount(session, body.min_amount_toman)
    if body.fee_mode is not None:
        if body.fee_mode not in {"seller", "buyer", "split"}:
            raise HTTPException(status_code=400, detail="fee_mode must be seller, buyer, or split")
        await SettingsService.set_hooshpay_fee_mode(session, body.fee_mode)
    if body.api_key is not None and body.api_key.strip():
        await SettingsService.set_hooshpay_api_key(session, body.api_key)
    if body.api_secret is not None and body.api_secret.strip():
        await SettingsService.set_hooshpay_api_secret(session, body.api_secret)
    if body.api_base_url is not None:
        await SettingsService.set_hooshpay_api_base_url(session, body.api_base_url)
    if body.callback_base_url is not None:
        await SettingsService.set_hooshpay_callback_base_url(session, body.callback_base_url)
    if body.title is not None:
        await SettingsService.set_hooshpay_title(session, body.title)
    if body.subtitle is not None:
        await SettingsService.set_hooshpay_subtitle(session, body.subtitle)
    if body.amount_label is not None:
        await SettingsService.set_hooshpay_amount_label(session, body.amount_label)
    if body.create_button is not None:
        await SettingsService.set_hooshpay_create_button(session, body.create_button)
    if body.pay_button is not None:
        await SettingsService.set_hooshpay_pay_button(session, body.pay_button)
    if body.preset_amounts is not None:
        await SettingsService.set_hooshpay_preset_amounts(session, body.preset_amounts)
    return await get_hooshpay_settings(session, admin)


class RialSettingsRequest(BaseModel):
    min_amount_toman: int | None = Field(default=None, ge=0)
    phone_required: bool | None = None
    support_handle: str | None = None
    payment_mode: str | None = None
    destination_card_number: str | None = None
    destination_card_holder: str | None = None
    receipt_valid_minutes: int | None = Field(default=None, ge=1)
    receipt_bot_username: str | None = None
    receipt_admin_ids: list[int] | None = None


@router.put("/settings/rial")
async def set_rial_settings(
    body: RialSettingsRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    if body.min_amount_toman is not None:
        await SettingsService.set_rial_min_amount(session, body.min_amount_toman)
    if body.phone_required is not None:
        await SettingsService.set_rial_phone_required(session, body.phone_required)
    if body.support_handle is not None:
        await SettingsService.set_rial_support_handle(session, body.support_handle)
    if body.payment_mode is not None:
        if body.payment_mode not in {"receipt_bot", "direct_support"}:
            raise HTTPException(status_code=400, detail="payment_mode must be receipt_bot or direct_support")
        await SettingsService.set_rial_payment_mode(session, body.payment_mode)
    if body.destination_card_number is not None:
        await SettingsService.set_rial_destination_card_number(session, body.destination_card_number)
    if body.destination_card_holder is not None:
        await SettingsService.set_rial_destination_card_holder(session, body.destination_card_holder)
    if body.receipt_valid_minutes is not None:
        await SettingsService.set_rial_receipt_valid_minutes(session, body.receipt_valid_minutes)
    if body.receipt_bot_username is not None:
        await SettingsService.set_rial_receipt_bot_username(session, body.receipt_bot_username)
    if body.receipt_admin_ids is not None:
        await SettingsService.set_rial_receipt_admin_ids(session, body.receipt_admin_ids)
    return await get_rial_settings(session, _admin)


# --- Trial settings ----------------------------------------------------------

@router.get("/settings/trial")
async def get_trial_settings(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    return {
        "enabled": await SettingsService.trial_enabled(session),
        "volume_mb": await SettingsService.get_trial_volume_mb(session),
        "duration_hours": await SettingsService.get_trial_duration_hours(session),
    }


class TrialSettingsRequest(BaseModel):
    enabled: bool | None = None
    volume_mb: int | None = Field(default=None, ge=0)
    duration_hours: int | None = Field(default=None, ge=0)


@router.put("/settings/trial")
async def set_trial_settings(
    body: TrialSettingsRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    if body.enabled is not None:
        await SettingsService.set_trial_enabled(session, body.enabled)
    if body.volume_mb is not None:
        await SettingsService.set_trial_volume_mb(session, body.volume_mb)
    if body.duration_hours is not None:
        await SettingsService.set_trial_duration_hours(session, body.duration_hours)
    return await get_trial_settings(session, _admin)


# --- Branded links -----------------------------------------------------------

class BrandedLinksRequest(BaseModel):
    enabled: bool


class SubscriptionProfileTitleRequest(BaseModel):
    title: str = ""


class SubscriptionDeviceLimitRequest(BaseModel):
    limit: int = Field(default=0, ge=0)


@router.get("/settings/branded-links")
async def get_branded_links(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    return {
        "enabled": await SettingsService.branded_links_enabled(session),
        "subscription_profile_title": await SettingsService.get_subscription_profile_title(session),
        "subscription_device_limit": await SettingsService.get_subscription_device_limit(session),
    }


@router.put("/settings/branded-links")
async def set_branded_links(
    body: BrandedLinksRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    await SettingsService.set_branded_links_enabled(session, body.enabled)
    return await get_branded_links(session, _admin)


@router.put("/settings/subscription-profile-title")
async def set_subscription_profile_title(
    body: SubscriptionProfileTitleRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    title = body.title.strip()
    await SettingsService.set_subscription_profile_title(session, title)
    limit = await SettingsService.get_subscription_device_limit(session)
    await SubscriptionLinkService.sync_panel_settings(title, subscription_device_limit=limit)
    return {"subscription_profile_title": title}


@router.put("/settings/subscription-device-limit")
async def set_subscription_device_limit(
    body: SubscriptionDeviceLimitRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    await SettingsService.set_subscription_device_limit(session, body.limit)
    title = await SettingsService.get_subscription_profile_title(session)
    await SubscriptionLinkService.sync_panel_settings(title, subscription_device_limit=body.limit)
    return {"subscription_device_limit": body.limit}


# --- Required channels -------------------------------------------------------

def _channel_out(c: RequiredChannel) -> dict:
    return {
        "id": c.id,
        "chat_id": c.chat_id,
        "title": c.title,
        "join_url": c.join_url,
        "is_active": c.is_active,
    }


class ChannelUpsertRequest(BaseModel):
    chat_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    join_url: str = Field(min_length=1)


@router.get("/required-channels")
async def list_channels(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    return [_channel_out(c) for c in await RequiredChannelService.list_channels(session)]


@router.post("/required-channels")
async def upsert_channel(
    body: ChannelUpsertRequest,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    channel = await RequiredChannelService.upsert_channel(
        session, body.chat_id, body.title, body.join_url
    )
    await session.commit()
    return _channel_out(channel)


@router.post("/required-channels/{channel_id}/toggle")
async def toggle_channel(
    channel_id: int,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    channel = await RequiredChannelService.toggle_channel(session, channel_id)
    await session.commit()
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return _channel_out(channel)


@router.delete("/required-channels/{channel_id}")
async def delete_channel(
    channel_id: int,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("shop")),
):
    ok = await RequiredChannelService.delete_channel(session, channel_id)
    await session.commit()
    if not ok:
        raise HTTPException(status_code=404, detail="Channel not found")
    return {"deleted": True}
