from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models import Price, ShopPlan
from typing import Dict, Optional
from datetime import datetime, timezone

class PriceService:
    @staticmethod
    async def init_default_prices(session: AsyncSession):
        defaults = {1: 15000, 2: 28000, 3: 40000, 5: 65000, 10: 120000, 20: 220000}
        for vol, price in defaults.items():
            stmt = select(Price).where(Price.volume_gb == vol)
            result = await session.execute(stmt)
            if not result.scalar_one_or_none():
                session.add(Price(volume_gb=vol, price=price))
        await session.commit()
    
    @staticmethod
    async def get_all_prices(session: AsyncSession) -> Dict[int, int]:
        plans_result = await session.execute(select(ShopPlan).order_by(ShopPlan.id))
        plans = plans_result.scalars().all()
        if plans:
            legacy_prices = await PriceService.get_legacy_prices(session)
            return {
                plan.id: plan.price if plan.price and plan.price > 0 else legacy_prices.get(plan.volume_gb, 0)
                for plan in plans
            }

        stmt = select(Price).order_by(Price.volume_gb)
        result = await session.execute(stmt)
        prices = result.scalars().all()
        return {p.volume_gb: p.price for p in prices}
    
    @staticmethod
    async def get_legacy_prices(session: AsyncSession) -> Dict[int, int]:
        stmt = select(Price).order_by(Price.volume_gb)
        result = await session.execute(stmt)
        return {price.volume_gb: price.price for price in result.scalars().all()}

    @staticmethod
    async def get_price(session: AsyncSession, volume_gb: int, category_key: str | None = None) -> Optional[int]:
        if category_key:
            plan_result = await session.execute(
                select(ShopPlan).where(ShopPlan.volume_gb == volume_gb, ShopPlan.category_key == category_key)
            )
            plan = plan_result.scalar_one_or_none()
            if plan and plan.price and plan.price > 0:
                return plan.price

        stmt = select(Price).where(Price.volume_gb == volume_gb)
        result = await session.execute(stmt)
        price_obj = result.scalar_one_or_none()
        return price_obj.price if price_obj else None

    @staticmethod
    async def get_plan_price(session: AsyncSession, plan: ShopPlan) -> Optional[int]:
        if plan.price and plan.price > 0:
            return plan.price
        return await PriceService.get_price(session, plan.volume_gb)
    
    @staticmethod
    async def update_price(session: AsyncSession, volume_gb: int, new_price: int, category_key: str | None = None) -> bool:
        if new_price <= 0:
            return False

        if category_key:
            plan_result = await session.execute(
                select(ShopPlan).where(ShopPlan.volume_gb == volume_gb, ShopPlan.category_key == category_key)
            )
            plan = plan_result.scalar_one_or_none()
            if plan:
                plan.price = new_price
                plan.updated_at = datetime.now(timezone.utc)
                await session.commit()
                return True

        stmt = select(Price).where(Price.volume_gb == volume_gb)
        result = await session.execute(stmt)
        price_obj = result.scalar_one_or_none()
        if price_obj:
            price_obj.price = new_price
            price_obj.updated_at = datetime.now(timezone.utc)
            await session.commit()
            return True
        return False
