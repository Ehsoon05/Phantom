from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_package.models import Admin, User
from bot_package.services.user_service import UserService
from bot_package.services.wallet_notification_service import WalletNotificationService

from ..deps import get_session, require_permission
from ..schemas import AdminUserOut, ChargeWalletRequest, SetBalanceRequest

router = APIRouter(prefix="/admin/users", tags=["admin"])


def _user_out(user: User) -> AdminUserOut:
    return AdminUserOut(
        telegram_id=user.telegram_id,
        first_name=user.first_name,
        username=user.username,
        wallet_balance=user.wallet_balance or 0,
        is_blocked=user.is_blocked,
        referral_code=user.referral_code,
        created_at=user.created_at,
    )


@router.get("", response_model=list[AdminUserOut])
async def list_users(
    q: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("users")),
):
    stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    if q:
        clean = q.lstrip("@")
        filters = [User.username.ilike(f"%{clean}%"), User.first_name.ilike(f"%{clean}%")]
        if clean.isdigit():
            filters.append(User.telegram_id == int(clean))
        stmt = stmt.where(or_(*filters))
    users = (await session.execute(stmt)).scalars().all()
    return [_user_out(u) for u in users]


@router.get("/count")
async def count_users(
    q: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("users")),
):
    stmt = select(func.count(User.id))
    if q:
        clean = q.lstrip("@")
        filters = [User.username.ilike(f"%{clean}%"), User.first_name.ilike(f"%{clean}%")]
        if clean.isdigit():
            filters.append(User.telegram_id == int(clean))
        stmt = stmt.where(or_(*filters))
    total = (await session.execute(stmt)).scalar_one()
    return {"total": total}


@router.get("/{telegram_id}", response_model=AdminUserOut)
async def get_user(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("users")),
):
    user = (
        await session.execute(select(User).where(User.telegram_id == telegram_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_out(user)


@router.get("/{telegram_id}/purchases")
async def user_purchases(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("users")),
):
    summary = await UserService.get_user_purchase_summary(session, telegram_id, limit=50)
    return {
        "total_count": summary["total_count"],
        "total_gb": summary["total_gb"],
        "total_spent": summary["total_spent"],
        "purchases": [
            {
                "id": p.id,
                "volume_gb": p.volume_gb,
                "category_key": p.category_key,
                "price": p.price,
                "service_name": p.service_name,
                "coupon_code": p.coupon_code,
                "purchased_at": p.purchased_at,
            }
            for p in summary["purchases"]
        ],
    }


@router.post("/{telegram_id}/charge", response_model=AdminUserOut)
async def charge_wallet(
    telegram_id: int,
    body: ChargeWalletRequest,
    session: AsyncSession = Depends(get_session),
    admin: Admin = Depends(require_permission("users")),
):
    ok = await UserService.charge_wallet(session, telegram_id, body.amount, admin.telegram_id)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    await session.commit()
    user = (
        await session.execute(select(User).where(User.telegram_id == telegram_id))
    ).scalar_one()
    await WalletNotificationService.send_charge_notification(
        session,
        telegram_id=telegram_id,
        amount=body.amount,
        wallet_balance=user.wallet_balance or 0,
    )
    return _user_out(user)


@router.post("/{telegram_id}/balance", response_model=AdminUserOut)
async def set_balance(
    telegram_id: int,
    body: SetBalanceRequest,
    session: AsyncSession = Depends(get_session),
    admin: Admin = Depends(require_permission("users")),
):
    ok = await UserService.set_wallet_balance(session, telegram_id, body.balance, admin.telegram_id)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    await session.commit()
    return await get_user(telegram_id, session, admin)


@router.post("/{telegram_id}/block", response_model=AdminUserOut)
async def toggle_block(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
    admin: Admin = Depends(require_permission("users")),
):
    user = (
        await session.execute(select(User).where(User.telegram_id == telegram_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_blocked = not user.is_blocked
    await session.commit()
    return _user_out(user)
