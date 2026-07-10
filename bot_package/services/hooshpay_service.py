from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import HooshPayInvoice, Transaction, User
from .settings_service import SettingsService


class HooshPayError(RuntimeError):
    pass


def verify_hooshpay_signature(payload: dict, signature: str, secret: str) -> bool:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


class HooshPayService:
    @staticmethod
    def order_id(invoice_id: int) -> str:
        return f"phantom-hp-{invoice_id}"

    @staticmethod
    async def create_invoice(
        session: AsyncSession,
        *,
        user_id: int,
        amount_toman: int,
        description: str | None = None,
    ) -> HooshPayInvoice:
        if not await SettingsService.hooshpay_enabled(session):
            raise HooshPayError("درگاه هوش‌پی در حال حاضر غیرفعال است.")
        minimum = await SettingsService.get_hooshpay_min_amount(session)
        if amount_toman < minimum:
            raise HooshPayError(f"حداقل مبلغ درگاه هوش‌پی {minimum:,} تومان است.")

        api_key = await SettingsService.get_hooshpay_api_key(session)
        if not api_key:
            raise HooshPayError("کلید API هوش‌پی تنظیم نشده است.")

        fee_mode = await SettingsService.get_hooshpay_fee_mode(session)
        api_base = await SettingsService.get_hooshpay_api_base_url(session)
        callback_base = await SettingsService.get_hooshpay_callback_base_url(session)
        invoice = HooshPayInvoice(
            order_id="pending",
            user_id=user_id,
            amount_toman=amount_toman,
            fee_mode=fee_mode,
            status="creating",
        )
        session.add(invoice)
        await session.flush()
        invoice.order_id = HooshPayService.order_id(invoice.id)
        callback_url = f"{callback_base}/api/v1/wallet/hooshpay/callback"
        return_url = f"{callback_base}/api/v1/wallet/hooshpay/return?order_id={invoice.order_id}"
        payload = {
            "amount": int(amount_toman),
            "fee_mode": fee_mode,
            "order_id": invoice.order_id,
            "description": description or f"شارژ کیف پول فانتوم هابز برای کاربر {user_id}",
            "callback_url": callback_url,
            "return_url": return_url,
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{api_base}/api/v1/invoices",
                    headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            invoice.status = "failed"
            invoice.raw_payload = json.dumps({"error": str(exc)}, ensure_ascii=False)
            invoice.updated_at = datetime.now(timezone.utc)
            await session.commit()
            raise HooshPayError("ساخت فاکتور هوش‌پی انجام نشد.") from exc

        if not data.get("success"):
            invoice.status = "failed"
            invoice.raw_payload = json.dumps(data, ensure_ascii=False)
            invoice.updated_at = datetime.now(timezone.utc)
            await session.commit()
            raise HooshPayError(str(data.get("message") or "HooshPay invoice failed"))

        HooshPayService.apply_invoice_payload(invoice, data.get("data") or {})
        invoice.raw_payload = json.dumps(data, ensure_ascii=False)
        await session.commit()
        await session.refresh(invoice)
        return invoice

    @staticmethod
    def apply_invoice_payload(invoice: HooshPayInvoice, payload: dict) -> None:
        card = payload.get("card") if isinstance(payload.get("card"), dict) else {}
        invoice.uid = payload.get("uid") or invoice.uid
        invoice.amount_toman = int(payload.get("amount") or invoice.amount_toman)
        invoice.payable_amount = _optional_int(payload.get("payable_amount"))
        invoice.merchant_credit = _optional_int(payload.get("merchant_credit"))
        invoice.fee_amount = _optional_int(payload.get("fee_amount"))
        invoice.fee_percent = _optional_int(payload.get("fee_percent"))
        invoice.fee_mode = payload.get("fee_mode") or invoice.fee_mode
        invoice.status = payload.get("status") or invoice.status or "pending"
        invoice.payment_url = payload.get("payment_url") or invoice.payment_url
        invoice.card_number = card.get("card_number") or invoice.card_number
        invoice.card_holder = card.get("holder_name") or invoice.card_holder
        invoice.bank_name = card.get("bank_name") or invoice.bank_name
        invoice.expires_at = _parse_datetime(payload.get("expires_at")) or invoice.expires_at
        invoice.updated_at = datetime.now(timezone.utc)

    @staticmethod
    async def get_invoice(session: AsyncSession, invoice_id: int) -> HooshPayInvoice | None:
        return await session.get(HooshPayInvoice, invoice_id)

    @staticmethod
    async def get_by_order_id(session: AsyncSession, order_id: str) -> HooshPayInvoice | None:
        result = await session.execute(select(HooshPayInvoice).where(HooshPayInvoice.order_id == order_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_for_user(session: AsyncSession, user_id: int, limit: int = 20) -> list[HooshPayInvoice]:
        result = await session.execute(
            select(HooshPayInvoice)
            .where(HooshPayInvoice.user_id == user_id)
            .order_by(HooshPayInvoice.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_recent(
        session: AsyncSession,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[HooshPayInvoice]:
        stmt = select(HooshPayInvoice).order_by(HooshPayInvoice.created_at.desc()).limit(limit).offset(offset)
        if status:
            stmt = stmt.where(HooshPayInvoice.status == status)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def verify_remote(session: AsyncSession, invoice: HooshPayInvoice) -> bool:
        api_key = await SettingsService.get_hooshpay_api_key(session)
        api_base = await SettingsService.get_hooshpay_api_base_url(session)
        if not api_key or not invoice.uid:
            return False
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{api_base}/api/v1/invoices/{invoice.uid}/verify",
                headers={"X-API-KEY": api_key},
            )
            response.raise_for_status()
            payload = response.json()
        invoice.raw_payload = json.dumps(payload, ensure_ascii=False)
        if payload.get("data"):
            HooshPayService.apply_invoice_payload(invoice, payload["data"])
        invoice.status = payload.get("status") or invoice.status
        return bool(payload.get("paid") or invoice.status == "paid")

    @staticmethod
    async def mark_paid_and_credit(
        session: AsyncSession,
        *,
        invoice: HooshPayInvoice,
        payload: dict | None = None,
    ) -> tuple[HooshPayInvoice, int | None, bool]:
        if payload:
            invoice.status = payload.get("status") or "paid"
            invoice.tracking_code = payload.get("tracking_code") or invoice.tracking_code
            invoice.payable_amount = _optional_int(payload.get("payable_amount")) or invoice.payable_amount
            invoice.merchant_credit = _optional_int(payload.get("merchant_credit")) or invoice.merchant_credit
            invoice.fee_amount = _optional_int(payload.get("fee_amount")) or invoice.fee_amount
            invoice.raw_payload = json.dumps(payload, ensure_ascii=False)
            invoice.paid_at = _parse_datetime(payload.get("paid_at")) or datetime.now(timezone.utc)
        else:
            invoice.status = "paid"
            invoice.paid_at = invoice.paid_at or datetime.now(timezone.utc)

        if invoice.credited_at is not None:
            invoice.updated_at = datetime.now(timezone.utc)
            await session.commit()
            return invoice, None, False

        user = (
            await session.execute(
                select(User).where(User.telegram_id == invoice.user_id).with_for_update()
            )
        ).scalar_one_or_none()
        if user is None:
            raise HooshPayError("کاربر فاکتور پیدا نشد.")
        user.wallet_balance = (user.wallet_balance or 0) + invoice.amount_toman
        wallet_balance = user.wallet_balance
        invoice.status = "paid"
        invoice.credited_at = datetime.now(timezone.utc)
        invoice.updated_at = datetime.now(timezone.utc)
        topup_transaction = Transaction(
            user_id=invoice.user_id,
            amount=invoice.amount_toman,
            type="hooshpay_charge",
            description=f"شارژ هوش‌پی {invoice.order_id}",
        )
        session.add(topup_transaction)
        await session.flush()
        from .referral_service import ReferralService

        commission = await ReferralService.grant_topup_commission(session, topup_transaction)
        await session.commit()
        await ReferralService.notify_commission(commission)
        return invoice, wallet_balance, True


def _optional_int(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
