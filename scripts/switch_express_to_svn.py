#!/usr/bin/env python3
"""Point existing Express subscriptions at their already-created SVN users."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot_package.database import async_session
from bot_package.models import Config, PanelBridgeAssignment, Purchase, ShopPlan
from bot_package.services.subscription_link_service import SubscriptionLinkService


def cached_mmd_usage(url: str) -> int | None:
    path = Path('/opt/phantom-subscription-panel/subscription-cache') / (
        hashlib.sha256(url.encode()).hexdigest() + '.json'
    )
    try:
        usage = json.loads(path.read_text()).get('usage') or {}
        return max(0, int(usage.get('upload') or 0) + int(usage.get('download') or 0))
    except (OSError, ValueError, TypeError):
        return None


async def main() -> None:
    async with async_session() as session:
        rows = (
            await session.execute(
                select(Config.id)
                .where(
                    Config.category_key == 'express',
                    Config.panel_key == 'mmd',
                    Config.is_sold.is_(True),
                    Config.panel_deleted_at.is_(None),
                )
                .order_by(Config.id)
            )
        ).scalars().all()
    print('candidates', len(rows), flush=True)
    done = 0
    skipped = []
    for config_id in rows:
        async with async_session() as session:
            config = await session.get(Config, config_id)
            assignment = (
                await session.execute(
                    select(PanelBridgeAssignment).where(
                        PanelBridgeAssignment.config_id == config_id,
                        PanelBridgeAssignment.rule_id == 2,
                        PanelBridgeAssignment.status == 'active',
                    )
                )
            ).scalar_one_or_none()
            if not config or not assignment or not assignment.target_sub_link:
                skipped.append((config_id, 'no SVN assignment'))
                continue
            if assignment.target_username != config.panel_username and not assignment.target_created:
                skipped.append((config_id, 'unowned target username'))
                continue
            old_usage = cached_mmd_usage(config.sub_link)
            if old_usage is None:
                skipped.append((config_id, 'no MMD usage cache'))
                continue
            purchase = (
                await session.execute(
                    select(Purchase)
                    .where(Purchase.config_id == config_id, Purchase.kind == 'purchase')
                    .order_by(Purchase.id.desc())
                )
            ).scalars().first()
            plan = await session.get(ShopPlan, config.shop_plan_id) if config.shop_plan_id else None
            config.sub_link = assignment.target_sub_link
            config.panel_key = 'svn'
            config.panel_username = assignment.target_username
            config.usage_offset_bytes = old_usage
            config.display_total_bytes = config.display_total_bytes or config.volume_gb * 1024**3
            if not await SubscriptionLinkService.sync_to_panel(
                config,
                purchase.service_name if purchase else None,
                device_limit=config.subscription_device_limit,
                show_config_preview=plan.show_subscription_configs if plan else None,
            ):
                skipped.append((config_id, 'subscription sync failed'))
                continue
            if not await SubscriptionLinkService.sync_supplements(
                config.public_sub_token, [], info_proxies_enabled=True
            ):
                skipped.append((config_id, 'supplement sync failed'))
                continue
            await session.commit()
            done += 1
            print('migrated', config_id, flush=True)
    print('complete', done, 'skipped', skipped, flush=True)


if __name__ == '__main__':
    asyncio.run(main())
