"""Crypto top-up lifecycle: create invoice -> watch chain -> credit wallet.

Crediting is idempotent (UNIQUE tx_hash) and reuses the row-lock pattern from
the purchase flow so concurrent writes to a wallet can't race.
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config_loader import BotConfig
from ..models import CryptoInvoice, Transaction, User
from . import bsc_watcher, ton_watcher, tron_watcher
from .rate_service import RateError, RateService

logger = logging.getLogger(__name__)

# Selectable payment methods. ``rate_coin`` picks the market used for conversion.
# USDC is priced off the USDT market (both peg ~$1), so it needs no separate rate.
SUPPORTED_COINS: dict[str, dict] = {
    "USDT_TRC20": {"coin": "USDT", "network": "TRC20", "rate_coin": "USDT", "label": "USDT (TRON · TRC20)"},
    "TON": {"coin": "TON", "network": "TON", "rate_coin": "TON", "label": "TON"},
    "USDT_TON": {"coin": "USDT", "network": "TON", "rate_coin": "USDT", "label": "USDT (TON)"},
    "USDC_BEP20": {"coin": "USDC", "network": "BEP20", "rate_coin": "USDT", "label": "USDC (BNB Smart Chain · BEP20)"},
}

# Cap on simultaneously-open invoices per user. Bounds the number of addresses
# the poll job must watch, preventing a /charge spammer from exhausting the
# upstream chain-API rate limit and starving legitimate payment detection.
MAX_PENDING_PER_USER = 3

# Per-coin dust floor: payments below this are ignored (spam/dust protection),
# but anything above it is credited at its *actual* value (see credit logic),
# so honest underpayments are no longer silently lost.
DUST_FLOOR: dict[str, Decimal] = {"USDT": Decimal("0.01"), "USDC": Decimal("0.01"), "TON": Decimal("0.05")}


class CryptoPaymentError(Exception):
    pass


def is_coin_available(coin_key: str) -> bool:
    """Whether the infrastructure for a payment method is configured."""
    spec = SUPPORTED_COINS.get(coin_key)
    if not spec or not BotConfig.CRYPTO_ENABLED:
        return False
    if spec["network"] == "TRC20":
        return bool(BotConfig.TRON_XPUB)
    if spec["network"] == "BEP20":
        return bool(BotConfig.BSC_XPUB)
    if spec["network"] == "TON":
        if not BotConfig.TON_DEPOSIT_ADDRESS:
            return False
        if spec["coin"] == "USDT":
            return bool(BotConfig.TON_USDT_JETTON_MASTER)
        return True  # native TON
    return False


def available_coins() -> list[str]:
    return [key for key in SUPPORTED_COINS if is_coin_available(key)]


class CryptoPaymentService:
    @staticmethod
    async def create_invoice(session: AsyncSession, user_id: int, coin_key: str, toman: int) -> CryptoInvoice:
        spec = SUPPORTED_COINS.get(coin_key)
        if not spec:
            raise CryptoPaymentError("Unknown payment method.")
        if not is_coin_available(coin_key):
            raise CryptoPaymentError("This payment method is not available.")
        if toman <= 0:
            raise CryptoPaymentError("Amount must be positive.")

        # Clean up this user's time-expired invoices and cap concurrently-open
        # ones so a /charge spammer cannot balloon the set of watched addresses.
        now = datetime.now(timezone.utc)
        existing = (
            await session.execute(
                select(CryptoInvoice).where(
                    CryptoInvoice.user_id == user_id,
                    CryptoInvoice.status == "pending",
                )
            )
        ).scalars().all()
        active = 0
        for old in existing:
            if old.expires_at and old.expires_at < now:
                old.status = "expired"
            else:
                active += 1
        if active >= MAX_PENDING_PER_USER:
            await session.commit()  # persist the expirations we just made
            raise CryptoPaymentError("Too many open invoices.")

        try:
            crypto_amount, rate, source = await RateService.toman_to_crypto(session, spec["rate_coin"], toman)
        except RateError as exc:
            raise CryptoPaymentError(f"Rate unavailable: {exc}") from exc

        invoice = CryptoInvoice(
            user_id=user_id,
            coin=spec["coin"],
            network=spec["network"],
            deposit_address="",  # filled after we have the invoice id
            expected_crypto=str(crypto_amount),
            quoted_toman=toman,
            locked_rate=str(rate),
            rate_source=source,
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=BotConfig.CRYPTO_INVOICE_TTL_MINUTES),
        )
        session.add(invoice)
        await session.flush()  # assign invoice.id

        try:
            if spec["network"] == "TRC20":
                invoice.address_index = invoice.id
                invoice.deposit_address = tron_watcher.derive_address(invoice.id)
            elif spec["network"] == "BEP20":
                invoice.address_index = invoice.id
                invoice.deposit_address = bsc_watcher.derive_address(invoice.id)
            else:  # TON family: shared address + unique, unpredictable memo
                invoice.deposit_address = BotConfig.TON_DEPOSIT_ADDRESS
                invoice.memo = "SVN" + secrets.token_hex(16)
        except Exception as exc:  # noqa: BLE001 - bad xpub/derivation config
            await session.rollback()
            raise CryptoPaymentError(f"Could not allocate deposit address: {exc}") from exc

        await session.commit()
        return invoice

    @staticmethod
    async def _fetch_payments(invoice: CryptoInvoice) -> list[dict]:
        # Only filter out dust; under/overpayment vs the expected amount is
        # decided in credit_from_payment so the actual received value is credited.
        min_amount = DUST_FLOOR.get(invoice.coin, Decimal("0"))

        if invoice.network == "TRC20":
            return await tron_watcher.fetch_incoming_usdt(invoice.deposit_address, min_amount)
        if invoice.network == "BEP20":
            return await bsc_watcher.fetch_incoming_usdc(invoice.deposit_address, min_amount)
        if invoice.network == "TON":
            if invoice.coin == "USDT":
                return await ton_watcher.fetch_incoming_jetton_ton(
                    invoice.memo, BotConfig.TON_USDT_JETTON_MASTER, BotConfig.TON_USDT_DECIMALS, min_amount
                )
            return await ton_watcher.fetch_incoming_ton(invoice.memo, min_amount)
        return []

    @staticmethod
    async def credit_from_payment(session: AsyncSession, invoice: CryptoInvoice, payment: dict) -> int:
        """Credit a wallet from a detected payment. Idempotent.

        Returns the toman amount credited, or 0 if nothing was credited.
        """
        if invoice.status in {"credited", "underpaid", "expired"}:
            return 0
        if payment.get("confirmations", 0) < BotConfig.CRYPTO_MIN_CONFIRMATIONS:
            return 0

        received = Decimal(str(payment["amount"]))
        locked_rate = Decimal(invoice.locked_rate)
        expected = Decimal(invoice.expected_crypto)
        tol = Decimal(BotConfig.CRYPTO_UNDERPAY_TOLERANCE)
        threshold = expected * (Decimal(100) - tol) / Decimal(100)

        # Credit the *actual* received value (never over-credit on underpayment).
        credited_toman = int((received * locked_rate).to_integral_value(rounding=ROUND_DOWN))
        if credited_toman <= 0:
            return 0

        # Lock the user row (FOR UPDATE on PostgreSQL; SQLite serializes writes).
        user = (
            await session.execute(
                select(User).where(User.telegram_id == invoice.user_id).with_for_update()
            )
        ).scalar_one_or_none()
        if user is None:
            logger.warning("Crypto credit skipped: user %s not found", invoice.user_id)
            return 0

        invoice.from_address = payment.get("from")
        invoice.received_crypto = str(received)
        invoice.tx_hash = payment.get("tx_hash")
        invoice.confirmations = payment.get("confirmations", 0)
        invoice.credited_at = datetime.now(timezone.utc)
        invoice.status = "credited" if received >= threshold else "underpaid"

        user.wallet_balance = (user.wallet_balance or 0) + credited_toman
        session.add(
            Transaction(
                user_id=invoice.user_id,
                amount=credited_toman,
                type="crypto_charge",
                description=(
                    f"شارژ کریپتو {invoice.coin}/{invoice.network} "
                    f"({received} {invoice.coin}) tx:{invoice.tx_hash}"
                ),
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            # Duplicate tx_hash => this payment was already credited elsewhere.
            await session.rollback()
            logger.info("Crypto credit skipped (duplicate tx) for invoice %s", invoice.id)
            return 0
        return credited_toman

    @staticmethod
    async def poll_pending(session: AsyncSession) -> list[dict]:
        """Check all pending invoices for payments.

        Returns a list of {user_id, invoice_id, credited_toman} for invoices
        that were credited this pass (used to notify users).
        """
        now = datetime.now(timezone.utc)
        pending = (
            await session.execute(
                select(CryptoInvoice).where(CryptoInvoice.status == "pending")
            )
        ).scalars().all()

        credited: list[dict] = []
        for invoice in pending:
            # Always check for a payment FIRST: a transfer that lands just before
            # the TTL must still be credited, not dropped by an early expiry.
            fetch_ok = True
            try:
                payments = await CryptoPaymentService._fetch_payments(invoice)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Payment fetch failed for invoice %s: %s", invoice.id, exc)
                payments = []
                fetch_ok = False

            matched = False
            for payment in payments:
                if not payment.get("tx_hash"):
                    continue
                amount = await CryptoPaymentService.credit_from_payment(session, invoice, payment)
                if amount > 0:
                    credited.append(
                        {"user_id": invoice.user_id, "invoice_id": invoice.id, "credited_toman": amount}
                    )
                    matched = True
                    break

            # Only expire after a *successful* fetch found no payment, so a
            # transient API error doesn't strand a real payment.
            if not matched and fetch_ok and invoice.expires_at and invoice.expires_at < now:
                invoice.status = "expired"
                await session.commit()
        return credited

    # --- Queries for the admin bot ------------------------------------------------

    @staticmethod
    async def list_recent(session: AsyncSession, limit: int = 15, offset: int = 0) -> list[CryptoInvoice]:
        rows = await session.execute(
            select(CryptoInvoice).order_by(CryptoInvoice.created_at.desc()).limit(limit).offset(offset)
        )
        return list(rows.scalars().all())

    @staticmethod
    async def list_for_user(session: AsyncSession, telegram_id: int, limit: int = 20) -> list[CryptoInvoice]:
        rows = await session.execute(
            select(CryptoInvoice)
            .where(CryptoInvoice.user_id == telegram_id)
            .order_by(CryptoInvoice.created_at.desc())
            .limit(limit)
        )
        return list(rows.scalars().all())

    @staticmethod
    async def get_invoice(session: AsyncSession, invoice_id: int) -> Optional[CryptoInvoice]:
        return await session.get(CryptoInvoice, invoice_id)

    # --- User-facing helpers ------------------------------------------------------

    @staticmethod
    async def list_pending_for_user(session: AsyncSession, telegram_id: int) -> list[CryptoInvoice]:
        """Return the user's still-open (pending, not yet expired) invoices."""
        now = datetime.now(timezone.utc)
        rows = await session.execute(
            select(CryptoInvoice)
            .where(CryptoInvoice.user_id == telegram_id, CryptoInvoice.status == "pending")
            .order_by(CryptoInvoice.created_at.desc())
        )
        invoices = list(rows.scalars().all())
        return [inv for inv in invoices if not (inv.expires_at and inv.expires_at < now)]

    @staticmethod
    async def cancel_pending(session: AsyncSession, telegram_id: int) -> int:
        """Cancel all of the user's pending invoices. Returns how many were cancelled."""
        rows = await session.execute(
            select(CryptoInvoice)
            .where(CryptoInvoice.user_id == telegram_id, CryptoInvoice.status == "pending")
        )
        invoices = list(rows.scalars().all())
        for inv in invoices:
            inv.status = "cancelled"
        if invoices:
            await session.commit()
        return len(invoices)
