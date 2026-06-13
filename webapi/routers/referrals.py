from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from bot_package.models import User
from bot_package.services.referral_service import ReferralService

from ..deps import get_current_user, get_session
from ..schemas import ReferralsOut

router = APIRouter(prefix="/referrals", tags=["referrals"])


@router.get("", response_model=ReferralsOut)
async def referrals(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    code = await ReferralService.ensure_referral_code(session, user)
    await session.commit()
    total = await ReferralService.count_referrals(session, user.telegram_id)
    rules = await ReferralService.list_rules(session, active_only=True)

    rule_progress = []
    for rule in rules:
        qualified = await ReferralService.count_qualified(
            session, user.telegram_id, rule.qualification_type
        )
        rule_progress.append(
            {
                "id": rule.id,
                "title": rule.title,
                "qualification_type": rule.qualification_type,
                "required_count": rule.required_count,
                "is_repeatable": rule.is_repeatable,
                "reward_type": rule.reward_type,
                "wallet_amount": rule.wallet_amount,
                "qualified_count": qualified,
            }
        )
    return ReferralsOut(referral_code=code, total_referrals=total, rules=rule_progress)
