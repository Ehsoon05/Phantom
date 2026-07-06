from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from ..models import User, Transaction, Purchase
from typing import Optional

class UserService:
    @staticmethod
    async def search_user(session: AsyncSession, query: str) -> Optional[User]:
        query = (query or "").strip()
        if query.isdigit():
            stmt = select(User).where(User.telegram_id == int(query))
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                return user
        
        username = query.lstrip('@').strip()
        if not username:
            return None
        stmt = select(User).where(func.lower(User.username) == username.lower())
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def charge_wallet(session: AsyncSession, telegram_id: int, amount: int, admin_id: int) -> bool:
        if amount <= 0:
            return False

        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            return False
        
        user.wallet_balance += amount
        transaction = Transaction(
            user_id=telegram_id,
            amount=amount,
            type="charge",
            description=f"شارژ توسط ادمین {admin_id}"
        )
        session.add(transaction)
        await session.flush()
        from .referral_service import ReferralService
        from .subscription_link_service import SubscriptionLinkService

        rewards = await ReferralService.evaluate_referred_user(session, telegram_id)
        await session.commit()
        for reward in rewards:
            if reward["config"] is not None:
                await SubscriptionLinkService.sync_to_panel(reward["config"], reward["service_name"])
        return True

    @staticmethod
    async def set_wallet_balance(session: AsyncSession, telegram_id: int, balance: int, admin_id: int) -> bool:
        if balance < 0:
            return False

        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            return False

        old_balance = user.wallet_balance or 0
        difference = balance - old_balance
        user.wallet_balance = balance
        transaction = Transaction(
            user_id=telegram_id,
            amount=difference,
            type="wallet_set",
            description=f"تنظیم موجودی توسط ادمین {admin_id}: {old_balance} -> {balance}",
        )
        session.add(transaction)
        await session.commit()
        return True
    
    @staticmethod
    async def get_user_stats(session: AsyncSession) -> dict:
        from datetime import datetime, timezone
        
        total_users = await session.execute(select(func.count(User.id)))
        total_users = total_users.scalar()
        
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        new_today = await session.execute(
            select(func.count(User.id)).where(User.created_at >= today)
        )
        new_today = new_today.scalar()
        
        total_balance = await session.execute(select(func.sum(User.wallet_balance)))
        total_balance = total_balance.scalar() or 0

        total_purchased_gb = await session.execute(select(func.sum(Purchase.volume_gb)))
        total_purchased_gb = total_purchased_gb.scalar() or 0

        total_spent = await session.execute(select(func.sum(Purchase.price)))
        total_spent = total_spent.scalar() or 0
        
        return {
            "total_users": total_users,
            "new_today": new_today,
            "total_balance": total_balance,
            "total_purchased_gb": total_purchased_gb,
            "total_spent": total_spent,
        }

    @staticmethod
    async def get_user_purchase_summary(session: AsyncSession, telegram_id: int, limit: int = 10) -> dict:
        total_count = await session.execute(
            select(func.count(Purchase.id)).where(Purchase.user_id == telegram_id)
        )
        total_count = total_count.scalar() or 0

        total_gb = await session.execute(
            select(func.sum(Purchase.volume_gb)).where(Purchase.user_id == telegram_id)
        )
        total_gb = total_gb.scalar() or 0

        total_spent = await session.execute(
            select(func.sum(Purchase.price)).where(Purchase.user_id == telegram_id)
        )
        total_spent = total_spent.scalar() or 0

        result = await session.execute(
            select(Purchase)
            .options(selectinload(Purchase.config))
            .where(Purchase.user_id == telegram_id)
            .order_by(Purchase.purchased_at.desc())
            .limit(limit)
        )
        purchases = list(result.scalars().all())

        return {
            "total_count": total_count,
            "total_gb": total_gb,
            "total_spent": total_spent,
            "purchases": purchases,
        }
