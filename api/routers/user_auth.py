from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_package.models import User
from bot_package.services.referral_service import ReferralService

from ..deps import get_current_user, get_session
from ..schemas import MeResponse, TelegramAuthRequest, TokenResponse
from ..security import AuthError, issue_user_token, validate_init_data

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/telegram", response_model=TokenResponse)
async def telegram_auth(body: TelegramAuthRequest, session: AsyncSession = Depends(get_session)):
    try:
        data = validate_init_data(body.init_data)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    tg_user = data.get("user")
    if not isinstance(tg_user, dict) or "id" not in tg_user:
        raise HTTPException(status_code=401, detail="initData has no user")

    telegram_id = int(tg_user["id"])
    user = (
        await session.execute(select(User).where(User.telegram_id == telegram_id))
    ).scalar_one_or_none()
    if user is None:
        user = User(
            telegram_id=telegram_id,
            first_name=tg_user.get("first_name") or "",
            username=tg_user.get("username"),
        )
        session.add(user)
        await session.flush()
    else:
        user.first_name = tg_user.get("first_name") or user.first_name
        user.username = tg_user.get("username")

    await ReferralService.ensure_referral_code(session, user)
    # start_param mirrors the bot's `/start ref_x` deep-link payload.
    payload = body.start_param or data.get("start_param")
    await ReferralService.apply_start_payload(session, user, payload)
    await session.commit()

    return TokenResponse(access_token=issue_user_token(telegram_id))


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)):
    return MeResponse(
        telegram_id=user.telegram_id,
        first_name=user.first_name,
        username=user.username,
        wallet_balance=user.wallet_balance or 0,
        referral_code=user.referral_code,
        trial_claimed=user.trial_claimed_at is not None,
        accepted_rules=user.accepted_rules_at is not None,
    )
