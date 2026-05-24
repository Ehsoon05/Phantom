from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User


def _base36(value: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    result = ""
    while value:
        value, remainder = divmod(value, 36)
        result = alphabet[remainder] + result
    return result


class ReferralService:
    @staticmethod
    def build_referral_code(telegram_id: int) -> str:
        return f"p{_base36(abs(telegram_id))}"

    @staticmethod
    async def ensure_referral_code(session: AsyncSession, user: User) -> str:
        if not user.referral_code:
            user.referral_code = ReferralService.build_referral_code(user.telegram_id)
            await session.flush()
        return user.referral_code

    @staticmethod
    async def apply_start_payload(session: AsyncSession, user: User, payload: str | None) -> bool:
        if not payload or user.referred_by_user_id:
            return False
        if not payload.startswith("ref_"):
            return False

        code = payload.removeprefix("ref_").strip().lower()
        if not code:
            return False

        result = await session.execute(select(User).where(func.lower(User.referral_code) == code))
        referrer = result.scalar_one_or_none()
        if not referrer or referrer.telegram_id == user.telegram_id:
            return False

        user.referred_by_user_id = referrer.telegram_id
        user.referred_at = datetime.now(timezone.utc)
        await session.flush()
        return True

    @staticmethod
    async def count_referrals(session: AsyncSession, telegram_id: int) -> int:
        result = await session.execute(
            select(func.count(User.id)).where(User.referred_by_user_id == telegram_id)
        )
        return int(result.scalar() or 0)

    @staticmethod
    async def referral_map(session: AsyncSession) -> list[tuple[int, int, datetime | None]]:
        result = await session.execute(
            select(User.telegram_id, User.referred_by_user_id, User.referred_at)
            .where(User.referred_by_user_id.is_not(None))
            .order_by(User.referred_at.desc())
        )
        return [(int(row[0]), int(row[1]), row[2]) for row in result.all()]
