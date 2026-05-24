from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Coupon, CouponRedemption, CouponTarget


class CouponError(ValueError):
    pass


class CouponService:
    @staticmethod
    def normalize_code(code: str) -> str:
        return code.strip().upper()

    @staticmethod
    def calculate_discount(price: int, coupon: Coupon | None) -> tuple[int, int]:
        if not coupon:
            return price, 0
        if coupon.discount_type == "percent":
            discount = price * coupon.amount // 100
        else:
            discount = coupon.amount
        discount = max(0, min(price, discount))
        return price - discount, discount

    @staticmethod
    async def create_coupon(
        session: AsyncSession,
        *,
        code: str,
        discount_type: str,
        amount: int,
        created_by: int,
        target_user_ids: list[int] | None = None,
    ) -> Coupon:
        code = CouponService.normalize_code(code)
        discount_type = discount_type.strip().lower()
        target_user_ids = list(dict.fromkeys(target_user_ids or []))

        if not code:
            raise CouponError("coupon code is required")
        if discount_type not in {"percent", "fixed"}:
            raise CouponError("discount type must be percent or fixed")
        if discount_type == "percent" and not 1 <= amount <= 100:
            raise CouponError("percent amount must be between 1 and 100")
        if discount_type == "fixed" and amount <= 0:
            raise CouponError("fixed amount must be positive")

        exists = await session.execute(select(Coupon).where(func.upper(Coupon.code) == code))
        if exists.scalar_one_or_none():
            raise CouponError("coupon code already exists")

        coupon = Coupon(
            code=code,
            discount_type=discount_type,
            amount=amount,
            applies_to_all=not target_user_ids,
            created_by=created_by,
        )
        session.add(coupon)
        await session.flush()

        for user_id in target_user_ids:
            session.add(CouponTarget(coupon_id=coupon.id, user_id=user_id))

        await session.commit()
        return coupon

    @staticmethod
    async def get_coupon_by_code(session: AsyncSession, code: str) -> Coupon | None:
        result = await session.execute(
            select(Coupon)
            .options(selectinload(Coupon.targets))
            .where(func.upper(Coupon.code) == CouponService.normalize_code(code), Coupon.is_active == True)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def is_targeted_to_user(coupon: Coupon, user_id: int) -> bool:
        return bool(coupon.applies_to_all or any(target.user_id == user_id for target in coupon.targets))

    @staticmethod
    async def apply_coupon(session: AsyncSession, user_id: int, code: str) -> Coupon:
        coupon = await CouponService.get_coupon_by_code(session, code)
        if not coupon:
            raise CouponError("coupon not found")
        if not CouponService.is_targeted_to_user(coupon, user_id):
            raise CouponError("coupon is not available for this user")

        used = await session.execute(
            select(CouponRedemption).where(
                CouponRedemption.user_id == user_id,
                CouponRedemption.coupon_id == coupon.id,
                CouponRedemption.redeemed_at.is_not(None),
            )
        )
        if used.scalar_one_or_none():
            raise CouponError("coupon has already been used")

        await session.execute(
            update(CouponRedemption)
            .where(CouponRedemption.user_id == user_id, CouponRedemption.is_active == True)
            .values(is_active=False)
        )
        session.add(CouponRedemption(coupon_id=coupon.id, user_id=user_id, is_active=True))
        await session.commit()
        return coupon

    @staticmethod
    async def get_active_coupon(session: AsyncSession, user_id: int) -> Coupon | None:
        result = await session.execute(
            select(Coupon)
            .join(CouponRedemption, CouponRedemption.coupon_id == Coupon.id)
            .options(selectinload(Coupon.targets))
            .where(
                CouponRedemption.user_id == user_id,
                CouponRedemption.is_active == True,
                CouponRedemption.redeemed_at.is_(None),
                Coupon.is_active == True,
            )
            .order_by(CouponRedemption.applied_at.desc())
            .limit(1)
        )
        coupon = result.scalar_one_or_none()
        if coupon and CouponService.is_targeted_to_user(coupon, user_id):
            return coupon
        return None

    @staticmethod
    async def prices_with_active_discount(
        session: AsyncSession,
        user_id: int,
        prices: dict[int, int],
    ) -> dict[int, tuple[int, int]]:
        coupon = await CouponService.get_active_coupon(session, user_id)
        return {
            volume: CouponService.calculate_discount(price, coupon)
            for volume, price in prices.items()
        }

    @staticmethod
    async def mark_active_coupon_redeemed(
        session: AsyncSession,
        user_id: int,
        purchase_id: int,
    ) -> None:
        result = await session.execute(
            select(CouponRedemption)
            .where(
                CouponRedemption.user_id == user_id,
                CouponRedemption.is_active == True,
                CouponRedemption.redeemed_at.is_(None),
            )
            .order_by(CouponRedemption.applied_at.desc())
            .limit(1)
        )
        redemption = result.scalar_one_or_none()
        if redemption:
            redemption.is_active = False
            redemption.redeemed_at = datetime.now(timezone.utc)
            redemption.purchase_id = purchase_id
