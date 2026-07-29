#!/usr/bin/env python3
"""Migrate sold SVN subscriptions to MMD while preserving public links and usage."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select

from bot_package.database import async_session, engine
from bot_package.models import Config, ProvisionPanel, Purchase, ShopPlan
from bot_package.services.provisioning_service import (
    ProvisioningError,
    ProvisioningService,
    _subscription_url,
    username_from_subscription_url,
)
from bot_package.services.schema_service import SchemaService
from bot_package.services.subscription_link_service import SubscriptionLinkService


CONFIRMATION = "MIGRATE-SVN-TO-MMD"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-key", default="svn")
    parser.add_argument("--target-key", default="mmd")
    parser.add_argument("--category", default="express")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    return parser.parse_args()


def _target_status(source: dict, remaining: int | None) -> str:
    status = str(source.get("status") or "active").strip().lower()
    if status == "on_hold":
        return "on_hold"
    if status != "active" or remaining == 0:
        return "disabled"
    return "active"


def _timing(source: dict, status: str) -> dict:
    expire = max(0, int(source.get("expire") or 0))
    on_hold_duration = source.get("on_hold_expire_duration")
    if status == "on_hold":
        return {
            "status": "on_hold",
            "expire": 0,
            "on_hold_expire_duration": max(0, int(on_hold_duration or 0)) or None,
        }
    return {
        "status": status,
        "expire": expire,
        "on_hold_expire_duration": None,
    }


async def _latest_purchase(session, config_id: int) -> Purchase | None:
    return (
        await session.execute(
            select(Purchase)
            .where(Purchase.config_id == config_id, Purchase.kind == "purchase")
            .order_by(Purchase.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def run(args: argparse.Namespace) -> int:
    if args.apply and args.confirm != CONFIRMATION:
        print(f"Refusing apply: pass --confirm {CONFIRMATION}")
        return 2

    await SchemaService.ensure_schema(engine)
    summary: Counter[str] = Counter()
    async with async_session() as session:
        source_panel = await ProvisioningService.get_panel(session, args.source_key)
        target_panel = await ProvisioningService.get_panel(session, args.target_key)
        if source_panel is None or target_panel is None:
            raise ProvisioningError("Source or target panel is missing/disabled.")

        configs = (
            await session.execute(
                select(Config)
                .where(
                    Config.panel_key == args.source_key,
                    Config.category_key == args.category,
                    Config.is_sold.is_(True),
                    Config.panel_deleted_at.is_(None),
                )
                .order_by(Config.id)
            )
        ).scalars().all()

        async with ProvisioningService._api_client(source_panel) as (source_client, source_token):
            async with ProvisioningService._api_client(target_panel) as (target_client, target_token):
                source_headers = {"Authorization": f"Bearer {source_token}"}
                target_headers = {"Authorization": f"Bearer {target_token}"}
                access_fields = await ProvisioningService._access_fields(
                    target_client,
                    target_panel,
                    target_headers,
                )

                for config in configs:
                    username = config.panel_username or username_from_subscription_url(config.sub_link)
                    if not username:
                        summary["missing_username"] += 1
                        continue

                    source_response = await source_client.get(
                        f"/api/user/{username}",
                        headers=source_headers,
                    )
                    if source_response.status_code == 404:
                        summary["missing_source"] += 1
                        continue
                    if source_response.is_error:
                        summary[f"source_http_{source_response.status_code}"] += 1
                        continue
                    source = source_response.json()

                    data_limit = max(0, int(source.get("data_limit") or 0))
                    used_traffic = max(0, int(source.get("used_traffic") or 0))
                    remaining = max(data_limit - used_traffic, 0) if data_limit else None
                    target_limit = remaining if remaining is not None else 0
                    status = _target_status(source, remaining)
                    payload = {
                        "username": username,
                        "data_limit": target_limit if target_limit > 0 else (1 if remaining == 0 else 0),
                        "data_limit_reset_strategy": "no_reset",
                        **_timing(source, status),
                        **access_fields,
                    }

                    existing = await target_client.get(
                        f"/api/user/{username}",
                        headers=target_headers,
                    )
                    if existing.status_code == 404:
                        action = "create"
                    elif existing.is_error:
                        summary[f"target_http_{existing.status_code}"] += 1
                        continue
                    else:
                        action = "update"

                    if not args.apply:
                        summary[f"would_{action}"] += 1
                        summary[f"source_{source.get('status') or 'unknown'}"] += 1
                        continue

                    if action == "create":
                        target_response = await target_client.post(
                            "/api/user",
                            headers=target_headers,
                            json=payload,
                        )
                    else:
                        target_response = await target_client.put(
                            f"/api/user/{username}",
                            headers=target_headers,
                            json={key: value for key, value in payload.items() if key != "username"},
                        )
                    if target_response.is_error:
                        summary[f"target_write_{target_response.status_code}"] += 1
                        continue
                    target_lookup = await target_client.get(
                        f"/api/user/{username}",
                        headers=target_headers,
                    )
                    if target_lookup.is_error:
                        summary[f"target_lookup_{target_lookup.status_code}"] += 1
                        continue
                    target_user = target_lookup.json()

                    old_values = (
                        config.sub_link,
                        config.panel_key,
                        config.panel_username,
                        config.usage_offset_bytes,
                        config.display_total_bytes,
                    )
                    config.sub_link = _subscription_url(target_panel.base_url, target_user)
                    config.panel_key = target_panel.key
                    config.panel_username = username
                    config.usage_offset_bytes = used_traffic
                    config.display_total_bytes = data_limit if data_limit > 0 else None
                    config.expired_detected_at = None
                    config.deletion_due_at = None
                    config.panel_deleted_at = None
                    await SubscriptionLinkService.ensure_public_token(session, config)

                    purchase = await _latest_purchase(session, config.id)
                    plan = await session.get(ShopPlan, config.shop_plan_id) if config.shop_plan_id else None
                    synced = await SubscriptionLinkService.sync_to_panel(
                        config,
                        purchase.service_name if purchase else None,
                        device_limit=(
                            config.subscription_device_limit
                            if config.subscription_device_limit is not None
                            else (plan.subscription_device_limit if plan else None)
                        ),
                        show_config_preview=plan.show_subscription_configs if plan else None,
                    )
                    if not synced:
                        (
                            config.sub_link,
                            config.panel_key,
                            config.panel_username,
                            config.usage_offset_bytes,
                            config.display_total_bytes,
                        ) = old_values
                        await session.rollback()
                        summary["subscription_sync_failed"] += 1
                        continue

                    await session.commit()
                    disable = await source_client.put(
                        f"/api/user/{username}",
                        headers=source_headers,
                        json={"status": "disabled"},
                    )
                    if disable.is_error:
                        summary["source_disable_failed"] += 1
                    summary[f"migrated_{action}"] += 1

        if args.apply and sum(value for key, value in summary.items() if "failed" in key or "http" in key or key.startswith("missing_")) == 0:
            plans = (
                await session.execute(
                    select(ShopPlan).where(
                        ShopPlan.category_key == args.category,
                        ShopPlan.provision_panel_key == args.source_key,
                    )
                )
            ).scalars().all()
            for plan in plans:
                plan.provision_panel_key = args.target_key
                plan.updated_at = datetime.now(timezone.utc)
            await session.commit()
            summary["plans_switched"] = len(plans)

    print(f"mode={'apply' if args.apply else 'dry-run'}")
    print(f"summary={dict(summary)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
