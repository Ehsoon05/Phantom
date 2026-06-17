"""Pydantic request/response models."""

from datetime import datetime

from pydantic import BaseModel, Field


# --- Auth -------------------------------------------------------------------

class TelegramAuthRequest(BaseModel):
    init_data: str = Field(min_length=1)
    start_param: str | None = None


class MeResponse(BaseModel):
    telegram_id: int
    first_name: str
    username: str | None
    wallet_balance: int
    referral_code: str | None
    trial_claimed: bool
    accepted_rules: bool
    phone_verified: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TelegramAuthResponse(TokenResponse):
    me: MeResponse


class AdminLoginRequest(BaseModel):
    telegram_id: int
    password: str = Field(min_length=1)


class AdminTokenResponse(TokenResponse):
    permissions: str
    is_owner: bool


# --- User -------------------------------------------------------------------

class PlanOut(BaseModel):
    id: int
    volume_gb: int
    volume_label: str
    category_key: str
    title: str
    price: int | None
    final_price: int | None
    discount_amount: int
    emoji: str | None
    style: str | None
    display_order: int
    in_stock: bool
    can_create: bool = False


class CategoryOut(BaseModel):
    key: str
    title: str
    emoji: str | None
    display_order: int
    plans: list[PlanOut]


class PurchaseRequest(BaseModel):
    plan_id: int


class PurchaseOut(BaseModel):
    id: int
    volume_gb: int
    volume_label: str
    category_key: str
    price: int
    original_price: int | None
    discount_amount: int
    coupon_code: str | None
    service_name: str | None
    purchased_at: datetime
    sub_link: str | None
    can_renew: bool = False
    renewal_price: int | None = None
    renewed_at: datetime | None = None


class RenewRequest(BaseModel):
    confirm: bool = True


class ApplyCouponRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class CouponOut(BaseModel):
    code: str
    discount_type: str
    amount: int


class TransactionOut(BaseModel):
    id: int
    amount: int
    type: str
    description: str | None
    created_at: datetime


class CryptoInvoiceRequest(BaseModel):
    coin_key: str
    amount_toman: int = Field(gt=0)


class CryptoInvoiceOut(BaseModel):
    id: int
    coin: str
    network: str
    deposit_address: str
    memo: str | None
    expected_crypto: str
    quoted_toman: int
    status: str
    created_at: datetime
    expires_at: datetime | None


class RialRequestIn(BaseModel):
    amount_toman: int = Field(gt=0)
    source_card: str = Field(min_length=16, max_length=19)


class RialRequestOut(BaseModel):
    id: int
    tracking_code: str
    amount_toman: int
    status: str
    support_handle: str
    request_text: str
    message_text: str | None = None
    copy_text: str | None = None
    send_url: str | None = None
    created_at: datetime


class ReferralsOut(BaseModel):
    referral_code: str
    referral_link: str
    share_text: str
    message_text: str
    total_referrals: int
    rules: list[dict]


# --- Admin ------------------------------------------------------------------

class AdminStatsOut(BaseModel):
    total_users: int
    new_users_today: int
    total_wallet_balance: int
    total_gb_purchased: int
    total_spent: int


class AdminUserOut(BaseModel):
    telegram_id: int
    first_name: str
    username: str | None
    wallet_balance: int
    is_blocked: bool
    referral_code: str | None
    created_at: datetime | None


class ChargeWalletRequest(BaseModel):
    amount: int


class SetBalanceRequest(BaseModel):
    balance: int = Field(ge=0)


class RialDecisionRequest(BaseModel):
    approve: bool
