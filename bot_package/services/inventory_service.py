
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, func, or_, select, update
from ..models import Config, ShopPlan
from .subscription_link_service import SubscriptionLinkService
from typing import List, Optional
from datetime import datetime, timezone, timedelta

class InventoryService:
    @staticmethod
    async def add_configs(
        session: AsyncSession,
        volume_gb: int,
        links: List[str],
        category_key: str = "default",
        plan_id: int | None = None,
    ) -> int:
        plan = await session.get(ShopPlan, plan_id) if plan_id else None
        device_limit = max(0, int(plan.subscription_device_limit or 0)) if plan else None
        added_count = 0
        for link in links:
            stmt = select(Config).where(Config.sub_link == link)
            result = await session.execute(stmt)
            if result.scalar_one_or_none() is None:
                new_config = Config(
                    shop_plan_id=plan_id,
                    volume_gb=volume_gb,
                    category_key=category_key,
                    sub_link=link,
                )
                session.add(new_config)
                await session.flush()
                await SubscriptionLinkService.ensure_public_token(session, new_config)
                await SubscriptionLinkService.sync_to_panel(
                    new_config,
                    device_limit=device_limit,
                    show_config_preview=plan.show_subscription_configs if plan else None,
                )
                added_count += 1
        await session.commit()
        return added_count
    
    @staticmethod
    async def get_stock_status(session: AsyncSession) -> list[tuple[int, str, int, str, int]]:
        stmt = (
            select(Config.shop_plan_id, func.count(Config.id))
            .where(Config.is_sold == False)
            .group_by(Config.shop_plan_id)
        )
        result = await session.execute(stmt)
        stock = {row[0]: row[1] for row in result.fetchall() if row[0] is not None}
        legacy_stmt = (
            select(Config.category_key, Config.volume_gb, func.count(Config.id))
            .where(Config.is_sold == False, Config.shop_plan_id.is_(None))
            .group_by(Config.category_key, Config.volume_gb)
        )
        legacy_stock = {
            (row[0] or "default", row[1]): row[2]
            for row in (await session.execute(legacy_stmt)).fetchall()
        }
        plans_result = await session.execute(
            select(ShopPlan).order_by(ShopPlan.category_key, ShopPlan.display_order, ShopPlan.volume_gb)
        )
        rows = []
        claimed_legacy_products: set[tuple[str, int]] = set()
        for plan in plans_result.scalars().all():
            key = plan.category_key or "default"
            legacy_key = (key, plan.volume_gb)
            legacy_count = 0
            if legacy_key not in claimed_legacy_products:
                legacy_count = legacy_stock.get(legacy_key, 0)
                claimed_legacy_products.add(legacy_key)
            rows.append(
                (plan.id, key, plan.volume_gb, plan.title, stock.get(plan.id, 0) + legacy_count)
            )
        return rows
    
    @staticmethod
    async def get_available_config(
        session: AsyncSession,
        volume_gb: int,
        category_key: str = "default",
        plan_id: int | None = None,
    ) -> Optional[Config]:
        product_filter = (
            or_(
                Config.shop_plan_id == plan_id,
                and_(
                    Config.shop_plan_id.is_(None),
                    Config.volume_gb == volume_gb,
                    Config.category_key == category_key,
                ),
            )
            if plan_id is not None
            else and_(Config.volume_gb == volume_gb, Config.category_key == category_key)
        )
        stmt = (
            select(Config)
            .where(product_filter, Config.is_sold == False)
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
