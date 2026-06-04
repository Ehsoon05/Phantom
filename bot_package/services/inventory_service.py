
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from ..models import Config, Price
from typing import List, Optional
from datetime import datetime, timezone, timedelta

class InventoryService:
    @staticmethod
    async def add_configs(session: AsyncSession, volume_gb: int, links: List[str]) -> int:
        added_count = 0
        for link in links:
            stmt = select(Config).where(Config.sub_link == link)
            result = await session.execute(stmt)
            if result.scalar_one_or_none() is None:
                new_config = Config(volume_gb=volume_gb, sub_link=link)
                session.add(new_config)
                added_count += 1
        await session.commit()
        return added_count
    
    @staticmethod
    async def get_stock_status(session: AsyncSession) -> dict:
        stmt = (
            select(Config.volume_gb, func.count(Config.id))
            .where(Config.is_sold == False)
            .group_by(Config.volume_gb)
        )
        result = await session.execute(stmt)
        stock = {row[0]: row[1] for row in result.fetchall()}
        price_result = await session.execute(select(Price.volume_gb).order_by(Price.volume_gb))
        for vol in price_result.scalars().all():
            stock.setdefault(vol, 0)
        return dict(sorted(stock.items()))
    
    @staticmethod
    async def get_available_config(session: AsyncSession, volume_gb: int) -> Optional[Config]:
        stmt = (
            select(Config)
            .where(Config.volume_gb == volume_gb, Config.is_sold == False)
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def sell_config(session: AsyncSession, config: Config, user_id: int):
        stmt = (
            update(Config)
            .where(Config.id == config.id, Config.is_sold == False)
            .values(
                is_sold=True,
                sold_to_user_id=user_id,
                sold_at=datetime.now(timezone.utc),
            )
        )
        result = await session.execute(stmt)
        if result.rowcount != 1:
            return False
        await session.refresh(config)
        return True
    
    @staticmethod
    async def get_sold_configs_by_period(session: AsyncSession, days: int) -> List[Config]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = select(Config).where(Config.is_sold == True, Config.sold_at >= since)
        result = await session.execute(stmt)
        return result.scalars().all()
