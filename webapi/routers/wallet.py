import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_package.models import RialPaymentRequest, Transaction, User
from bot_package.services.crypto_payment_service import (
    SUPPORTED_COINS,
    CryptoPaymentError,
    CryptoPaymentService,
    available_coins,
    is_coin_available,
)
from bot_package.config_loader import BotConfig
from bot_package.services.rial_payment_service import RialPaymentService
from bot_package.services.settings_service import SettingsService
from bot_package.services.shop_customization_service import ShopCustomizationService
from bot_package.utils.datetime_format import format_tehran_time

from ..deps import get_current_user, get_session
from ..schemas import (
    CryptoInvoiceOut,
    CryptoInvoiceRequest,
    RialRequestIn,
    RialRequestOut,
    TransactionOut,
)

router = APIRouter(prefix="/wallet", tags=["wallet"])


def _normalize_card(value: str) -> str | None:
    digits = re.sub(r"\D", "", value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")))
    if len(digits) != 16 or len(set(digits)) == 1:
        return None
    checksum = 0
    for index, digit in enumerate(digits):
        weighted = int(digit) * (2 if index % 2 == 0 else 1)
        checksum += weighted - 9 if weighted > 9 else weighted
    return digits if checksum % 10 == 0 else None


def _invoice_out(invoice) -> CryptoInvoiceOut:
    return CryptoInvoiceOut(
        id=invoice.id,
        coin=invoice.coin,
        network=invoice.network,
        deposit_address=invoice.deposit_address,
        memo=invoice.memo,
        expected_crypto=invoice.expected_crypto,
        quoted_toman=invoice.quoted_toman,
        status=invoice.status,
        created_at=invoice.created_at,
        expires_at=invoice.expires_at,
    )


def _crypto_label(value: str) -> str:
    return "گرام(تون)" if value.upper() == "TON" else value


@router.get("/methods")
async def payment_methods(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    phone_required = await SettingsService.rial_phone_required(session)
    return {
        "crypto_coins": [
            {
                "key": key,
                "label": _crypto_label(SUPPORTED_COINS[key]["label"]),
                "coin": SUPPORTED_COINS[key]["coin"],
                "network": SUPPORTED_COINS[key]["network"],
            }
            for key in available_coins()
        ],
        "rial": {
            "min_amount_toman": await SettingsService.get_rial_min_amount(session),
            "phone_required": phone_required,
            "phone_verified": bool(user.verified_phone_number and user.phone_verified_at),
            "verify_phone_url": (
                f"https://t.me/{BotConfig.MAIN_BOT_USERNAME}?start=verify_phone"
            ),
            "payment_mode": await SettingsService.get_rial_payment_mode(session),
        },
    }


@router.get("/transactions", response_model=list[TransactionOut])
async def transactions(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    rows = (
        (
            await session.execute(
                select(Transaction)
                .where(Transaction.user_id == user.telegram_id)
                .order_by(Transaction.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    return [
        TransactionOut(
            id=t.id, amount=t.amount, type=t.type, description=t.description, created_at=t.created_at
        )
        for t in rows
    ]


@router.post("/crypto/invoices", response_model=CryptoInvoiceOut)
async def create_crypto_invoice(
    body: CryptoInvoiceRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    if not is_coin_available(body.coin_key):
        raise HTTPException(status_code=400, detail="Payment method not available")
    try:
        invoice = await CryptoPaymentService.create_invoice(
            session, user.telegram_id, body.coin_key, body.amount_toman
        )
        await session.commit()
    except CryptoPaymentError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _invoice_out(invoice)


@router.get("/crypto/invoices/{invoice_id}", response_model=CryptoInvoiceOut)
async def get_crypto_invoice(
    invoice_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    invoice = await CryptoPaymentService.get_invoice(session, invoice_id)
    if invoice is None or invoice.user_id != user.telegram_id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _invoice_out(invoice)


@router.post("/crypto/invoices/{invoice_id}/cancel", response_model=CryptoInvoiceOut)
async def cancel_crypto_invoice(
    invoice_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    invoice = await CryptoPaymentService.get_invoice(session, invoice_id)
    if invoice is None or invoice.user_id != user.telegram_id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending payments can be cancelled")
    invoice.status = "cancelled"
    await session.commit()
    return _invoice_out(invoice)


@router.get("/crypto/invoices", response_model=list[CryptoInvoiceOut])
async def list_crypto_invoices(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    invoices = await CryptoPaymentService.list_for_user(session, user.telegram_id, limit=20)
    return [_invoice_out(i) for i in invoices]


@router.post("/rial/requests", response_model=RialRequestOut)
async def create_rial_request(
    body: RialRequestIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    min_amount = await SettingsService.get_rial_min_amount(session)
    if body.amount_toman < min_amount:
        raise HTTPException(status_code=400, detail=f"Minimum amount is {min_amount} toman")
    require_phone = await SettingsService.rial_phone_required(session)
    phone_number = user.verified_phone_number
    if require_phone and not phone_number:
        raise HTTPException(
            status_code=403,
            detail="ابتدا شماره ایران متعلق به اکانت تلگرام خود را داخل ربات تایید کنید.",
        )
    source_card = _normalize_card(body.source_card)
    if not source_card:
        raise HTTPException(status_code=400, detail="شماره کارت مبدا معتبر نیست.")

    # Only one pending rial request per user.
    existing_pending = (
        await session.execute(
            select(RialPaymentRequest.id).where(
                RialPaymentRequest.user_id == user.telegram_id,
                RialPaymentRequest.status == "pending",
            )
        )
    ).first()
    if existing_pending is not None:
        raise HTTPException(
            status_code=409, detail="You already have a pending rial request awaiting confirmation."
        )

    support_handle = await SettingsService.get_rial_support_handle(session)
    payment_mode = await SettingsService.get_rial_payment_mode(session)
    destination_card = await SettingsService.get_rial_destination_card_number(session)
    destination_holder = await SettingsService.get_rial_destination_card_holder(session)
    valid_minutes = await SettingsService.get_rial_receipt_valid_minutes(session)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=valid_minutes)
    # Build the request exactly like the bot: a copyable support message, a
    # fuller "direct" text stored for the admin, and the customizable
    # rial_payment_request template shown to the user.
    request = await RialPaymentService.create_request(
        session,
        user_id=user.telegram_id,
        amount_toman=body.amount_toman,
        phone_number=phone_number,
        source_card=source_card,
        support_handle=support_handle,
        request_text="",
        payment_mode=payment_mode,
        destination_card_number=destination_card if payment_mode == "receipt_bot" else None,
        destination_card_holder=destination_holder if payment_mode == "receipt_bot" else None,
        expires_at=expires_at if payment_mode == "receipt_bot" else None,
    )
    if payment_mode == "receipt_bot":
        direct_text = (
            f"درخواست پرداخت کارت‌به‌کارت #{request.id}\n"
            f"مبلغ: {body.amount_toman:,} تومان\n"
            f"کارت مبدا: {source_card}\n"
            f"کارت مقصد: {destination_card}\n"
            f"صاحب کارت: {destination_holder}\n"
            f"کد پیگیری: {request.tracking_code}\n"
            f"آیدی عددی تلگرام: {user.telegram_id}"
        )
        if phone_number:
            direct_text += f"\nشماره تماس: {phone_number}"
        message = await ShopCustomizationService.get_message(
            session,
            "rial_card_payment_instructions",
            destination_card=destination_card,
            destination_holder=destination_holder,
            amount=f"{body.amount_toman:,}",
            valid_minutes=f"{valid_minutes:,}",
            expires_at=format_tehran_time(expires_at),
            tracking_code=request.tracking_code,
        )
        await RialPaymentService.update_request_text(session, request, direct_text)
        return RialRequestOut(
            id=request.id,
            tracking_code=request.tracking_code,
            amount_toman=request.amount_toman,
            status=request.status,
            payment_mode=request.payment_mode,
            support_handle=request.support_handle,
            request_text=direct_text,
            message_text=str(message),
            copy_text=destination_card,
            send_url=None,
            destination_card=destination_card,
            destination_holder=destination_holder,
            expires_at=request.expires_at,
            receipt_bot_url=f"https://t.me/{BotConfig.MAIN_BOT_USERNAME}?start=rial_receipt_{request.id}",
            created_at=request.created_at,
        )
    copy_text = (
        "سلام،\n\n"
        f"درخواست شارژ حساب به مبلغ {body.amount_toman:,} تومان را دارم\n"
        f"شماره کارت مبدا: {source_card}\n"
        "تشکر 🙏"
    )
    direct_text = (
        f"{copy_text}\n"
        f"کد پیگیری: {request.tracking_code}\n"
        f"آیدی عددی تلگرام: {user.telegram_id}"
    )
    if phone_number:
        direct_text += f"\nشماره تماس: {phone_number}"
    message = await ShopCustomizationService.get_message(
        session,
        "rial_payment_request",
        support_handle=support_handle,
        amount=f"{body.amount_toman:,}",
        source_card=source_card,
        tracking_code=request.tracking_code,
        phone_number=phone_number or "دریافت نشد",
        copy_text=copy_text,
    )
    await RialPaymentService.update_request_text(session, request, direct_text)

    username = support_handle.lstrip("@")
    send_url = f"https://t.me/{username}?text={quote(direct_text, safe='')}"
    return RialRequestOut(
        id=request.id,
        tracking_code=request.tracking_code,
        amount_toman=request.amount_toman,
        status=request.status,
        payment_mode=request.payment_mode,
        support_handle=request.support_handle,
        request_text=direct_text,
        message_text=str(message),
        copy_text=copy_text,
        send_url=send_url,
        destination_card=request.destination_card_number,
        destination_holder=request.destination_card_holder,
        expires_at=request.expires_at,
        receipt_bot_url=None,
        created_at=request.created_at,
    )


@router.get("/rial/requests")
async def list_rial_requests(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    rows = (
        (
            await session.execute(
                select(RialPaymentRequest)
                .where(RialPaymentRequest.user_id == user.telegram_id)
                .order_by(RialPaymentRequest.created_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": r.id,
            "tracking_code": r.tracking_code,
            "amount_toman": r.amount_toman,
            "status": r.status,
            "payment_mode": r.payment_mode,
            "expires_at": r.expires_at,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.post("/rial/requests/{request_id}/cancel")
async def cancel_rial_request(
    request_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    request = (
        await session.execute(
            select(RialPaymentRequest).where(RialPaymentRequest.id == request_id)
        )
    ).scalar_one_or_none()
    if request is None or request.user_id != user.telegram_id:
        raise HTTPException(status_code=404, detail="Request not found")
    if request.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending requests can be cancelled")
    request.status = "cancelled"
    await session.commit()
    return {"id": request.id, "status": request.status}
