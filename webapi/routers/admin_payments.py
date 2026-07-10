from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_package.models import Admin, HooshPayInvoice, RialPaymentRequest
from bot_package.services.crypto_payment_service import CryptoPaymentService
from bot_package.services.hooshpay_service import HooshPayService
from bot_package.services.rial_payment_service import RialPaymentService
from bot_package.services.wallet_notification_service import WalletNotificationService

from ..deps import get_session, require_permission
from ..schemas import RialDecisionRequest

router = APIRouter(prefix="/admin/payments", tags=["admin"])


def _rial_out(request: RialPaymentRequest) -> dict:
    return {
        "id": request.id,
        "tracking_code": request.tracking_code,
        "user_id": request.user_id,
        "amount_toman": request.amount_toman,
        "phone_number": request.phone_number,
        "source_card": request.source_card,
        "payment_mode": request.payment_mode,
        "destination_card_number": request.destination_card_number,
        "destination_card_holder": request.destination_card_holder,
        "expires_at": request.expires_at,
        "receipt_status": request.receipt_status,
        "rejection_reason": request.rejection_reason,
        "status": request.status,
        "created_at": request.created_at,
        "updated_at": request.updated_at,
    }


def _hooshpay_out(invoice: HooshPayInvoice) -> dict:
    return {
        "id": invoice.id,
        "uid": invoice.uid,
        "order_id": invoice.order_id,
        "user_id": invoice.user_id,
        "amount_toman": invoice.amount_toman,
        "payable_amount": invoice.payable_amount,
        "merchant_credit": invoice.merchant_credit,
        "fee_amount": invoice.fee_amount,
        "fee_percent": invoice.fee_percent,
        "fee_mode": invoice.fee_mode,
        "payment_url": invoice.payment_url,
        "card_number": invoice.card_number,
        "card_holder": invoice.card_holder,
        "bank_name": invoice.bank_name,
        "status": invoice.status,
        "tracking_code": invoice.tracking_code,
        "created_at": invoice.created_at,
        "updated_at": invoice.updated_at,
        "expires_at": invoice.expires_at,
        "credited_at": invoice.credited_at,
    }


@router.get("/rial")
async def list_rial_requests(
    status: str | None = Query(default="pending"),
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("users")),
):
    stmt = select(RialPaymentRequest).order_by(RialPaymentRequest.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(RialPaymentRequest.status == status)
    rows = (await session.execute(stmt)).scalars().all()
    return [_rial_out(r) for r in rows]


@router.get("/hooshpay")
async def list_hooshpay_invoices(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("reports")),
):
    rows = await HooshPayService.list_recent(session, status=status, limit=limit, offset=offset)
    return [_hooshpay_out(row) for row in rows]


@router.post("/rial/{request_id}/decision")
async def decide_rial_request(
    request_id: int,
    body: RialDecisionRequest,
    session: AsyncSession = Depends(get_session),
    admin: Admin = Depends(require_permission("users")),
):
    request, wallet_balance = await RialPaymentService.decide_request(
        session,
        request_id=request_id,
        approve=body.approve,
        admin_id=admin.telegram_id,
        rejection_reason=body.rejection_reason,
    )
    if request is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if body.approve and request.status == "approved" and wallet_balance is not None:
        await WalletNotificationService.send_charge_notification(
            session,
            telegram_id=request.user_id,
            amount=request.amount_toman,
            wallet_balance=wallet_balance,
        )
    return _rial_out(request)


@router.get("/crypto")
async def list_crypto_invoices(
    limit: int = Query(default=25, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("reports")),
):
    invoices = await CryptoPaymentService.list_recent(session, limit=limit, offset=offset)
    return [
        {
            "id": i.id,
            "user_id": i.user_id,
            "coin": i.coin,
            "network": i.network,
            "quoted_toman": i.quoted_toman,
            "expected_crypto": i.expected_crypto,
            "received_crypto": i.received_crypto,
            "status": i.status,
            "tx_hash": i.tx_hash,
            "created_at": i.created_at,
            "credited_at": i.credited_at,
        }
        for i in invoices
    ]
