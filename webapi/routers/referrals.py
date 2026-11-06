from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from bot_package.config_loader import BotConfig
from bot_package.models import ShopPlan, User
from bot_package.services.referral_service import ReferralService
from bot_package.services.shop_customization_service import ShopCustomizationService

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
    referral_link = f"https://t.me/{BotConfig.MAIN_BOT_USERNAME}?start=ref_{code}"
    commission_text = await ReferralService.commission_text(session)
    message_text = await ShopCustomizationService.get_message(
        session,
        "referral",
        link=referral_link,
        count=total,
        commission_text=commission_text,
    )
    share_text = await ShopCustomizationService.get_message(
        session,
        "referral_share_text",
        link=referral_link,
    )

    rule_progress = []
    for rule in rules:
        qualified = await ReferralService.count_qualified(
            session, user.telegram_id, rule.qualification_type
        )
        target = (
            ((qualified // rule.required_count) + 1) * rule.required_count
            if rule.is_repeatable
            else rule.required_count
        )
        reward_text = f"{rule.wallet_amount or 0:,} تومان اعتبار کیف پول"
        if rule.reward_type == "service":
            plan = await session.get(ShopPlan, rule.shop_plan_id)
            reward_text = f"سرویس رایگان {plan.title}" if plan else "سرویس رایگان"
        rule_progress.append(
            {
                "id": rule.id,
                "title": rule.title,
                "qualification_type": rule.qualification_type,
                "qualification_label": ReferralService.QUALIFICATION_LABELS.get(
                    rule.qualification_type,
                    rule.qualification_type,
                ),
                "required_count": rule.required_count,
                "target_count": target,
                "is_repeatable": rule.is_repeatable,
                "reward_type": rule.reward_type,
                "wallet_amount": rule.wallet_amount,
                "reward_text": reward_text,
                "qualified_count": qualified,
            }
        )
    return ReferralsOut(
        referral_code=code,
        referral_link=referral_link,
        share_text=str(share_text),
        message_text=str(message_text),
        total_referrals=total,
        rules=rule_progress,
    )
