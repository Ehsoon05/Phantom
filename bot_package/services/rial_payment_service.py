from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import RialPaymentRequest


class RialPaymentService:
    @staticmethod
    async def create_request(
        session: AsyncSession,
        *,
        user_id: int,
        amount_toman: int,
        phone_number: str | None,
        source_card: str,
        support_handle: str,
        request_text: str,
    ) -> RialPaymentRequest:
        while True:
            tracking_code = str(secrets.randbelow(9_000_000_000_000_000_000) + 1_000_000_000_000_000_000)
            existing = await session.execute(
                select(RialPaymentRequest.id).where(RialPaymentRequest.tracking_code == tracking_code)
            )
            if existing.scalar_one_or_none() is None:
                break

        request = RialPaymentRequest(
            tracking_code=tracking_code,
            user_id=user_id,
            amount_toman=amount_toman,
            phone_number=phone_number,
            source_card=source_card,
            support_handle=support_handle,
            request_text=request_text,
            status="pending",
        )
        session.add(request)
        await session.commit()
        await session.refresh(request)
        return request

    @staticmethod
    async def update_request_text(
        session: AsyncSession,
        request: RialPaymentRequest,
        request_text: str,
    ) -> None:
        request.request_text = request_text
        request.updated_at = datetime.now(timezone.utc)
        await session.commit()

    @staticmethod
    async def list_recent(session: AsyncSession, limit: int = 10) -> list[RialPaymentRequest]:
        result = await session.execute(
            select(RialPaymentRequest)
            .order_by(RialPaymentRequest.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
