import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
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
from bot_package.services.hooshpay_service import HooshPayError, HooshPayService, verify_hooshpay_signature
from bot_package.services.settings_service import SettingsService
from bot_package.services.shop_customization_service import ShopCustomizationService
from bot_package.services.wallet_notification_service import WalletNotificationService
from bot_package.utils.datetime_format import format_tehran_time

from ..deps import get_current_user, get_session
from ..schemas import (
    CryptoInvoiceOut,
    CryptoInvoiceRequest,
    HooshPayInvoiceOut,
    HooshPayInvoiceRequest,
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


def _hooshpay_out(invoice) -> HooshPayInvoiceOut:
    return HooshPayInvoiceOut(
        id=invoice.id,
        uid=invoice.uid,
        order_id=invoice.order_id,
        amount_toman=invoice.amount_toman,
        payable_amount=invoice.payable_amount,
        merchant_credit=invoice.merchant_credit,
        fee_amount=invoice.fee_amount,
        fee_percent=invoice.fee_percent,
        fee_mode=invoice.fee_mode,
        payment_url=invoice.payment_url,
        card_number=invoice.card_number,
        card_holder=invoice.card_holder,
        bank_name=invoice.bank_name,
        status=invoice.status,
        tracking_code=invoice.tracking_code,
        created_at=invoice.created_at,
        expires_at=invoice.expires_at,
        credited_at=invoice.credited_at,
    )


@router.get("/methods")
async def payment_methods(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    phone_required = await SettingsService.rial_phone_required(session)
    source_card_required = await SettingsService.rial_source_card_required(session)
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
            "source_card_required": source_card_required,
            "phone_verified": bool(user.verified_phone_number and user.phone_verified_at),
            "verify_phone_url": (
                f"https://t.me/{BotConfig.MAIN_BOT_USERNAME}?start=verify_phone"
            ),
            "payment_mode": await SettingsService.get_rial_payment_mode(session),
        },
        "hooshpay": {
            "enabled": await SettingsService.hooshpay_enabled(session),
            "min_amount_toman": await SettingsService.get_hooshpay_min_amount(session),
            "fee_mode": await SettingsService.get_hooshpay_fee_mode(session),
            "title": await SettingsService.get_hooshpay_title(session),
            "subtitle": await SettingsService.get_hooshpay_subtitle(session),
            "amount_label": await SettingsService.get_hooshpay_amount_label(session),
            "create_button": await SettingsService.get_hooshpay_create_button(session),
            "pay_button": await SettingsService.get_hooshpay_pay_button(session),
            "preset_amounts": await SettingsService.get_hooshpay_preset_amounts(session),
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
    require_source_card = await SettingsService.rial_source_card_required(session)
    source_card = _normalize_card(body.source_card or "") if require_source_card else "دریافت نشد"
    if require_source_card and not source_card:
        raise HTTPException(status_code=400, detail="شماره کارت مبدا معتبر نیست.")

    payment_mode = await SettingsService.get_rial_payment_mode(session)
    # Only one pending rial request per user.
    pending_filters = [
        RialPaymentRequest.user_id == user.telegram_id,
        RialPaymentRequest.status == "pending",
    ]
    if payment_mode == "receipt_bot":
        pending_filters.append(RialPaymentRequest.receipt_status == "submitted")
    existing_pending = (
        await session.execute(
            select(RialPaymentRequest.id).where(
                *pending_filters,
            )
        )
    ).first()
    if existing_pending is not None:
        raise HTTPException(
            status_code=409, detail="You already have a pending rial request awaiting confirmation."
        )

    support_handle = await SettingsService.get_rial_support_handle(session)
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
            receipt_status=request.receipt_status,
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
        receipt_status=request.receipt_status,
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


@router.post("/hooshpay/invoices", response_model=HooshPayInvoiceOut)
async def create_hooshpay_invoice(
    body: HooshPayInvoiceRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    try:
        invoice = await HooshPayService.create_invoice(
            session,
            user_id=user.telegram_id,
            amount_toman=body.amount_toman,
        )
    except HooshPayError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _hooshpay_out(invoice)


@router.get("/hooshpay/invoices", response_model=list[HooshPayInvoiceOut])
async def list_hooshpay_invoices(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    invoices = await HooshPayService.list_for_user(session, user.telegram_id, limit=20)
    return [_hooshpay_out(invoice) for invoice in invoices]


@router.get("/hooshpay/invoices/{invoice_id}", response_model=HooshPayInvoiceOut)
async def get_hooshpay_invoice(
    invoice_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    invoice = await HooshPayService.get_invoice(session, invoice_id)
    if invoice is None or invoice.user_id != user.telegram_id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _hooshpay_out(invoice)


@router.post("/hooshpay/invoices/{invoice_id}/verify", response_model=HooshPayInvoiceOut)
async def verify_hooshpay_invoice(
    invoice_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    invoice = await HooshPayService.get_invoice(session, invoice_id)
    if invoice is None or invoice.user_id != user.telegram_id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    try:
        paid = await HooshPayService.verify_remote(session, invoice)
        if paid:
            invoice, wallet_balance, credited = await HooshPayService.mark_paid_and_credit(session, invoice=invoice)
            if credited and wallet_balance is not None:
                await WalletNotificationService.send_charge_notification(
                    session,
                    telegram_id=invoice.user_id,
                    amount=invoice.amount_toman,
                    wallet_balance=wallet_balance,
                )
        else:
            await session.commit()
    except (HooshPayError, Exception) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _hooshpay_out(invoice)


@router.post("/hooshpay/callback")
async def hooshpay_callback(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    payload = await request.json()
    signature = request.headers.get("X-HooshPay-Signature", "")
    secret = await SettingsService.get_hooshpay_api_secret(session)
    if not secret or not verify_hooshpay_signature(payload, signature, secret):
        raise HTTPException(status_code=401, detail="Invalid signature")
    if payload.get("event") != "payment.success":
        return {"ok": True}
    order_id = str(payload.get("order_id") or "")
    invoice = await HooshPayService.get_by_order_id(session, order_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice, wallet_balance, credited = await HooshPayService.mark_paid_and_credit(
        session,
        invoice=invoice,
        payload=payload,
    )
    if credited and wallet_balance is not None:
        await WalletNotificationService.send_charge_notification(
            session,
            telegram_id=invoice.user_id,
            amount=invoice.amount_toman,
            wallet_balance=wallet_balance,
        )
    return {"ok": True}


@router.get("/hooshpay/return")
async def hooshpay_return(order_id: str | None = None):
    return {
        "ok": True,
        "message": "پرداخت شما در حال بررسی است. پس از تایید، کیف پول به‌صورت خودکار شارژ می‌شود.",
        "order_id": order_id,
    }


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
            "receipt_status": r.receipt_status,
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
