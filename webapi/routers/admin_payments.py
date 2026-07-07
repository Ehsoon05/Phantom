from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_package.models import Admin, RialPaymentRequest
from bot_package.services.crypto_payment_service import CryptoPaymentService
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
