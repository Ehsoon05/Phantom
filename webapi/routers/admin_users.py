from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_package.models import Admin, User
from bot_package.services.user_service import UserService

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
    return await UserService.get_user_purchase_summary(session, telegram_id)


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
    return await get_user(telegram_id, session, admin)


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
