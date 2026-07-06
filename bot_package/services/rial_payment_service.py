from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import RialPaymentRequest, Transaction, User


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

    @staticmethod
    async def list_pending_for_user(
        session: AsyncSession,
        user_id: int,
        *,
        limit: int = 10,
    ) -> list[RialPaymentRequest]:
        result = await session.execute(
            select(RialPaymentRequest)
            .where(
                RialPaymentRequest.user_id == user_id,
                RialPaymentRequest.status == "pending",
            )
            .order_by(RialPaymentRequest.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def decide_request(
        session: AsyncSession,
        *,
        request_id: int,
        approve: bool,
        admin_id: int,
    ) -> tuple[RialPaymentRequest | None, int | None]:
        request = (
            await session.execute(
                select(RialPaymentRequest)
                .where(RialPaymentRequest.id == request_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if request is None:
            return None, None
        if request.status != "pending":
            return request, None

        wallet_balance: int | None = None
        if approve:
            user = (
                await session.execute(
                    select(User)
                    .where(User.telegram_id == request.user_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if user is None:
                return None, None
            user.wallet_balance = (user.wallet_balance or 0) + request.amount_toman
            wallet_balance = user.wallet_balance
            topup_transaction = Transaction(
                user_id=request.user_id,
                amount=request.amount_toman,
                type="rial_charge",
                description=(
                    f"تایید درخواست کارت‌به‌کارت #{request.id} "
                    f"توسط ادمین {admin_id}"
                ),
            )
            session.add(topup_transaction)
            request.status = "approved"
        else:
            request.status = "rejected"

        request.updated_at = datetime.now(timezone.utc)
        await session.flush()
        from .referral_service import ReferralService
        from .subscription_link_service import SubscriptionLinkService

        rewards = []
        commission = None
        if approve:
            rewards = await ReferralService.evaluate_referred_user(session, request.user_id)
            commission = await ReferralService.grant_topup_commission(session, topup_transaction)
        await session.commit()
        for reward in rewards:
            if reward["config"] is not None:
                await SubscriptionLinkService.sync_to_panel(reward["config"], reward["service_name"])
        await ReferralService.notify_commission(commission)
        return request, wallet_balance
