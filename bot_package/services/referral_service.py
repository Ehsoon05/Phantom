from datetime import datetime, timezone

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Config,
    Purchase,
    ReferralRewardGrant,
    ReferralRewardRule,
    ShopPlan,
    Transaction,
    User,
)
from .inventory_service import InventoryService
from .subscription_link_service import SubscriptionLinkService


def _base36(value: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    result = ""
    while value:
        value, remainder = divmod(value, 36)
        result = alphabet[remainder] + result
    return result


class ReferralService:
    QUALIFICATION_LABELS = {
        "joined": "عضویت و پذیرش قوانین",
        "wallet_charged": "حداقل یک شارژ کیف پول",
        "purchased": "حداقل یک خرید سرویس",
        "purchased_and_charged": "حداقل یک خرید و یک شارژ کیف پول",
    }
    REWARD_LABELS = {
        "wallet": "اعتبار کیف پول",
        "service": "سرویس رایگان",
    }
    TOPUP_TRANSACTION_TYPES = ("charge", "crypto_charge", "rial_charge")

    @staticmethod
    def build_referral_code(telegram_id: int) -> str:
        return f"p{_base36(abs(telegram_id))}"

    @staticmethod
    async def ensure_referral_code(session: AsyncSession, user: User) -> str:
        if not user.referral_code:
            user.referral_code = ReferralService.build_referral_code(user.telegram_id)
            await session.flush()
        return user.referral_code

    @staticmethod
    async def apply_start_payload(session: AsyncSession, user: User, payload: str | None) -> bool:
        if not payload or user.referred_by_user_id:
            return False
        if not payload.startswith("ref_"):
            return False

        code = payload.removeprefix("ref_").strip().lower()
        if not code:
            return False

        result = await session.execute(select(User).where(func.lower(User.referral_code) == code))
        referrer = result.scalar_one_or_none()
        if not referrer or referrer.telegram_id == user.telegram_id:
            return False

        user.referred_by_user_id = referrer.telegram_id
        user.referred_at = datetime.now(timezone.utc)
        await session.flush()
        return True

    @staticmethod
    async def count_referrals(session: AsyncSession, telegram_id: int) -> int:
        result = await session.execute(
            select(func.count(User.id)).where(User.referred_by_user_id == telegram_id)
        )
        return int(result.scalar() or 0)

    @staticmethod
    def _qualification_condition(qualification_type: str):
        has_purchase = exists(
            select(Purchase.id).where(
                Purchase.user_id == User.telegram_id,
                Purchase.price > 0,
                Purchase.category_key != "trial",
            )
        )
        has_charge = exists(
            select(Transaction.id).where(
                Transaction.user_id == User.telegram_id,
                Transaction.amount > 0,
                Transaction.type.in_(ReferralService.TOPUP_TRANSACTION_TYPES),
            )
        )
        if qualification_type == "joined":
            return User.accepted_rules_at.is_not(None)
        if qualification_type == "wallet_charged":
            return has_charge
        if qualification_type == "purchased":
            return has_purchase
        if qualification_type == "purchased_and_charged":
            return and_(has_purchase, has_charge)
        return User.id == -1

    @staticmethod
    async def count_qualified(
        session: AsyncSession,
        referrer_user_id: int,
        qualification_type: str,
    ) -> int:
        result = await session.execute(
            select(func.count(User.id)).where(
                User.referred_by_user_id == referrer_user_id,
                ReferralService._qualification_condition(qualification_type),
            )
        )
        return int(result.scalar() or 0)

    @staticmethod
    async def list_rules(session: AsyncSession, *, active_only: bool = False) -> list[ReferralRewardRule]:
        stmt = select(ReferralRewardRule).order_by(ReferralRewardRule.id)
        if active_only:
            stmt = stmt.where(ReferralRewardRule.is_active.is_(True))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def create_rule(
        session: AsyncSession,
        *,
        title: str,
        qualification_type: str,
        required_count: int,
        is_repeatable: bool,
        reward_type: str,
        created_by: int,
        wallet_amount: int | None = None,
        shop_plan_id: int | None = None,
    ) -> ReferralRewardRule:
        if qualification_type not in ReferralService.QUALIFICATION_LABELS:
            raise ValueError("Invalid referral qualification")
        if reward_type not in ReferralService.REWARD_LABELS:
            raise ValueError("Invalid referral reward")
        if required_count <= 0:
            raise ValueError("Required referral count must be positive")
        if reward_type == "wallet" and (wallet_amount is None or wallet_amount <= 0):
            raise ValueError("Wallet reward must be positive")
        if reward_type == "service":
            plan = await session.get(ShopPlan, shop_plan_id)
            if plan is None:
                raise ValueError("Referral reward plan does not exist")

        rule = ReferralRewardRule(
            title=title.strip(),
            qualification_type=qualification_type,
            required_count=required_count,
            is_repeatable=is_repeatable,
            reward_type=reward_type,
            wallet_amount=wallet_amount if reward_type == "wallet" else None,
            shop_plan_id=shop_plan_id if reward_type == "service" else None,
            created_by=created_by,
        )
        session.add(rule)
        await session.flush()
        return rule

    @staticmethod
    async def toggle_rule(session: AsyncSession, rule_id: int) -> ReferralRewardRule | None:
        rule = await session.get(ReferralRewardRule, rule_id)
        if rule:
            rule.is_active = not rule.is_active
            rule.updated_at = datetime.now(timezone.utc)
            await session.commit()
        return rule

    @staticmethod
    async def delete_rule(session: AsyncSession, rule_id: int) -> bool:
        rule = await session.get(ReferralRewardRule, rule_id)
        if not rule:
            return False
        await session.delete(rule)
        await session.commit()
        return True

    @staticmethod
    async def evaluate_referrer(session: AsyncSession, referrer_user_id: int) -> list[dict]:
        referrer = (
            await session.execute(
                select(User).where(User.telegram_id == referrer_user_id).with_for_update()
            )
        ).scalar_one_or_none()
        if not referrer:
            return []

        rewards: list[dict] = []
        for rule in await ReferralService.list_rules(session, active_only=True):
            qualified_count = await ReferralService.count_qualified(
                session, referrer_user_id, rule.qualification_type
            )
            if qualified_count < rule.required_count:
                continue

            milestones = (
                range(rule.required_count, qualified_count + 1, rule.required_count)
                if rule.is_repeatable
                else (rule.required_count,)
            )
            for milestone in milestones:
                existing = await session.execute(
                    select(ReferralRewardGrant.id).where(
                        ReferralRewardGrant.rule_id == rule.id,
                        ReferralRewardGrant.referrer_user_id == referrer_user_id,
                        ReferralRewardGrant.milestone_count == milestone,
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    continue

                grant = ReferralRewardGrant(
                    rule_id=rule.id,
                    referrer_user_id=referrer_user_id,
                    milestone_count=milestone,
                    qualified_count=qualified_count,
                    reward_type=rule.reward_type,
                )
                if rule.reward_type == "wallet":
                    amount = int(rule.wallet_amount or 0)
                    referrer.wallet_balance = (referrer.wallet_balance or 0) + amount
                    grant.wallet_amount = amount
                    session.add(
                        Transaction(
                            user_id=referrer_user_id,
                            amount=amount,
                            type="referral_reward",
                            description=f"پاداش رفرال: {rule.title} - مرحله {milestone}",
                        )
                    )
                    reward_text = f"{amount:,} تومان اعتبار کیف پول"
                else:
                    plan = await session.get(ShopPlan, rule.shop_plan_id)
                    if not plan:
                        continue
                    config = await InventoryService.get_available_config(
                        session, plan.volume_gb, plan.category_key or "default"
                    )
                    if not config or not await InventoryService.sell_config(session, config, referrer_user_id):
                        continue
                    purchase = Purchase(
                        user_id=referrer_user_id,
                        config_id=config.id,
                        volume_gb=plan.volume_gb,
                        category_key=plan.category_key or "default",
                        price=0,
                        original_price=0,
                        discount_amount=0,
                        service_name=f"جایزه رفرال - {rule.title}",
                    )
                    session.add(purchase)
                    await session.flush()
                    grant.config_id = config.id
                    grant.purchase_id = purchase.id
                    await SubscriptionLinkService.ensure_public_token(session, config)
                    reward_text = f"سرویس رایگان {plan.title}"

                session.add(grant)
                await session.flush()
                rewards.append(
                    {
                        "rule": rule.title,
                        "milestone": milestone,
                        "qualified_count": qualified_count,
                        "reward": reward_text,
                        "config": config if rule.reward_type == "service" else None,
                        "service_name": purchase.service_name if rule.reward_type == "service" else None,
                    }
                )
        return rewards

    @staticmethod
    async def evaluate_referred_user(session: AsyncSession, referred_user_id: int) -> list[dict]:
        result = await session.execute(
            select(User.referred_by_user_id).where(User.telegram_id == referred_user_id)
        )
        referrer_user_id = result.scalar_one_or_none()
        if not referrer_user_id:
            return []
        return await ReferralService.evaluate_referrer(session, int(referrer_user_id))

    @staticmethod
    async def evaluate_all_referrers(session: AsyncSession) -> list[dict]:
        result = await session.execute(
            select(User.referred_by_user_id)
            .where(User.referred_by_user_id.is_not(None))
            .distinct()
        )
        rewards: list[dict] = []
        for referrer_user_id in result.scalars().all():
            rewards.extend(
                await ReferralService.evaluate_referrer(session, int(referrer_user_id))
            )
        return rewards

    @staticmethod
    async def referral_map(session: AsyncSession) -> list[tuple[int, int, datetime | None]]:
        result = await session.execute(
            select(User.telegram_id, User.referred_by_user_id, User.referred_at)
            .where(User.referred_by_user_id.is_not(None))
            .order_by(User.referred_at.desc())
        )
        return [(int(row[0]), int(row[1]), row[2]) for row in result.all()]
