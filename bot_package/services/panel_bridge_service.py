from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import delete, select

from ..database import async_session
from ..models import (
    BotSetting,
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


logger = logging.getLogger(__name__)


PHANTOM_TUNNEL_HAJMI_SCOPE_MIGRATION = "_migration_phantom_tunnel_hajmi_scope_v1"


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


def _epoch_seconds(value: Any) -> int:
    if value in {None, "", 0, "0"}:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise BridgeSkip("تاریخ سرویس مبدا قابل تشخیص نیست.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


def _target_timing(source: dict[str, Any]) -> dict[str, Any]:
    status = str(source.get("status") or "").strip().lower()
    if status not in {"active", "on_hold", "disabled", "limited", "expired"}:
        raise BridgeSkip(f"وضعیت سرویس مبدا {status or 'نامشخص'} است.")
    expire = _epoch_seconds(source.get("expire"))
    if status == "on_hold":
        duration = int(source.get("on_hold_expire_duration") or 0)
        if duration <= 0:
            raise BridgeSkip("مدت on hold سرویس مبدا معتبر نیست.")
        return {"status": "on_hold", "expire": 0, "on_hold_expire_duration": duration}
    if status != "active" or (expire and expire <= int(datetime.now(timezone.utc).timestamp())):
        status = "disabled"
    return {"status": status, "expire": expire, "on_hold_expire_duration": None}


def _remaining_data_limit(source: dict[str, Any]) -> int:
    total = int(source.get("data_limit") or 0)
    if total <= 0:
        return 0
    remaining = total - int(source.get("used_traffic") or 0)
    return max(0, remaining)


def _bridge_fallback_username(username: str, rule_id: int, config_id: int) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", username).strip("_") or "user"
    suffix = f"_b{rule_id}_{config_id}"
    return f"{cleaned[: max(1, 32 - len(suffix))]}{suffix}"


def _external_source_payload(item: dict[str, Any]) -> dict[str, Any] | None:
    if not item.get("cache_available"):
        return None
    status = str(item.get("upstream_status") or "active").strip().lower()
    if status not in {"active", "on_hold", "expired", "disabled", "limited"}:
        status = "active"
    return {
        "status": status,
        "data_limit": max(0, int(item.get("upstream_total_bytes") or 0)),
        "used_traffic": max(0, int(item.get("upstream_used_bytes") or 0)),
        "expire": max(0, int(item.get("upstream_expire") or 0)),
        "on_hold_expire_duration": None,
    }


def _metadata_source_payload(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": str(metadata.get("status") or "active").strip().lower(),
        "data_limit": max(0, int(metadata.get("total") or 0)),
        "used_traffic": max(0, int(metadata.get("used") or 0)),
        "expire": max(0, int(metadata.get("expire") or 0)),
        "on_hold_expire_duration": None,
    }


def _external_panel_fragment(source_payload: dict[str, Any]) -> str:
    return "namahdod" if int(source_payload.get("data_limit") or 0) <= 0 else "hajmi"


def _external_username(item: dict[str, Any], upstream_url: str) -> str:
    return str(
        item.get("upstream_panel_username")
        or item.get("panel_username")
        or item.get("service_name")
        or str(item.get("upstream_title") or "").lstrip("@")
        or username_from_subscription_url(upstream_url)
        or ""
    ).strip()


def _automatic_reconcile_candidate(config: Config) -> bool:
    return bool(config.is_sold and config.panel_deleted_at is None)


class PanelBridgeService:
    @staticmethod
    async def migrate_phantom_tunnel_hajmi_scope(session) -> None:
        migration = (
            await session.execute(
                select(BotSetting).where(BotSetting.key == PHANTOM_TUNNEL_HAJMI_SCOPE_MIGRATION)
            )
        ).scalar_one_or_none()
        if migration is not None:
            return

        rules = (
            await session.execute(
                select(PanelBridgeRule).where(PanelBridgeRule.target_panel_key == "phantom_tunnel")
            )
        ).scalars().all()
        now = datetime.now(timezone.utc)
        for rule in rules:
            rule.source_panel_keys_json = json.dumps(["mexico_hajmi"])
            rule.updated_at = now
        session.add(BotSetting(key=PHANTOM_TUNNEL_HAJMI_SCOPE_MIGRATION, value="done"))
        await session.commit()

    @staticmethod
    async def _resolve_external_panel(
        candidates: list[ProvisionPanel],
        *,
        requested_key: str,
        username: str,
        cached_payload: dict[str, Any] | None,
        existing_panel_key: str,
    ) -> tuple[ProvisionPanel | None, dict[str, Any] | None]:
        if requested_key:
            return candidates[0], cached_payload

        unavailable_panels: list[ProvisionPanel] = []
        for panel in candidates:
            try:
                live_payload = await PanelBridgeService._fetch_panel_user(panel, username)
                return panel, live_payload
            except BridgeSkip:
                # A 404 is authoritative: this account does not own the user.
                continue
            except Exception:
                unavailable_panels.append(panel)

        if cached_payload is None or not unavailable_panels:
            return None, None

        # Same-host provider accounts cannot be distinguished from a cached
        # subscription URL alone. Preserve an earlier live classification when
        # possible; only then use the volume-based legacy fallback.
        existing = next(
            (panel for panel in candidates if panel.key == existing_panel_key),
            None,
        )
        if existing is not None:
            return existing, cached_payload
        preferred_fragment = _external_panel_fragment(cached_payload)
        fallback = next(
            (panel for panel in candidates if preferred_fragment in panel.key),
            None,
        )
        return fallback, cached_payload if fallback is not None else None

    @staticmethod
    async def import_external_configs(rule_id: int) -> list[int]:
        external_rows = await SubscriptionLinkService.list_panel_configs()
        if not external_rows:
            return []

        async with async_session() as session:
            rule = await session.get(PanelBridgeRule, rule_id)
            if not rule or not rule.is_enabled:
                return []
            source_keys = [str(value) for value in _json_list(rule.source_panel_keys_json)]
            if not source_keys:
                return []
            panels = [
                panel
                for key in source_keys
                if (panel := await ProvisioningService.get_panel(session, key)) is not None
            ]
            if not panels:
                return []

            existing_configs = (await session.execute(select(Config))).scalars().all()
            configs_by_token = {
                str(config.public_sub_token): config
                for config in existing_configs
                if config.public_sub_token
            }
            configs_by_link = {
                str(config.sub_link): config for config in existing_configs if config.sub_link
            }
            imported_ids: list[int] = []

            for item in external_rows:
                token = str(item.get("token") or "").strip()
                upstream_url = str(item.get("upstream_url") or "").strip()
                if not token or not upstream_url:
                    continue
                existing = configs_by_token.get(token) or configs_by_link.get(upstream_url)
                if existing is not None and existing.provision_source != "external_subscription":
                    continue

                requested_key = str(item.get("source_panel_key") or "").strip()
                upstream_host = (urlparse(upstream_url).hostname or "").lower()
                candidates = [panel for panel in panels if panel.key == requested_key]
                if not candidates:
                    candidates = [
                        panel
                        for panel in panels
                        if (urlparse(panel.base_url).hostname or "").lower() == upstream_host
                    ]
                if not candidates:
                    continue

                username = _external_username(item, upstream_url)
                if not username:
                    continue

                source_payload = _external_source_payload(item)
                if source_payload is not None:
                    if source_payload["status"] not in {"active", "on_hold"} and existing is None:
                        continue
                resolved_panel, source_payload = await PanelBridgeService._resolve_external_panel(
                    candidates,
                    requested_key=requested_key,
                    username=username,
                    cached_payload=source_payload,
                    existing_panel_key=str(existing.panel_key or "") if existing else "",
                )
                if resolved_panel is None or source_payload is None:
                    continue

                source_limit = int(source_payload.get("data_limit") or 0)
                external_volume = int(item.get("volume_gb") or 0)
                volume_gb = external_volume or (source_limit // (1024**3) if source_limit > 0 else 0)
                telegram_user_id = int(item.get("telegram_user_id") or 0)
                previous_identity = (
                    existing.sub_link,
                    existing.panel_key,
                    existing.panel_username,
                ) if existing is not None else None
                config = existing or Config(
                    volume_gb=max(0, volume_gb),
                    category_key=str(item.get("category_key") or "manual"),
                    sub_link=upstream_url,
                    public_sub_token=token,
                    provision_source="external_subscription",
                    is_sold=True,
                    sold_at=datetime.now(timezone.utc),
                )
                if existing is None:
                    session.add(config)
                config.volume_gb = max(0, volume_gb)
                config.category_key = str(item.get("category_key") or "manual")
                config.sub_link = upstream_url
                config.public_sub_token = token
                config.panel_key = resolved_panel.key
                config.panel_username = username
                config.is_sold = True
                config.sold_to_user_id = telegram_user_id or config.sold_to_user_id
                await session.flush()
                current_identity = (config.sub_link, config.panel_key, config.panel_username)
                if existing is None or previous_identity != current_identity:
                    imported_ids.append(config.id)
                configs_by_token[token] = config
                configs_by_link[upstream_url] = config

            await session.commit()
            return imported_ids

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
        reset_traffic: bool = False,
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
        if int(source.get("data_limit") or 0) > 0 and body["data_limit"] <= 0:
            body["status"] = "disabled"
        async with ProvisioningService._api_client(target) as (client, token):
            headers = {"Authorization": f"Bearer {token}"}
            existing = await client.get(f"/api/user/{username}", headers=headers)
            if existing.status_code == 404:
                create_body = dict(body)
                needs_post_create_disable = body["status"] not in {"active", "on_hold"}
                if needs_post_create_disable:
                    create_body["status"] = "active"
                    create_body["expire"] = 0
                    if int(source.get("data_limit") or 0) > 0 and body["data_limit"] <= 0:
                        create_body["data_limit"] = 1
                response = await client.post("/api/user", headers=headers, json=create_body)
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
            if existing.status_code == 404 and needs_post_create_disable:
                response = await client.put(f"/api/user/{username}", headers=headers, json=body)
                if response.is_error:
                    raise _panel_error(response, "غیرفعال‌سازی سرویس کمکی پایان‌یافته")
                payload = response.json()
            if may_update and reset_traffic:
                reset = await client.post(f"/api/user/{username}/reset", headers=headers)
                if reset.status_code not in {200, 204, 404, 405}:
                    raise _panel_error(reset, "ریست حجم سرویس کمکی پس از تمدید")
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
        if config.provision_source != "external_subscription":
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
    async def reconcile_config(
        rule_id: int,
        config_id: int,
        *,
        reset_target_traffic: bool = False,
    ) -> str:
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
            fallback_username = _bridge_fallback_username(username, rule.id, config.id)
            expected_target_names = {username, fallback_username}
            if assignment and assignment.target_username not in expected_target_names:
                if assignment.target_created:
                    async with ProvisioningService._api_client(target) as (client, token):
                        response = await client.delete(
                            f"/api/user/{assignment.target_username}",
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        if response.status_code not in {200, 204, 404}:
                            raise _panel_error(response, "حذف یوزرنیم قبلی سرویس کمکی")
                assignment.target_created = False
            source_payload = None
            if config.provision_source == "external_subscription" and config.public_sub_token:
                metadata = await SubscriptionLinkService.fetch_metadata(config.public_sub_token)
                if metadata:
                    source_payload = _metadata_source_payload(metadata)
            if source_payload is None:
                try:
                    source_payload = await PanelBridgeService._fetch_panel_user(source, username)
                except Exception:
                    if not config.public_sub_token:
                        raise
                    metadata = await SubscriptionLinkService.fetch_metadata(
                        config.public_sub_token
                    )
                    if not metadata:
                        raise
                    source_payload = _metadata_source_payload(metadata)
            target_username = assignment.target_username if assignment else username
            used_fallback = target_username == fallback_username
            try:
                target_sub_link, created = await PanelBridgeService._upsert_target_user(
                    target,
                    target_username,
                    source_payload,
                    _json_dict(rule.target_inbounds_json),
                    may_update=assignment is not None,
                    reset_traffic=reset_target_traffic,
                )
            except ProvisioningError as exc:
                collision = (
                    "HTTP 403" in str(exc)
                    or "HTTP 422" in str(exc)
                    or "متعلق به این قانون نیست" in str(exc)
                )
                if not collision or target_username == fallback_username:
                    raise
                target_username = fallback_username
                used_fallback = True
                target_sub_link, created = await PanelBridgeService._upsert_target_user(
                    target,
                    target_username,
                    source_payload,
                    _json_dict(rule.target_inbounds_json),
                    may_update=True,
                    reset_traffic=reset_target_traffic,
                )
            if assignment is None:
                assignment = PanelBridgeAssignment(
                    rule_id=rule.id,
                    config_id=config.id,
                    target_panel_key=target.key,
                    target_username=target_username,
                    target_sub_link=target_sub_link,
                    target_created=created,
                )
                session.add(assignment)
            else:
                assignment.target_created = assignment.target_created or created
            if used_fallback:
                assignment.target_created = True
            assignment.target_username = target_username
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

        await PanelBridgeService.import_external_configs(rule_id)
        async with async_session() as session:
            rule = await session.get(PanelBridgeRule, rule_id)
            if not rule:
                return
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
    async def discover_external_configs() -> dict[str, int]:
        async with async_session() as session:
            rule_ids = list(
                (
                    await session.execute(
                        select(PanelBridgeRule.id).where(PanelBridgeRule.is_enabled.is_(True))
                    )
                ).scalars().all()
            )
        stats = {"imported": 0, "synced": 0, "failed": 0}
        for rule_id in rule_ids:
            imported_ids = await PanelBridgeService.import_external_configs(rule_id)
            stats["imported"] += len(imported_ids)
            async with async_session() as session:
                rule = await session.get(PanelBridgeRule, rule_id)
                if not rule:
                    continue
                # Immediate reconciliation can fail transiently after a purchase
                # or an inventory assignment. Retry every unassigned sold config,
                # regardless of how it entered the system.
                candidate_configs = (
                    await session.execute(
                        select(Config).where(
                            Config.is_sold.is_(True),
                            Config.panel_deleted_at.is_(None),
                        )
                    )
                ).scalars().all()
                assigned_ids = set(
                    (
                        await session.execute(
                            select(PanelBridgeAssignment.config_id).where(
                                PanelBridgeAssignment.rule_id == rule_id
                            )
                        )
                    ).scalars().all()
                )
                pending_ids = [
                    config.id
                    for config in candidate_configs
                    if (
                        _automatic_reconcile_candidate(config)
                        and config.id not in assigned_ids
                        and _rule_matches(rule, config)
                    )
                ]
            reconcile_ids = sorted(set(imported_ids + pending_ids))
            failures: list[str] = []
            for config_id in reconcile_ids:
                try:
                    await PanelBridgeService.reconcile_config(rule_id, config_id)
                    stats["synced"] += 1
                except Exception as exc:
                    stats["failed"] += 1
                    failures.append(f"config={config_id}: {str(exc)[:900]}")
                    logger.warning(
                        "Automatic panel bridge reconciliation failed for rule=%s config=%s: %s",
                        rule_id,
                        config_id,
                        exc,
                    )
            if reconcile_ids:
                async with async_session() as session:
                    rule = await session.get(PanelBridgeRule, rule_id)
                    if rule:
                        rule.last_synced_at = datetime.now(timezone.utc)
                        rule.updated_at = datetime.now(timezone.utc)
                        if failures:
                            rule.sync_status = "completed_with_errors"
                            rule.failed_count = len(failures)
                            rule.last_error = failures[-1]
                        elif rule.sync_status != "running":
                            rule.sync_status = "completed"
                            rule.failed_count = 0
                            rule.last_error = None
                        await session.commit()
        return stats

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
    async def reconcile_matching_config(
        config_id: int,
        *,
        reset_target_traffic: bool = False,
    ) -> None:
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
                await PanelBridgeService.reconcile_config(
                    rule_id,
                    config_id,
                    reset_target_traffic=reset_target_traffic,
                )
            except Exception as exc:
                logger.warning(
                    "Immediate panel bridge reconciliation failed for rule=%s config=%s: %s",
                    rule_id,
                    config_id,
                    exc,
                )

    @staticmethod
    async def set_config_assignments_enabled(config_id: int, enabled: bool) -> None:
        async with async_session() as session:
            assignments = (
                await session.execute(
                    select(PanelBridgeAssignment).where(
                        PanelBridgeAssignment.config_id == config_id,
                        PanelBridgeAssignment.status == "active",
                    )
                )
            ).scalars().all()
            errors: list[str] = []
            for assignment in assignments:
                target = await ProvisioningService.get_panel(session, assignment.target_panel_key)
                if target is None:
                    errors.append(f"پنل مقصد {assignment.target_panel_key} در دسترس نیست.")
                    continue
                try:
                    async with ProvisioningService._api_client(target) as (client, token):
                        response = await client.put(
                            f"/api/user/{assignment.target_username}",
                            headers={"Authorization": f"Bearer {token}"},
                            json={"status": "active" if enabled else "disabled"},
                        )
                        if response.is_error:
                            raise _panel_error(response, "تغییر وضعیت سرویس معادل")
                except Exception as exc:
                    errors.append(str(exc))
            if errors:
                raise ProvisioningError(errors[-1])

    @staticmethod
    async def remove_config_assignments(config_id: int) -> None:
        async with async_session() as session:
            config = await session.get(Config, config_id)
            if config is None:
                return
            await PanelBridgeService.remove_config_assignments_in_session(session, config)
            await session.commit()

    @staticmethod
    async def remove_config_assignments_in_session(session, config: Config) -> None:
        assignments = (
            await session.execute(
                select(PanelBridgeAssignment).where(
                    PanelBridgeAssignment.config_id == config.id
                )
            )
        ).scalars().all()
        for assignment in assignments:
            target = await ProvisioningService.get_panel(session, assignment.target_panel_key)
            if assignment.target_created and target is not None:
                async with ProvisioningService._api_client(target) as (client, token):
                    response = await client.delete(
                        f"/api/user/{assignment.target_username}",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if response.status_code not in {200, 204, 404}:
                        raise _panel_error(response, "حذف سرویس معادل")
            await session.delete(assignment)
        await session.flush()
        if assignments and config.public_sub_token:
            await PanelBridgeService._sync_config_links(session, config)

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
