from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, ForeignKey
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
    volume_gb = Column(Integer, nullable=False)
    sub_link = Column(String, nullable=False, unique=True)
    is_sold = Column(Boolean, default=False)
    sold_to_user_id = Column(BigInteger, nullable=True)
    sold_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    purchases = relationship("Purchase", back_populates="config")

class Purchase(Base):
    __tablename__ = "purchases"
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    config_id = Column(Integer, ForeignKey("configs.id"), nullable=False)
    volume_gb = Column(Integer, nullable=False)
    price = Column(Integer, nullable=False)
    original_price = Column(Integer, nullable=True)
    discount_amount = Column(Integer, nullable=False, default=0)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=True)
    purchased_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user = relationship("User", back_populates="purchases")
    config = relationship("Config", back_populates="purchases")
    coupon = relationship("Coupon", back_populates="purchases")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    amount = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

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
