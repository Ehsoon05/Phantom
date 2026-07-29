#!/usr/bin/env python3
"""Restore MMD-migrated subscriptions to SVN from a protected manifest."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import httpx
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot_package.config_loader import BotConfig
from bot_package.database import async_session, engine
from bot_package.models import Config, Purchase, ShopPlan
from bot_package.services.provisioning_service import (
    ProvisioningError,
    ProvisioningService,
)
from bot_package.services.schema_service import SchemaService
from bot_package.services.subscription_link_service import SubscriptionLinkService

from scripts.migrate_manual_svn_to_mmd import (
    _address_rewrites_text,
    _sync_payload,
    _token,
)


CONFIRMATION = "ROLLBACK-MMD-TO-SVN"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        default="/opt/phantom/backups/mmd-migration-rollback-20260729.json",
    )
    parser.add_argument("--source-api-url")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    return parser.parse_args()


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

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        raise ProvisioningError(f"Rollback manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    source_api_url = (
        args.source_api_url
        or manifest.get("source_api_url")
        or "http://127.0.0.1:18443"
    )
    await SchemaService.ensure_schema(engine)
    summary: Counter[str] = Counter()

    async with async_session() as session:
        source_panel = await ProvisioningService.get_panel(
            session,
            manifest.get("source_key", "svn"),
        )
        target_panel = await ProvisioningService.get_panel(
            session,
            manifest.get("target_key", "mmd"),
        )
        if source_panel is None or target_panel is None:
            raise ProvisioningError("Source or target panel is missing/disabled.")

        async with httpx.AsyncClient(
            base_url=source_api_url.rstrip("/"),
            verify=False,
            timeout=30,
        ) as source_client:
            source_token = await _token(source_client, source_panel)
            source_headers = {"Authorization": f"Bearer {source_token}"}
            async with ProvisioningService._api_client(target_panel) as (
                target_client,
                target_token,
            ):
                target_headers = {"Authorization": f"Bearer {target_token}"}
                entries = (
                    list(manifest.get("main_entries") or [])
                    + list(manifest.get("manual_entries") or [])
                )
                if not args.apply:
                    print(
                        "mode=dry-run\n"
                        f"summary={{'would_restore': {len(entries)}, "
                        f"'main': {len(manifest.get('main_entries') or [])}, "
                        f"'manual': {len(manifest.get('manual_entries') or [])}}}"
                    )
                    return 0

                async with httpx.AsyncClient(timeout=30) as sync_client:
                    for entry in entries:
                        username = entry["username"]
                        restore = await source_client.put(
                            f"/api/user/{username}",
                            headers=source_headers,
                            json={"status": entry.get("rollback_status", "active")},
                        )
                        if restore.is_error:
                            summary[
                                f"source_restore_{restore.status_code}"
                            ] += 1
                            continue

                        original_row = entry["original_panel_row"]
                        if entry["kind"] == "main":
                            config = await session.get(
                                Config,
                                int(entry["config_id"]),
                            )
                            if config is None:
                                summary["missing_main_config"] += 1
                                continue
                            old = entry["original_config"]
                            config.sub_link = old["sub_link"]
                            config.panel_key = old["panel_key"]
                            config.panel_username = old["panel_username"]
                            config.usage_offset_bytes = max(
                                0,
                                int(old.get("usage_offset_bytes") or 0),
                            )
                            config.display_total_bytes = old.get(
                                "display_total_bytes"
                            )
                            purchase = await _latest_purchase(session, config.id)
                            plan = (
                                await session.get(ShopPlan, config.shop_plan_id)
                                if config.shop_plan_id
                                else None
                            )
                            payload = _sync_payload(
                                original_row,
                                upstream_url=old["sub_link"],
                                panel_username=old["panel_username"],
                                usage_offset_bytes=0,
                                display_total_bytes=0,
                                info_proxies_enabled=bool(
                                    original_row.get(
                                        "info_proxies_enabled",
                                        True,
                                    )
                                ),
                                address_rewrites=_address_rewrites_text(
                                    original_row.get("address_rewrites_json")
                                ),
                            )
                            if purchase and not payload.get("service_name"):
                                payload["service_name"] = purchase.service_name
                            if (
                                plan
                                and payload.get("device_limit") is None
                            ):
                                payload["device_limit"] = (
                                    config.subscription_device_limit
                                    if config.subscription_device_limit
                                    is not None
                                    else plan.subscription_device_limit
                                )
                        else:
                            payload = _sync_payload(
                                original_row,
                                upstream_url=original_row["sub_link"],
                                panel_username=original_row.get(
                                    "panel_username"
                                )
                                or username,
                                usage_offset_bytes=0,
                                display_total_bytes=0,
                                info_proxies_enabled=bool(
                                    original_row.get(
                                        "info_proxies_enabled",
                                        True,
                                    )
                                ),
                                address_rewrites=_address_rewrites_text(
                                    original_row.get("address_rewrites_json")
                                ),
                            )

                        sync = await sync_client.post(
                            BotConfig.SUBSCRIPTION_PANEL_SYNC_URL,
                            json=payload,
                            headers={
                                "Authorization": (
                                    f"Bearer "
                                    f"{BotConfig.SUBSCRIPTION_PANEL_SYNC_TOKEN}"
                                )
                            },
                        )
                        if sync.is_error:
                            summary[
                                f"subscription_sync_{sync.status_code}"
                            ] += 1
                            continue

                        disable_target = await target_client.put(
                            f"/api/user/{username}",
                            headers=target_headers,
                            json={"status": "disabled"},
                        )
                        if disable_target.is_error:
                            summary[
                                f"target_disable_{disable_target.status_code}"
                            ] += 1
                            continue
                        summary[f"restored_{entry['kind']}"] += 1

                backup_path = manifest.get("main_backup_db")
                if backup_path and Path(backup_path).exists():
                    backup = sqlite3.connect(backup_path)
                    plan_rows = backup.execute(
                        """
                        SELECT id, provision_panel_key
                        FROM shop_plans
                        WHERE category_key = 'express'
                        """
                    ).fetchall()
                    backup.close()
                    for plan_id, panel_key in plan_rows:
                        plan = await session.get(ShopPlan, int(plan_id))
                        if plan is not None:
                            plan.provision_panel_key = panel_key
                await session.commit()

    print("mode=apply")
    print(f"summary={dict(summary)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
