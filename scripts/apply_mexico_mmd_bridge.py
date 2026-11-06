#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from bot_package.config_loader import BotConfig
from bot_package.database import async_session
from bot_package.models import Config, PanelBridgeRule
from bot_package.services.panel_bridge_service import BridgeSkip, PanelBridgeService
from bot_package.services.provisioning_service import ProvisioningService


RULE_NAME = "اتصال موقت Mexico از MMD"
TARGET_INBOUND = "VLESS+HTTPUPGRADE+NONE+8080"


async def ensure_rule() -> PanelBridgeRule:
    async with async_session() as session:
        rule = (
            await session.execute(select(PanelBridgeRule).where(PanelBridgeRule.name == RULE_NAME))
        ).scalar_one_or_none()
        target = await ProvisioningService.get_panel(session, "mmd")
        if target is None:
            raise RuntimeError("پنل MMD فعال نیست.")
        options = await ProvisioningService.fetch_inbound_options(target)
        selected = next(
            (
                item
                for item in options
                if item["protocol"] == "vless" and item["tag"] == TARGET_INBOUND
            ),
            None,
        )
        if selected is None or int(selected.get("port") or 0) <= 0:
            raise RuntimeError(f"اینباند {TARGET_INBOUND} در MMD پیدا نشد.")
        if rule is None:
            rule = PanelBridgeRule(name=RULE_NAME)
            session.add(rule)
        rule.source_panel_keys_json = json.dumps(["mexico_hajmi", "mexico_namahdod"])
        rule.source_category_keys_json = "[]"
        rule.source_plan_ids_json = "[]"
        rule.target_panel_key = "mmd"
        rule.target_inbounds_json = json.dumps({"vless": [TARGET_INBOUND]}, ensure_ascii=False)
        rule.target_ports_json = json.dumps([int(selected["port"])])
        rule.cleanup_on_delete = True
        rule.is_enabled = True
        await session.commit()
        await session.refresh(rule)
        return rule


async def sample(rule: PanelBridgeRule) -> None:
    config_ids = await PanelBridgeService.matching_config_ids(rule)
    async with async_session() as session:
        preferred = list(
            (
                await session.execute(
                    select(Config.id).where(
                        Config.id.in_(config_ids or [-1]),
                        Config.shop_plan_id.is_not(None),
                    )
                )
            ).scalars().all()
        )
    ordered = [*preferred, *[value for value in config_ids if value not in set(preferred)]]
    last_error = "نمونه واجد شرایطی پیدا نشد."
    for config_id in ordered[:30]:
        try:
            await PanelBridgeService.reconcile_config(rule.id, config_id)
        except BridgeSkip as exc:
            last_error = str(exc)
            continue
        except Exception as exc:
            last_error = str(exc)
            continue
        async with async_session() as session:
            config = await session.get(Config, config_id)
            print(
                json.dumps(
                    {
                        "rule_id": rule.id,
                        "config_id": config_id,
                        "panel_username": config.panel_username if config else None,
                        "public_url": (
                            f"{BotConfig.SUBSCRIPTION_PUBLIC_BASE_URL}/token/{config.public_sub_token}"
                            if config and config.public_sub_token
                            else None
                        ),
                    },
                    ensure_ascii=False,
                )
            )
        return
    raise RuntimeError(last_error)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Apply the rule to every matching active config")
    args = parser.parse_args()
    rule = await ensure_rule()
    if args.all:
        await PanelBridgeService.run_rule(rule.id)
        async with async_session() as session:
            current = await session.get(PanelBridgeRule, rule.id)
            print(
                json.dumps(
                    {
                        "rule_id": current.id,
                        "status": current.sync_status,
                        "total": current.total_matches,
                        "synced": current.synced_count,
                        "skipped": current.skipped_count,
                        "failed": current.failed_count,
                        "last_error": current.last_error,
                    },
                    ensure_ascii=False,
                )
            )
        return
    await sample(rule)


if __name__ == "__main__":
    asyncio.run(main())
