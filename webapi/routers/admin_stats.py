from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot_package.models import Admin, Purchase
from bot_package.services.inventory_service import InventoryService
from bot_package.services.user_service import UserService

from ..deps import get_session, require_permission
from ..schemas import AdminStatsOut

router = APIRouter(prefix="/admin/stats", tags=["admin"])
TEHRAN = ZoneInfo("Asia/Tehran")


def _tehran_range(days: int) -> tuple[datetime, datetime]:
    today = datetime.now(TEHRAN).date()
    start = datetime.combine(today - timedelta(days=days - 1), time.min, TEHRAN)
    end = datetime.combine(today + timedelta(days=1), time.min, TEHRAN)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


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
    cutoff, end = _tehran_range(days)
    rows = (
        await session.execute(
            select(Purchase.purchased_at, Purchase.price).where(
                Purchase.purchased_at >= cutoff,
                Purchase.purchased_at < end,
            )
        )
    ).all()
    # Bucket per Iran calendar day in Python — portable across SQLite and Postgres.
    buckets: dict[str, dict] = {}
    for purchased_at, price in rows:
        if purchased_at.tzinfo is None:
            purchased_at = purchased_at.replace(tzinfo=timezone.utc)
        key = purchased_at.astimezone(TEHRAN).date().isoformat()
        bucket = buckets.setdefault(key, {"date": key, "revenue_toman": 0, "purchases": 0})
        bucket["revenue_toman"] += price
        bucket["purchases"] += 1
    return sorted(buckets.values(), key=lambda b: b["date"])


@router.get("/sales-daily")
async def sales_daily(
    days: int = Query(default=45, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("reports")),
):
    start, end = _tehran_range(days)
    purchases = (
        await session.execute(
            select(Purchase).where(Purchase.purchased_at >= start, Purchase.purchased_at < end)
        )
    ).scalars().all()
    buckets: dict[str, dict] = {}
    for purchase in purchases:
        purchased_at = purchase.purchased_at
        if purchased_at.tzinfo is None:
            purchased_at = purchased_at.replace(tzinfo=timezone.utc)
        key = purchased_at.astimezone(TEHRAN).date().isoformat()
        bucket = buckets.setdefault(
            key,
            {
                "date": key,
                "revenue_toman": 0,
                "sales": 0,
                "renewals": 0,
                "inventory": 0,
                "panel": 0,
            },
        )
        bucket["revenue_toman"] += purchase.price
        if purchase.kind == "renewal":
            bucket["renewals"] += 1
        else:
            bucket["sales"] += 1
        if purchase.provision_source == "panel":
            bucket["panel"] += 1
        else:
            bucket["inventory"] += 1
    return sorted(buckets.values(), key=lambda b: b["date"])


@router.get("/sales-report")
async def sales_report(
    days: int = Query(default=45, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("reports")),
):
    start, end = _tehran_range(days)
    purchases = (
        await session.execute(
            select(Purchase).where(Purchase.purchased_at >= start, Purchase.purchased_at < end)
        )
    ).scalars().all()
    purchases = sorted(purchases, key=lambda item: item.purchased_at, reverse=True)

    summary = {
        "days": days,
        "total_transactions": len(purchases),
        "sales": 0,
        "renewals": 0,
        "inventory": 0,
        "panel": 0,
        "revenue_toman": 0,
    }
    by_category: dict[str, dict] = {}
    by_service: dict[str, dict] = {}
    by_source: dict[str, dict] = {}
    by_kind: dict[str, dict] = {}
    daily: dict[str, dict] = {}

    for purchase in purchases:
        price = purchase.price or 0
        summary["revenue_toman"] += price
        kind = "renewal" if purchase.kind == "renewal" else "purchase"
        source = "panel" if purchase.provision_source == "panel" else "inventory"
        category = purchase.category_key or "default"
        service = purchase.service_name or f"{purchase.volume_gb}GB"
        if kind == "renewal":
            summary["renewals"] += 1
        else:
            summary["sales"] += 1
        summary[source] += 1

        for bucket_map, key in (
            (by_category, category),
            (by_service, service),
            (by_source, source),
            (by_kind, kind),
        ):
            bucket = bucket_map.setdefault(key, {"key": key, "count": 0, "revenue_toman": 0})
            bucket["count"] += 1
            bucket["revenue_toman"] += price

        purchased_at = purchase.purchased_at
        if purchased_at.tzinfo is None:
            purchased_at = purchased_at.replace(tzinfo=timezone.utc)
        date_key = purchased_at.astimezone(TEHRAN).date().isoformat()
        day = daily.setdefault(
            date_key,
            {
                "date": date_key,
                "revenue_toman": 0,
                "sales": 0,
                "renewals": 0,
                "inventory": 0,
                "panel": 0,
            },
        )
        day["revenue_toman"] += price
        if kind == "renewal":
            day["renewals"] += 1
        else:
            day["sales"] += 1
        day[source] += 1

    recent = []
    for purchase in purchases[:limit]:
        purchased_at = purchase.purchased_at
        if purchased_at.tzinfo is None:
            purchased_at = purchased_at.replace(tzinfo=timezone.utc)
        recent.append(
            {
                "id": purchase.id,
                "user_id": purchase.user_id,
                "service_name": purchase.service_name,
                "category_key": purchase.category_key,
                "volume_gb": purchase.volume_gb,
                "price": purchase.price,
                "kind": purchase.kind,
                "provision_source": purchase.provision_source,
                "purchased_at": purchased_at.astimezone(TEHRAN).isoformat(),
            }
        )

    def sorted_buckets(values: dict[str, dict]) -> list[dict]:
        return sorted(values.values(), key=lambda item: (item["count"], item["revenue_toman"]), reverse=True)

    return {
        "summary": summary,
        "daily": sorted(daily.values(), key=lambda item: item["date"]),
        "by_category": sorted_buckets(by_category),
        "by_service": sorted_buckets(by_service),
        "by_source": sorted_buckets(by_source),
        "by_kind": sorted_buckets(by_kind),
        "recent": recent,
    }


@router.get("/stock")
async def stock(
    session: AsyncSession = Depends(get_session),
    _admin: Admin = Depends(require_permission("inventory")),
):
    rows = await InventoryService.get_stock_status(session)
    return [
        {
            "plan_id": plan_id,
            "category_key": category,
            "volume_gb": volume,
            "title": title,
            "available": count,
        }
        for plan_id, category, volume, title, count in rows
    ]
