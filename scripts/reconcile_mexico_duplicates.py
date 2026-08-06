import argparse
import asyncio
import re

from sqlalchemy import select

from bot_package.database import async_session
from bot_package.models import Config, ProvisionPanel, ShopPlan
from bot_package.services.mexico_panel_maintenance_service import (
    MexicoPanelMaintenanceService,
    _desired_device_limit,
    _recovery_base_username,
)
from bot_package.services.provisioning_service import MEXICO_PANEL_KEYS, ProvisioningService, _panel_error
from bot_package.services.subscription_link_service import SubscriptionLinkService


async def _delete_user(panel, username: str) -> None:
    async with ProvisioningService._api_client(panel) as (client, token):
        response = await client.delete(
            f"/api/user/{username}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code not in {200, 204, 404}:
            raise _panel_error(response, f"حذف نسخه تکراری {username}")


async def reconcile(*, apply: bool) -> dict[str, int]:
    stats = {"checked": 0, "candidates": 0, "rebound": 0, "deleted": 0, "failed": 0}
    synced = {
        str(item.get("token") or ""): item
        for item in await SubscriptionLinkService.list_panel_configs()
        if item.get("token")
    }
    async with async_session() as session:
        panels = {
            panel.key: panel
            for panel in (
                await session.execute(
                    select(ProvisionPanel).where(
                        ProvisionPanel.key.in_(MEXICO_PANEL_KEYS),
                        ProvisionPanel.is_enabled.is_(True),
                    )
                )
            ).scalars().all()
        }
        configs = list(
            (
                await session.execute(
                    select(Config).where(Config.panel_key.in_(MEXICO_PANEL_KEYS))
                )
            ).scalars().all()
        )
        plans = {
            plan.id: plan
            for plan in (
                await session.execute(
                    select(ShopPlan).where(
                        ShopPlan.id.in_([row.shop_plan_id for row in configs if row.shop_plan_id])
                    )
                )
            ).scalars().all()
        }

    panel_users = {
        key: await MexicoPanelMaintenanceService._list_users(panel)
        for key, panel in panels.items()
    }
    for config in configs:
        stats["checked"] += 1
        username = str(config.panel_username or "")
        if not re.search(r"_r[0-9]+$", username):
            continue
        base = _recovery_base_username(username)
        users = panel_users.get(config.panel_key or "", {})
        duplicate = users.get(username)
        canonical = users.get(base)
        if duplicate is None or canonical is None:
            continue
        stats["candidates"] += 1
        print(f"{config.panel_key}: {username} -> {base}")
        if not apply:
            continue
        try:
            async with async_session() as session:
                current = await session.get(Config, config.id)
                if current is None:
                    continue
                plan = plans.get(current.shop_plan_id)
                device_limit = _desired_device_limit(
                    current,
                    plan,
                    synced.get(current.public_sub_token or ""),
                )
                await MexicoPanelMaintenanceService._bind_config_to_existing(
                    session,
                    panels[current.panel_key],
                    current,
                    plan,
                    canonical,
                    device_limit,
                )
                await session.commit()
            stats["rebound"] += 1
            await _delete_user(panels[config.panel_key], username)
            stats["deleted"] += 1
        except Exception as exc:  # noqa: BLE001
            stats["failed"] += 1
            print(f"FAILED {username}: {exc}")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(asyncio.run(reconcile(apply=args.apply)))


if __name__ == "__main__":
    main()
