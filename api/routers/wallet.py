from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_package.models import Transaction, User
from bot_package.services.crypto_payment_service import (
    CryptoPaymentError,
    CryptoPaymentService,
    is_coin_available,
)
from bot_package.services.rial_payment_service import RialPaymentService
from bot_package.services.settings_service import SettingsService

from ..deps import get_current_user, get_session
from ..schemas import (
    CryptoInvoiceOut,
    CryptoInvoiceRequest,
    RialRequestIn,
    RialRequestOut,
    TransactionOut,
)

router = APIRouter(prefix="/wallet", tags=["wallet"])


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
    if await SettingsService.rial_phone_required(session) and not body.phone_number:
        raise HTTPException(status_code=400, detail="Phone number is required")

    support_handle = await SettingsService.get_rial_support_handle(session)
    request_text = (
        f"درخواست شارژ ریالی\n"
        f"مبلغ: {body.amount_toman:,} تومان\n"
        f"کارت مبدا: {body.source_card}\n"
        f"پشتیبانی: {support_handle}"
    )
    request = await RialPaymentService.create_request(
        session,
        user_id=user.telegram_id,
        amount_toman=body.amount_toman,
        phone_number=body.phone_number,
        source_card=body.source_card,
        support_handle=support_handle,
        request_text=request_text,
    )
    return RialRequestOut(
        id=request.id,
        tracking_code=request.tracking_code,
        amount_toman=request.amount_toman,
        status=request.status,
        support_handle=request.support_handle,
        request_text=request.request_text,
        created_at=request.created_at,
    )
