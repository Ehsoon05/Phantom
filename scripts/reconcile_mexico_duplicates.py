import argparse
import asyncio
from collections import defaultdict
import re

from sqlalchemy import select

from bot_package.database import async_session
from bot_package.models import Config, ProvisionPanel, ShopPlan
from bot_package.services.mexico_panel_maintenance_service import (
    MexicoPanelMaintenanceService,
    _desired_device_limit,
    _recovery_base_username,
)
from bot_package.services.provisioning_service import (
    MEXICO_PANEL_KEYS,
    MEXICO_UNLIMITED_DATA_LIMIT_BYTES,
    ProvisioningService,
    _panel_error,
)
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
            canonical = await MexicoPanelMaintenanceService._get_user(
                panels[config.panel_key],
                base,
            )
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


async def merge_orphan_groups(*, apply: bool) -> dict[str, int]:
    stats = {"groups": 0, "rebound": 0, "deleted": 0, "failed": 0}
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
    grouped = defaultdict(list)
    for config in configs:
        username = str(config.panel_username or "")
        if re.search(r"_r[0-9]+$", username):
            grouped[(config.panel_key, _recovery_base_username(username))].append(config)

    for (panel_key, base), rows in grouped.items():
        usernames = sorted({str(row.panel_username) for row in rows})
        users = panel_users.get(panel_key or "", {})
        existing = [username for username in usernames if username in users]
        if base in users or len(existing) < 2:
            continue
        stats["groups"] += 1
        canonical_username = min(
            existing,
            key=lambda name: min(row.id for row in rows if row.panel_username == name),
        )
        print(f"{panel_key}: {', '.join(existing)} -> {canonical_username}")
        if not apply:
            continue
        canonical = await MexicoPanelMaintenanceService._get_user(
            panels[panel_key],
            canonical_username,
        )
        for duplicate_username in existing:
            if duplicate_username == canonical_username:
                continue
            duplicate_rows = [row for row in rows if row.panel_username == duplicate_username]
            try:
                for row in duplicate_rows:
                    async with async_session() as session:
                        current = await session.get(Config, row.id)
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
                            panels[panel_key],
                            current,
                            plan,
                            canonical,
                            device_limit,
                        )
                        await session.commit()
                    stats["rebound"] += 1
                await _delete_user(panels[panel_key], duplicate_username)
                stats["deleted"] += 1
            except Exception as exc:  # noqa: BLE001
                stats["failed"] += 1
                print(f"FAILED {duplicate_username}: {exc}")
    return stats


async def reconcile_cross_panel_unlimited(*, apply: bool) -> dict[str, int]:
    stats = {"groups": 0, "configs_rebound": 0, "source_deleted": 0, "failed": 0}
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

    hajmi_panel = panels.get("mexico_hajmi")
    namahdod_panel = panels.get("mexico_namahdod")
    if hajmi_panel is None or namahdod_panel is None:
        raise RuntimeError("Both Mexico panels must be enabled")
    hajmi_users = await MexicoPanelMaintenanceService._list_users(hajmi_panel)
    namahdod_users = await MexicoPanelMaintenanceService._list_users(namahdod_panel)
    namahdod_by_root = {
        _recovery_base_username(username).casefold(): username
        for username in namahdod_users
    }

    for source_config in configs:
        if source_config.panel_key != "mexico_hajmi":
            continue
        source_username = str(source_config.panel_username or "")
        if not re.search(r"_r[0-9]+$", source_username):
            continue
        root = _recovery_base_username(source_username).casefold()
        target_username = namahdod_by_root.get(root)
        source_payload = hajmi_users.get(source_username)
        target_summary = namahdod_users.get(target_username or "")
        if source_payload is None or target_summary is None or not target_username:
            continue
        source_expire = str(source_payload.get("expire") or "")
        target_expire = str(target_summary.get("expire") or "")
        if source_expire and target_expire and source_expire != target_expire:
            continue

        related = [
            row
            for row in configs
            if row.id == source_config.id
            or (
                row.panel_key == "mexico_namahdod"
                and _recovery_base_username(row.panel_username or "").casefold() == root
            )
        ]
        desired_limit = max(
            _desired_device_limit(
                row,
                plans.get(row.shop_plan_id),
                synced.get(row.public_sub_token or ""),
            )
            for row in related
        )
        stats["groups"] += 1
        print(
            f"{source_username} ({hajmi_panel.title}) -> "
            f"{target_username} ({namahdod_panel.title}), configs={len(related)}, hwid={desired_limit}"
        )
        if not apply:
            continue

        try:
            target_payload = await MexicoPanelMaintenanceService._get_user(
                namahdod_panel,
                target_username,
            )
            update = {}
            if int(target_payload.get("hwid_limit") or 0) != desired_limit:
                update["hwid_limit"] = desired_limit
            if int(target_payload.get("data_limit") or 0) != MEXICO_UNLIMITED_DATA_LIMIT_BYTES:
                update["data_limit"] = MEXICO_UNLIMITED_DATA_LIMIT_BYTES
                update["data_limit_reset_strategy"] = "no_reset"
            if update:
                async with ProvisioningService._api_client(namahdod_panel) as (client, token):
                    response = await client.put(
                        f"/api/user/{target_username}",
                        headers={"Authorization": f"Bearer {token}"},
                        json=update,
                    )
                    if response.is_error:
                        raise _panel_error(response, f"به‌روزرسانی {target_username}")
                target_payload = await MexicoPanelMaintenanceService._get_user(
                    namahdod_panel,
                    target_username,
                )

            for row in related:
                async with async_session() as session:
                    current = await session.get(Config, row.id)
                    if current is None:
                        continue
                    current.panel_key = "mexico_namahdod"
                    current.panel_username = target_username
                    current.display_total_bytes = 0
                    current.usage_offset_bytes = 0
                    current.subscription_device_limit = desired_limit
                    await MexicoPanelMaintenanceService._bind_config_to_existing(
                        session,
                        namahdod_panel,
                        current,
                        plans.get(current.shop_plan_id),
                        target_payload,
                        desired_limit,
                    )
                    await session.commit()
                stats["configs_rebound"] += 1
            await _delete_user(hajmi_panel, source_username)
            stats["source_deleted"] += 1
        except Exception as exc:  # noqa: BLE001
            stats["failed"] += 1
            print(f"FAILED {source_username}: {exc}")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--merge-orphan-groups", action="store_true")
    parser.add_argument("--cross-panel-unlimited", action="store_true")
    args = parser.parse_args()
    if args.cross_panel_unlimited:
        print(asyncio.run(reconcile_cross_panel_unlimited(apply=args.apply)))
    elif args.merge_orphan_groups:
        print(asyncio.run(merge_orphan_groups(apply=args.apply)))
    else:
        print(asyncio.run(reconcile(apply=args.apply)))


if __name__ == "__main__":
    main()
