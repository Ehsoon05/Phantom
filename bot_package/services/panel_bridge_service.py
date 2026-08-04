from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select

from ..database import async_session
from ..models import (
    Config,
    PanelBridgeAssignment,
    PanelBridgeRule,
    ProvisionPanel,
    Purchase,
)
from .provisioning_service import (
    ProvisioningError,
    ProvisioningService,
    _panel_error,
    _subscription_url,
    username_from_subscription_url,
)
from .subscription_link_service import SubscriptionLinkService


class BridgeSkip(RuntimeError):
    pass


def _json_list(value: str | None) -> list:
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _json_dict(value: str | None) -> dict:
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _rule_matches(rule: PanelBridgeRule, config: Config) -> bool:
    panels = {str(value) for value in _json_list(rule.source_panel_keys_json)}
    categories = {str(value) for value in _json_list(rule.source_category_keys_json)}
    plan_ids = {int(value) for value in _json_list(rule.source_plan_ids_json) if str(value).isdigit()}
    return (
        (not panels or str(config.panel_key or "") in panels)
        and (not categories or str(config.category_key or "") in categories)
        and (not plan_ids or int(config.shop_plan_id or 0) in plan_ids)
    )


def _target_timing(source: dict[str, Any]) -> dict[str, Any]:
    status = str(source.get("status") or "").strip().lower()
    if status not in {"active", "on_hold"}:
        raise BridgeSkip(f"وضعیت سرویس مبدا {status or 'نامشخص'} است.")
    expire = int(source.get("expire") or 0)
    if status == "active" and expire and expire <= int(datetime.now(timezone.utc).timestamp()):
        raise BridgeSkip("تاریخ سرویس مبدا تمام شده است.")
    if status == "on_hold":
        duration = int(source.get("on_hold_expire_duration") or 0)
        if duration <= 0:
            raise BridgeSkip("مدت on hold سرویس مبدا معتبر نیست.")
        return {"status": "on_hold", "expire": 0, "on_hold_expire_duration": duration}
    return {"status": "active", "expire": expire, "on_hold_expire_duration": None}


def _remaining_data_limit(source: dict[str, Any]) -> int:
    total = int(source.get("data_limit") or 0)
    if total <= 0:
        return 0
    remaining = total - int(source.get("used_traffic") or 0)
    if remaining <= 0:
        raise BridgeSkip("حجم سرویس مبدا تمام شده است.")
    return remaining


class PanelBridgeService:
    @staticmethod
    async def _refresh_target_ports(session, rule: PanelBridgeRule) -> None:
        target = await ProvisioningService.get_panel(session, rule.target_panel_key)
        if target is None:
            raise ProvisioningError("پنل مقصد فعال و معتبر نیست.")
        selected = _json_dict(rule.target_inbounds_json)
        options = await ProvisioningService.fetch_inbound_options(target)
        available = {
            (str(item.get("protocol") or ""), str(item.get("tag") or "")): int(item.get("port") or 0)
            for item in options
        }
        ports: set[int] = set()
        for protocol, tags in selected.items():
            for tag in tags:
                key = (str(protocol), str(tag))
                if key not in available:
                    raise ProvisioningError(
                        f"اینباند انتخاب‌شده {protocol} / {tag} دیگر در پنل مقصد وجود ندارد."
                    )
                if available[key] > 0:
                    ports.add(available[key])
        if not ports:
            raise ProvisioningError("اینباند انتخاب‌شده پورت قابل استفاده ندارد.")
        rule.target_ports_json = json.dumps(sorted(ports))
        await session.flush()

    @staticmethod
    async def matching_config_ids(rule: PanelBridgeRule) -> list[int]:
        async with async_session() as session:
            rows = (
                await session.execute(
                    select(Config).where(
                        Config.is_sold.is_(True),
                        Config.panel_deleted_at.is_(None),
                    )
                )
            ).scalars().all()
            return [row.id for row in rows if _rule_matches(rule, row)]

    @staticmethod
    async def _fetch_panel_user(panel: ProvisionPanel, username: str) -> dict[str, Any]:
        async with ProvisioningService._api_client(panel) as (client, token):
            response = await client.get(
                f"/api/user/{username}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code == 404:
                raise BridgeSkip("یوزر در پنل مبدا پیدا نشد.")
            if response.is_error:
                raise _panel_error(response, "دریافت سرویس مبدا")
            payload = response.json()
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    async def _upsert_target_user(
        target: ProvisionPanel,
        username: str,
        source: dict[str, Any],
        inbounds: dict[str, list[str]],
        *,
        may_update: bool,
    ) -> tuple[str, bool]:
        access = {
            "proxies": {protocol: {} for protocol in inbounds},
            "inbounds": inbounds,
        }
        body = {
            "username": username,
            "data_limit": _remaining_data_limit(source),
            "data_limit_reset_strategy": "no_reset",
            **_target_timing(source),
            **access,
        }
        async with ProvisioningService._api_client(target) as (client, token):
            headers = {"Authorization": f"Bearer {token}"}
            existing = await client.get(f"/api/user/{username}", headers=headers)
            if existing.status_code == 404:
                response = await client.post("/api/user", headers=headers, json=body)
                created = True
            elif existing.is_error:
                raise _panel_error(existing, "بررسی یوزر پنل مقصد")
            elif may_update:
                response = await client.put(f"/api/user/{username}", headers=headers, json=body)
                created = False
            else:
                raise ProvisioningError(
                    f"یوزر {username} از قبل در پنل مقصد وجود دارد و متعلق به این قانون نیست."
                )
            if response.is_error:
                raise _panel_error(response, "ساخت سرویس کمکی در پنل مقصد")
            payload = response.json()
        return _subscription_url(target.base_url, payload), created

    @staticmethod
    async def _sync_config_links(session, config: Config) -> None:
        token = await SubscriptionLinkService.ensure_public_token(session, config)
        service_name = (
            await session.execute(
                select(Purchase.service_name)
                .where(Purchase.config_id == config.id)
                .order_by(Purchase.purchased_at.desc())
            )
        ).scalars().first()
        await session.flush()
        primary_ok = await SubscriptionLinkService.sync_to_panel(config, service_name)
        if not primary_ok:
            raise ProvisioningError("همگام‌سازی لینک اصلی با پنل ساب انجام نشد.")

        rows = (
            await session.execute(
                select(PanelBridgeAssignment, PanelBridgeRule)
                .join(PanelBridgeRule, PanelBridgeRule.id == PanelBridgeAssignment.rule_id)
                .where(
                    PanelBridgeAssignment.config_id == config.id,
                    PanelBridgeAssignment.status == "active",
                    PanelBridgeRule.is_enabled.is_(True),
                )
            )
        ).all()
        supplements = [
            {
                "source_key": f"bridge:{rule.id}",
                "label": rule.name,
                "upstream_url": assignment.target_sub_link,
                "allowed_ports": [int(value) for value in _json_list(rule.target_ports_json)],
            }
            for assignment, rule in rows
        ]
        if not await SubscriptionLinkService.sync_supplements(token, supplements):
            raise ProvisioningError("افزودن منبع کمکی به پنل ساب انجام نشد.")

    @staticmethod
    async def reconcile_config(rule_id: int, config_id: int) -> str:
        async with async_session() as session:
            rule = await session.get(PanelBridgeRule, rule_id)
            config = await session.get(Config, config_id)
            if not rule or not config or not rule.is_enabled or not _rule_matches(rule, config):
                raise BridgeSkip("سرویس دیگر با قانون تطابق ندارد.")
            source = await ProvisioningService.get_panel(session, config.panel_key)
            target = await ProvisioningService.get_panel(session, rule.target_panel_key)
            if source is None or target is None:
                raise ProvisioningError("پنل مبدا یا مقصد فعال و معتبر نیست.")
            username = config.panel_username or username_from_subscription_url(config.sub_link)
            if not username:
                raise ProvisioningError("نام کاربری سرویس مبدا قابل تشخیص نیست.")
            assignment = (
                await session.execute(
                    select(PanelBridgeAssignment).where(
                        PanelBridgeAssignment.rule_id == rule.id,
                        PanelBridgeAssignment.config_id == config.id,
                    )
                )
            ).scalar_one_or_none()
            source_payload = await PanelBridgeService._fetch_panel_user(source, username)
            target_sub_link, created = await PanelBridgeService._upsert_target_user(
                target,
                username,
                source_payload,
                _json_dict(rule.target_inbounds_json),
                may_update=assignment is not None,
            )
            if assignment is None:
                assignment = PanelBridgeAssignment(
                    rule_id=rule.id,
                    config_id=config.id,
                    target_panel_key=target.key,
                    target_username=username,
                    target_sub_link=target_sub_link,
                    target_created=created,
                )
                session.add(assignment)
            assignment.target_sub_link = target_sub_link
            assignment.target_panel_key = target.key
            assignment.status = "active"
            assignment.last_error = None
            assignment.updated_at = datetime.now(timezone.utc)
            await session.flush()
            await PanelBridgeService._sync_config_links(session, config)
            await session.commit()
        return "synced"

    @staticmethod
    async def run_rule(rule_id: int) -> None:
        async with async_session() as session:
            rule = await session.get(PanelBridgeRule, rule_id)
            if not rule:
                return
            rule.sync_status = "running"
            rule.synced_count = 0
            rule.skipped_count = 0
            rule.failed_count = 0
            rule.last_error = None
            rule.updated_at = datetime.now(timezone.utc)
            try:
                await PanelBridgeService._refresh_target_ports(session, rule)
            except Exception as exc:
                rule.sync_status = "completed_with_errors"
                rule.failed_count = 1
                rule.last_error = str(exc)[:1000]
                rule.last_synced_at = datetime.now(timezone.utc)
                await session.commit()
                return
            await session.commit()
            config_ids = await PanelBridgeService.matching_config_ids(rule)
            rule.total_matches = len(config_ids)
            await session.commit()

        async with async_session() as session:
            stale_ids = list(
                (
                    await session.execute(
                        select(PanelBridgeAssignment.config_id).where(
                            PanelBridgeAssignment.rule_id == rule_id,
                            PanelBridgeAssignment.config_id.not_in(config_ids or [-1]),
                        )
                    )
                ).scalars().all()
            )
        for config_id in stale_ids:
            await PanelBridgeService.remove_assignment(rule_id, config_id)

        semaphore = asyncio.Semaphore(4)

        async def reconcile(config_id: int) -> tuple[str, str | None]:
            async with semaphore:
                try:
                    return await PanelBridgeService.reconcile_config(rule_id, config_id), None
                except BridgeSkip as exc:
                    return "skipped", str(exc)
                except Exception as exc:
                    return "failed", str(exc)[:1000]

        results = await asyncio.gather(*(reconcile(config_id) for config_id in config_ids))
        synced = sum(status == "synced" for status, _ in results)
        skipped = sum(status == "skipped" for status, _ in results)
        failures = [error for status, error in results if status == "failed" and error]
        async with async_session() as session:
            rule = await session.get(PanelBridgeRule, rule_id)
            if not rule:
                return
            rule.synced_count = synced
            rule.skipped_count = skipped
            rule.failed_count = len(failures)
            rule.last_error = failures[-1] if failures else None
            rule.sync_status = "completed" if not failures else "completed_with_errors"
            rule.last_synced_at = datetime.now(timezone.utc)
            rule.updated_at = datetime.now(timezone.utc)
            await session.commit()

    @staticmethod
    async def remove_assignment(rule_id: int, config_id: int) -> None:
        async with async_session() as session:
            assignment = (
                await session.execute(
                    select(PanelBridgeAssignment).where(
                        PanelBridgeAssignment.rule_id == rule_id,
                        PanelBridgeAssignment.config_id == config_id,
                    )
                )
            ).scalar_one_or_none()
            config = await session.get(Config, config_id)
            if assignment is None:
                return
            target = await ProvisioningService.get_panel(session, assignment.target_panel_key)
            if assignment.target_created and target is not None:
                async with ProvisioningService._api_client(target) as (client, token):
                    response = await client.delete(
                        f"/api/user/{assignment.target_username}",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if response.status_code not in {200, 204, 404}:
                        raise _panel_error(response, "حذف سرویس کمکی")
            await session.delete(assignment)
            await session.flush()
            if config and config.public_sub_token:
                await PanelBridgeService._sync_config_links(session, config)
            await session.commit()

    @staticmethod
    async def reconcile_matching_config(config_id: int) -> None:
        async with async_session() as session:
            config = await session.get(Config, config_id)
            if config is None:
                return
            rules = (
                await session.execute(
                    select(PanelBridgeRule).where(PanelBridgeRule.is_enabled.is_(True))
                )
            ).scalars().all()
            rule_ids = [rule.id for rule in rules if _rule_matches(rule, config)]
        for rule_id in rule_ids:
            try:
                await PanelBridgeService.reconcile_config(rule_id, config_id)
            except Exception:
                continue

    @staticmethod
    async def remove_rule(rule_id: int) -> None:
        async with async_session() as session:
            rule = await session.get(PanelBridgeRule, rule_id)
            if not rule:
                return
            rule.is_enabled = False
            rule.sync_status = "cleaning"
            assignments = (
                await session.execute(
                    select(PanelBridgeAssignment).where(PanelBridgeAssignment.rule_id == rule.id)
                )
            ).scalars().all()
            config_ids = [assignment.config_id for assignment in assignments]
            await session.commit()

        failed_assignment_ids: list[int] = []
        for assignment in assignments:
            async with async_session() as session:
                target = await ProvisioningService.get_panel(session, assignment.target_panel_key)
            if rule.cleanup_on_delete and assignment.target_created and target is not None:
                try:
                    async with ProvisioningService._api_client(target) as (client, token):
                        response = await client.delete(
                            f"/api/user/{assignment.target_username}",
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        if response.status_code not in {200, 204, 404}:
                            raise _panel_error(response, "حذف سرویس کمکی")
                except Exception as exc:
                    failed_assignment_ids.append(assignment.id)
                    async with async_session() as session:
                        row = await session.get(PanelBridgeAssignment, assignment.id)
                        if row:
                            row.status = "cleanup_failed"
                            row.last_error = str(exc)[:1000]
                            row.updated_at = datetime.now(timezone.utc)
                            await session.commit()

        async with async_session() as session:
            await session.execute(
                delete(PanelBridgeAssignment).where(
                    PanelBridgeAssignment.rule_id == rule_id,
                    PanelBridgeAssignment.id.not_in(failed_assignment_ids or [-1]),
                )
            )
            await session.commit()
            for config_id in config_ids:
                config = await session.get(Config, config_id)
                if config and config.public_sub_token:
                    await PanelBridgeService._sync_config_links(session, config)
            rule = await session.get(PanelBridgeRule, rule_id)
            if rule:
                if failed_assignment_ids:
                    rule.sync_status = "cleanup_failed"
                    rule.failed_count = len(failed_assignment_ids)
                    rule.last_error = "پاک‌سازی بعضی یوزرهای پنل مقصد انجام نشد؛ حذف را دوباره اجرا کنید."
                else:
                    await session.delete(rule)
            await session.commit()
