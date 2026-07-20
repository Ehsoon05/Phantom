from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone

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
        payment_mode: str = "receipt_bot",
        destination_card_number: str | None = None,
        destination_card_holder: str | None = None,
        expires_at: datetime | None = None,
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
            payment_mode=payment_mode,
            destination_card_number=destination_card_number,
            destination_card_holder=destination_card_holder,
            expires_at=expires_at,
            receipt_status="awaiting",
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
    async def set_card_message(
        session: AsyncSession,
        request: RialPaymentRequest,
        *,
        chat_id: int,
        message_id: int,
    ) -> None:
        request.card_message_chat_id = chat_id
        request.card_message_id = message_id
        request.updated_at = datetime.now(timezone.utc)
        await session.commit()

    @staticmethod
    async def set_admin_messages(
        session: AsyncSession,
        request: RialPaymentRequest,
        messages: list[dict],
    ) -> None:
        request.admin_message_ids_json = json.dumps(messages)
        request.updated_at = datetime.now(timezone.utc)
        await session.commit()

    @staticmethod
    async def receipt_admin_messages(request: RialPaymentRequest) -> list[dict]:
        try:
            data = json.loads(request.admin_message_ids_json or "[]")
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    @staticmethod
    async def get_request(session: AsyncSession, request_id: int) -> RialPaymentRequest | None:
        return await session.get(RialPaymentRequest, request_id)

    @staticmethod
    async def latest_receipt_waiting_request(session: AsyncSession, user_id: int) -> RialPaymentRequest | None:
        result = await session.execute(
            select(RialPaymentRequest)
            .where(
                RialPaymentRequest.user_id == user_id,
                RialPaymentRequest.status == "pending",
                RialPaymentRequest.payment_mode == "receipt_bot",
                RialPaymentRequest.receipt_status == "awaiting",
            )
            .order_by(RialPaymentRequest.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def is_expired(request: RialPaymentRequest) -> bool:
        expires_at = request.expires_at
        if expires_at is None:
            return False
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at <= datetime.now(timezone.utc)

    @staticmethod
    async def mark_expired(session: AsyncSession, request: RialPaymentRequest) -> None:
        if request.status == "pending":
            request.status = "expired"
        request.receipt_status = "expired"
        request.updated_at = datetime.now(timezone.utc)
        await session.commit()

    @staticmethod
    async def record_receipt(
        session: AsyncSession,
        request: RialPaymentRequest,
        *,
        chat_id: int,
        message_id: int,
        receipt_text: str | None,
    ) -> None:
        request.receipt_chat_id = chat_id
        request.receipt_message_id = message_id
        request.receipt_text = receipt_text
        request.receipt_status = "submitted"
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
        rejection_reason: str | None = None,
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
        topup_transaction: Transaction | None = None
        if approve:
            marker = f"[rial_request:{request.id}]"
            legacy_marker = f"کارت‌به‌کارت #{request.id}"
            existing_transaction = (
                await session.execute(
                    select(Transaction)
                    .where(
                        Transaction.user_id == request.user_id,
                        Transaction.type == "rial_charge",
                        Transaction.description.ilike(f"%{legacy_marker}%"),
                    )
                    .order_by(Transaction.id.asc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if existing_transaction is None:
                existing_transaction = (
                    await session.execute(
                        select(Transaction)
                        .where(
                            Transaction.user_id == request.user_id,
                            Transaction.type == "rial_charge",
                            Transaction.description.ilike(f"%{marker}%"),
                        )
                        .order_by(Transaction.id.asc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
            if existing_transaction is not None:
                user = (
                    await session.execute(
                        select(User).where(User.telegram_id == request.user_id)
                    )
                ).scalar_one_or_none()
                request.status = "approved"
                request.decided_by = request.decided_by or admin_id
                request.receipt_status = "approved"
                request.updated_at = datetime.now(timezone.utc)
                await session.commit()
                return request, None

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
                    f"توسط ادمین {admin_id} {marker}"
                ),
            )
            session.add(topup_transaction)
            request.status = "approved"
        else:
            request.status = "rejected"
            request.rejection_reason = rejection_reason

        request.decided_by = admin_id
        request.receipt_status = "approved" if approve else "rejected"
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
