from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ..models import User, Transaction
from typing import Optional

class UserService:
    @staticmethod
    async def search_user(session: AsyncSession, query: str) -> Optional[User]:
        if query.isdigit():
            stmt = select(User).where(User.telegram_id == int(query))
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                return user
        
        username = query.lstrip('@')
        stmt = select(User).where(User.username == username)
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
        await session.commit()
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
        
        return {
            "total_users": total_users,
            "new_today": new_today,
            "total_balance": total_balance
        }
