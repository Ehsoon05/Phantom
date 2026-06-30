from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime, timezone

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=False)
    wallet_balance = Column(Integer, default=0)
    is_blocked = Column(Boolean, default=False)
    referral_code = Column(String, unique=True, nullable=True)
    referred_by_user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=True)
    referred_at = Column(DateTime, nullable=True)
    accepted_rules_at = Column(DateTime, nullable=True)
    trial_claimed_at = Column(DateTime, nullable=True)
    trial_panel_username = Column(String, nullable=True)
    verified_phone_number = Column(String, nullable=True)
    phone_verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    purchases = relationship("Purchase", back_populates="user")
    referrals = relationship(
        "User",
        primaryjoin="User.telegram_id == foreign(User.referred_by_user_id)",
        viewonly=True,
    )

class Config(Base):
    __tablename__ = "configs"
    id = Column(Integer, primary_key=True)
    shop_plan_id = Column(Integer, ForeignKey("shop_plans.id"), nullable=True, index=True)
    volume_gb = Column(Integer, nullable=False)
    category_key = Column(String, nullable=False, default="default")
    sub_link = Column(String, nullable=False, unique=True)
    public_sub_token = Column(String, nullable=True, unique=True)
    panel_key = Column(String, nullable=True)
    panel_username = Column(String, nullable=True)
    provision_source = Column(String, nullable=False, default="inventory")
    is_sold = Column(Boolean, default=False)
    sold_to_user_id = Column(BigInteger, nullable=True)
    sold_at = Column(DateTime, nullable=True)
    expired_detected_at = Column(DateTime, nullable=True)
    deletion_due_at = Column(DateTime, nullable=True)
    panel_deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    purchases = relationship("Purchase", back_populates="config")

class Purchase(Base):
    __tablename__ = "purchases"
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    config_id = Column(Integer, ForeignKey("configs.id"), nullable=False)
    volume_gb = Column(Integer, nullable=False)
    category_key = Column(String, nullable=False, default="default")
    price = Column(Integer, nullable=False)
    original_price = Column(Integer, nullable=True)
    discount_amount = Column(Integer, nullable=False, default=0)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=True)
    coupon_code = Column(String, nullable=True)
    service_name = Column(String, nullable=True)
    kind = Column(String, nullable=False, default="purchase")
    provision_source = Column(String, nullable=False, default="inventory")
    renewed_at = Column(DateTime, nullable=True)
    renews_purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=True)
    purchased_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user = relationship("User", back_populates="purchases")
    config = relationship("Config", back_populates="purchases")
    coupon = relationship("Coupon", back_populates="purchases")


class ServiceReminderLog(Base):
    __tablename__ = "service_reminder_logs"
    __table_args__ = (
        UniqueConstraint("purchase_id", "rule_key", name="uq_service_reminder_purchase_rule"),
    )

    id = Column(Integer, primary_key=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=False)
    config_id = Column(Integer, ForeignKey("configs.id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    rule_key = Column(String, nullable=False)
    remaining_percent = Column(Integer, nullable=True)
    remaining_seconds = Column(Integer, nullable=True)
    sent_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    purchase = relationship("Purchase")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    amount = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ReferralRewardRule(Base):
    __tablename__ = "referral_reward_rules"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    qualification_type = Column(String, nullable=False)
    required_count = Column(Integer, nullable=False, default=1)
    is_repeatable = Column(Boolean, nullable=False, default=False)
    reward_type = Column(String, nullable=False)
    wallet_amount = Column(Integer, nullable=True)
    shop_plan_id = Column(Integer, ForeignKey("shop_plans.id"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    shop_plan = relationship("ShopPlan")
    grants = relationship("ReferralRewardGrant", back_populates="rule", cascade="all, delete-orphan")


class ReferralRewardGrant(Base):
    __tablename__ = "referral_reward_grants"
    __table_args__ = (
        UniqueConstraint("rule_id", "referrer_user_id", "milestone_count", name="uq_referral_reward_grant"),
    )

    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey("referral_reward_rules.id"), nullable=False)
    referrer_user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    milestone_count = Column(Integer, nullable=False)
    qualified_count = Column(Integer, nullable=False)
    reward_type = Column(String, nullable=False)
    wallet_amount = Column(Integer, nullable=True)
    config_id = Column(Integer, ForeignKey("configs.id"), nullable=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=True)
    granted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    rule = relationship("ReferralRewardRule", back_populates="grants")

class Price(Base):
    __tablename__ = "prices"
    id = Column(Integer, primary_key=True)
    volume_gb = Column(Integer, unique=True, nullable=False)
    price = Column(Integer, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    permissions = Column(String, nullable=False, default="")
    is_owner = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Coupon(Base):
    __tablename__ = "coupons"
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, nullable=False)
    discount_type = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    applies_to_all = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    targets = relationship("CouponTarget", back_populates="coupon", cascade="all, delete-orphan")
    redemptions = relationship("CouponRedemption", back_populates="coupon", cascade="all, delete-orphan")
    purchases = relationship("Purchase", back_populates="coupon")


class CouponTarget(Base):
    __tablename__ = "coupon_targets"
    id = Column(Integer, primary_key=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=False)
    user_id = Column(BigInteger, nullable=False)
    coupon = relationship("Coupon", back_populates="targets")


class CouponRedemption(Base):
    __tablename__ = "coupon_redemptions"
    id = Column(Integer, primary_key=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    is_active = Column(Boolean, default=True)
    applied_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    redeemed_at = Column(DateTime, nullable=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=True)
    coupon = relationship("Coupon", back_populates="redemptions")


class RequiredChannel(Base):
    __tablename__ = "required_channels"
    id = Column(Integer, primary_key=True)
    chat_id = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    join_url = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ShopMessage(Base):
    __tablename__ = "shop_messages"
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    text = Column(Text, nullable=False)
    parse_mode = Column(String, nullable=True, default="Markdown")
    photo_file_id = Column(String, nullable=True)
    premium_emoji_id = Column(String, nullable=True)
    premium_emoji_position = Column(String, nullable=False, default="none")
    response_button_type = Column(String, nullable=False, default="text")
    response_button_text = Column(String, nullable=True)
    response_button_url = Column(String, nullable=True)
    response_button_style = Column(String, nullable=True)
    response_button_premium_emoji_id = Column(String, nullable=True)
    response_button_source_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ShopButton(Base):
    __tablename__ = "shop_buttons"
    id = Column(Integer, primary_key=True)
    action = Column(String, nullable=False)
    menu = Column(String, nullable=False)
    text = Column(String, nullable=False)
    emoji = Column(String, nullable=True)
    premium_emoji_id = Column(String, nullable=True)
    premium_emoji_position = Column(String, nullable=False, default="left")
    emoji_position = Column(String, nullable=False, default="left")
    style = Column(String, nullable=True)
    row = Column(Integer, nullable=False, default=0)
    col = Column(Integer, nullable=False, default=0)
    is_enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ShopPlan(Base):
    __tablename__ = "shop_plans"
    id = Column(Integer, primary_key=True)
    volume_gb = Column(Integer, nullable=False)
    category_key = Column(String, nullable=False, default="default")
    title = Column(String, nullable=False)
    price = Column(Integer, nullable=True)
    emoji = Column(String, nullable=True)
    premium_emoji_id = Column(String, nullable=True)
    premium_emoji_position = Column(String, nullable=False, default="left")
    emoji_position = Column(String, nullable=False, default="left")
    style = Column(String, nullable=True, default="success")
    display_order = Column(Integer, nullable=False, default=0)
    duration_days = Column(Integer, nullable=False, default=30)
    provision_volume_gb = Column(Integer, nullable=True)
    provision_duration_days = Column(Integer, nullable=True)
    provision_time_mode = Column(String, nullable=False, default="on_hold")
    subscription_device_limit = Column(Integer, nullable=False, default=0)
    name_prefix = Column(String, nullable=True)
    provision_mode = Column(String, nullable=False, default="inventory")
    provision_panel_key = Column(String, nullable=True)
    provision_enabled = Column(Boolean, nullable=False, default=False)
    renew_enabled = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ShopPlanCategory(Base):
    __tablename__ = "shop_plan_categories"
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    emoji = Column(String, nullable=True)
    premium_emoji_id = Column(String, nullable=True)
    emoji_position = Column(String, nullable=False, default="left")
    style = Column(String, nullable=True, default="primary")
    provision_panel_key = Column(String, nullable=True)
    provision_enabled = Column(Boolean, nullable=False, default=False)
    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class BotSetting(Base):
    """Generic key/value store for runtime-tunable settings (e.g. crypto rate mode)."""
    __tablename__ = "bot_settings"
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ProvisionPanel(Base):
    __tablename__ = "provision_panels"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    panel_type = Column(String, nullable=False, default="marzban")
    base_url = Column(String, nullable=False)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)
    group_ids = Column(Text, nullable=True)
    inbounds_json = Column(Text, nullable=True)
    protocols_json = Column(Text, nullable=True)
    hwid_limit = Column(Integer, nullable=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class RialPaymentRequest(Base):
    __tablename__ = "rial_payment_requests"

    id = Column(Integer, primary_key=True)
    tracking_code = Column(String, unique=True, nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    amount_toman = Column(Integer, nullable=False)
    phone_number = Column(String, nullable=True)
    source_card = Column(String, nullable=False)
    support_handle = Column(String, nullable=False)
    request_text = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User")


class CryptoInvoice(Base):
    """A single crypto top-up request and its on-chain settlement state.

    Attribution:
      - TRC-20: a unique ``deposit_address`` per invoice identifies the payer.
      - TON:    a shared address + unique ``memo`` per invoice identifies the payer.
    """
    __tablename__ = "crypto_invoices"
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    coin = Column(String, nullable=False)            # USDT | TON
    network = Column(String, nullable=False)         # TRC20 | TON
    deposit_address = Column(String, nullable=False)
    memo = Column(String, nullable=True)             # TON comment/tag; null for TRC-20
    address_index = Column(Integer, nullable=True)   # HD derivation index for TRC-20

    # Amounts: crypto stored as string to avoid float rounding; toman as integer.
    expected_crypto = Column(String, nullable=False)
    quoted_toman = Column(Integer, nullable=False)
    locked_rate = Column(String, nullable=False)     # toman per 1 coin unit, at creation
    rate_source = Column(String, nullable=True)      # online | manual

    status = Column(String, nullable=False, default="pending")  # pending|paid|confirmed|credited|expired|underpaid|error
    from_address = Column(String, nullable=True)     # on-chain sender, filled on detection
    received_crypto = Column(String, nullable=True)  # actual amount seen on-chain
    tx_hash = Column(String, unique=True, nullable=True)  # UNIQUE => credit idempotency
    confirmations = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)
    credited_at = Column(DateTime, nullable=True)

    user = relationship("User")
