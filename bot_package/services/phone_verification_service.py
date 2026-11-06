from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User


class PhoneVerificationService:
    @staticmethod
    def normalize_iran_phone(value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.translate(
            str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
        )
        digits = re.sub(r"\D", "", normalized)
        if digits.startswith("0098"):
            digits = digits[2:]
        if digits.startswith("98") and len(digits) == 12:
            digits = "0" + digits[2:]
        if len(digits) != 11 or not digits.startswith("09"):
            return None
        return f"+98{digits[1:]}"

    @staticmethod
    async def verify(
        session: AsyncSession,
        telegram_id: int,
        phone_number: str,
    ) -> User | None:
        user = (
            await session.execute(select(User).where(User.telegram_id == telegram_id))
        ).scalar_one_or_none()
        if user is None:
            return None
        user.verified_phone_number = phone_number
        user.phone_verified_at = datetime.now(timezone.utc)
        await session.commit()
        return user
