from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_package.models import Admin, Purchase
from bot_package.services.inventory_service import InventoryService
from bot_package.services.user_service import UserService

from ..deps import get_session, require_permission
from ..schemas import AdminStatsOut

router = APIRouter(prefix="/admin/stats", tags=["admin"])


@router.get("", response_model=AdminStatsOut)
async def stats(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("reports")),
):
    data = await UserService.get_user_stats(session)
    return AdminStatsOut(
        total_users=data.get("total_users", 0),
        new_users_today=data.get("new_today", 0),
        total_wallet_balance=data.get("total_balance", 0),
        total_gb_purchased=data.get("total_purchased_gb", 0),
        total_spent=data.get("total_spent", 0),
    )


@router.get("/sales")
async def sales(
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("reports")),
):
    sold = await InventoryService.get_sold_configs_by_period(session, days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    revenue, count = (
        await session.execute(
            select(func.coalesce(func.sum(Purchase.price), 0), func.count(Purchase.id)).where(
                Purchase.purchased_at >= cutoff
            )
        )
    ).one()
    return {"days": days, "configs_sold": len(sold), "purchases": count, "revenue_toman": revenue}


@router.get("/revenue-daily")
async def revenue_daily(
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("reports")),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        await session.execute(
            select(Purchase.purchased_at, Purchase.price).where(Purchase.purchased_at >= cutoff)
        )
    ).all()
    # Bucket per calendar day in Python — portable across SQLite and Postgres.
    buckets: dict[str, dict] = {}
    for purchased_at, price in rows:
        key = purchased_at.date().isoformat()
        bucket = buckets.setdefault(key, {"date": key, "revenue_toman": 0, "purchases": 0})
        bucket["revenue_toman"] += price
        bucket["purchases"] += 1
    return sorted(buckets.values(), key=lambda b: b["date"])


@router.get("/stock")
async def stock(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("inventory")),
):
    rows = await InventoryService.get_stock_status(session)
    return [
        {"category_key": category, "volume_gb": volume, "title": title, "available": count}
        for category, volume, title, count in rows
    ]
