from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select
from telegram.error import TelegramError
from telegram.ext import Application, ContextTypes

from ..database import async_session
from ..models import Admin, Config, ProvisionPanel, Purchase, ShopPlan
from .provisioning_service import (
    MEXICO_PANEL_KEYS,
    MEXICO_UNLIMITED_DATA_LIMIT_BYTES,
    ProvisioningService,
    _panel_error,
    _subscription_url,
)
from .subscription_link_service import SubscriptionLinkService


logger = logging.getLogger(__name__)
MAINTENANCE_INTERVAL_SECONDS = 1800
ACTIVE_SYNC_STATES = {"active", "limited", "on_hold"}


def _positive_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _desired_device_limit(config: Config, plan: ShopPlan | None, synced: dict | None = None) -> int:
    configured = _positive_int(config.subscription_device_limit)
    if configured > 0:
        return configured
    synced_limit = _positive_int(synced.get("device_limit")) if synced is not None else 0
    if synced_limit > 0:
        return synced_limit
    if plan is not None:
        plan_limit = _positive_int(plan.subscription_device_limit)
        if plan_limit > 0:
            return plan_limit
    return 1


def _user_rows(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("users", "items", "data", "results"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [item for item in rows if isinstance(item, dict)]
    return []


def _remaining_hajmi_bytes(config: Config, metadata: dict) -> tuple[int, int, int]:
    total = _positive_int(metadata.get("total"))
    if total <= 0:
        total = max(0, int(config.volume_gb or 0)) * 1024**3
    used = min(_positive_int(metadata.get("used")), total) if total > 0 else 0
    return total, used, max(total - used, 0)


def _cached_metadata(item: dict | None) -> dict | None:
    if not item or not item.get("cache_available"):
        return None
    return {
        "status": str(item.get("upstream_status") or "active"),
        "total": _positive_int(item.get("upstream_total_bytes")),
        "used": _positive_int(item.get("upstream_used_bytes")),
        "expire": _positive_int(item.get("upstream_expire")),
    }


def _stored_recovery_metadata(config: Config, panel_key: str) -> dict | None:
    if panel_key == "mexico_namahdod":
        return {"status": "active", "total": 0, "used": 0, "expire": 0}
    total = _positive_int(config.display_total_bytes)
    if total <= 0:
        total = max(0, int(config.volume_gb or 0)) * 1024**3
    if total <= 0:
        return None
    used = min(_positive_int(config.usage_offset_bytes), total)
    return {"status": "active", "total": total, "used": used, "expire": 0}


def _subscription_needs_sync(panel_key: str, synced: dict | None, changed: bool) -> bool:
    if changed or not synced:
        return True
    return str(synced.get("source_panel_key") or "") != panel_key


def _synced_username(item: dict) -> str:
    return str(item.get("upstream_panel_username") or item.get("panel_username") or "").strip()


def _synced_device_limit(item: dict) -> int:
    return max(1, _positive_int(item.get("device_limit")))


def _is_synced_namahdod_item(item: dict, namahdod_users: dict[str, dict]) -> bool:
    source_key = str(item.get("source_panel_key") or "").strip()
    if source_key:
        return source_key == "mexico_namahdod"
    username = _synced_username(item)
    if username and username in namahdod_users:
        return True
    status = str(item.get("upstream_status") or "").strip().lower()
    if status not in ACTIVE_SYNC_STATES:
        return False
    identity = " ".join(
        str(item.get(key) or "")
        for key in ("service_name", "panel_username", "upstream_panel_username", "upstream_title")
    ).lower()
    unlimited_marker = any(marker in identity for marker in ("unlimited", "namah", "نامحدود"))
    total = _positive_int(item.get("upstream_total_bytes"))
    return unlimited_marker and total in {0, MEXICO_UNLIMITED_DATA_LIMIT_BYTES}


def _should_reset_unlimited(user_payload: dict) -> bool:
    status = str(user_payload.get("status") or "").strip().lower()
    return (
        _positive_int(user_payload.get("used_traffic")) >= MEXICO_UNLIMITED_DATA_LIMIT_BYTES
        and status not in {"expired", "disabled"}
    )


def _restored_expire(metadata: dict, plan: ShopPlan | None) -> int:
    now = datetime.now(timezone.utc)
    maximum = now + timedelta(days=30) - timedelta(minutes=1)
    expire = _positive_int(metadata.get("expire"))
    if expire > 0:
        return min(expire, int(maximum.timestamp()))
    duration_days = max(1, min(30, int(plan.provision_duration_days or plan.duration_days or 30))) if plan else 30
    return int((now + timedelta(days=duration_days) - timedelta(minutes=1)).timestamp())


def _recovery_username(value: str, config_id: int, *, force_suffix: bool = False) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_@.-]+", "_", str(value or "").strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_.-") or "PhantomHubs"
    suffix = f"_r{config_id}" if force_suffix else ""
    maximum_base = max(3, 32 - len(suffix))
    return f"{cleaned[:maximum_base]}{suffix}"


def _recovery_base_username(value: str) -> str:
    username = str(value or "").strip()
    match = re.match(r"^(?P<base>.+)_r[0-9]+$", username)
    return match.group("base") if match else username


def _dominant_group_ids(users: dict[str, dict]) -> list[int]:
    groups = [
        tuple(_positive_int(value) for value in item.get("group_ids") or [] if _positive_int(value) > 0)
        for item in users.values()
    ]
    groups = [group for group in groups if group]
    if not groups:
        return []
    return list(Counter(groups).most_common(1)[0][0])


class MexicoPanelMaintenanceService:
    @staticmethod
    async def _list_users(panel: ProvisionPanel) -> dict[str, dict]:
        users: dict[str, dict] = {}
        async with ProvisioningService._api_client(panel) as (client, token):
            headers = {"Authorization": f"Bearer {token}"}
            offset = 0
            while True:
                response = await client.get(
                    "/api/users",
                    headers=headers,
                    params={"limit": 500, "offset": offset},
                )
                if response.is_error:
                    raise _panel_error(response, f"دریافت کاربران {panel.title}")
                payload = response.json()
                rows = _user_rows(payload)
                for item in rows:
                    username = str(item.get("username") or "").strip()
                    if username:
                        users[username] = item
                total = _positive_int(payload.get("total")) if isinstance(payload, dict) else 0
                if not rows or (total > 0 and offset + len(rows) >= total):
                    break
                if total <= 0 and len(rows) < 500:
                    break
                offset += len(rows)
        return users

    @staticmethod
    async def _latest_purchase(session, config_id: int) -> Purchase | None:
        return (
            await session.execute(
                select(Purchase)
                .where(Purchase.config_id == config_id, Purchase.kind == "purchase")
                .order_by(Purchase.purchased_at.desc())
            )
        ).scalars().first()

    @staticmethod
    async def _bind_config_to_existing(
        session,
        panel: ProvisionPanel,
        config: Config,
        plan: ShopPlan | None,
        user_payload: dict,
        device_limit: int,
    ) -> None:
        username = str(user_payload.get("username") or "").strip()
        if not username:
            raise ValueError("Existing provider user has no username")
        config.panel_username = username
        config.sub_link = _subscription_url(panel.base_url, user_payload)
        config.subscription_device_limit = device_limit
        config.panel_deleted_at = None
        config.expired_detected_at = None
        config.deletion_due_at = None
        await session.flush()
        purchase = await MexicoPanelMaintenanceService._latest_purchase(session, config.id)
        await SubscriptionLinkService.sync_to_panel(
            config,
            purchase.service_name if purchase else None,
            device_limit=device_limit,
            show_config_preview=plan.show_subscription_configs if plan else None,
            telegram_user_id=config.sold_to_user_id,
        )

    @staticmethod
    async def _restore_missing(
        session,
        panel: ProvisionPanel,
        config: Config,
        plan: ShopPlan | None,
        device_limit: int,
        synced: dict | None,
    ) -> tuple[dict | None, str]:
        if not config.public_sub_token or not config.panel_username:
            return None, "missing_identity"
        metadata = _cached_metadata(synced)
        if not metadata:
            metadata = await SubscriptionLinkService.fetch_metadata(config.public_sub_token)
        if not metadata:
            metadata = _stored_recovery_metadata(config, panel.key)
        if not metadata:
            return None, "missing_metadata"

        original_expire = _positive_int(metadata.get("expire"))
        now = int(datetime.now(timezone.utc).timestamp())
        if original_expire and original_expire <= now:
            return None, "expired"
        expire = _restored_expire(metadata, plan)

        if panel.key == "mexico_hajmi":
            total, used, data_limit = _remaining_hajmi_bytes(config, metadata)
            if total <= 0 or data_limit <= 0:
                return None, "finished"
            config.usage_offset_bytes = used
            config.display_total_bytes = total
        else:
            data_limit = MEXICO_UNLIMITED_DATA_LIMIT_BYTES
            config.usage_offset_bytes = 0
            config.display_total_bytes = 0

        original_username = config.panel_username
        target_username = _recovery_username(original_username, config.id)
        async with ProvisioningService._api_client(panel) as (client, token):
            headers = {"Authorization": f"Bearer {token}"}
            access_fields = await ProvisioningService._access_fields(client, panel, headers)
            if device_limit > 0:
                access_fields["hwid_limit"] = device_limit
            create_payload = {
                    "username": target_username,
                    "status": "active",
                    "expire": expire,
                    "on_hold_expire_duration": None,
                    "data_limit": data_limit,
                    "data_limit_reset_strategy": "no_reset",
                    **access_fields,
                }
            response = await client.post(
                "/api/user",
                headers=headers,
                json=create_payload,
            )
            if response.status_code == 409:
                response = await client.get(
                    f"/api/user/{target_username}",
                    headers=headers,
                )
                if response.status_code == 404:
                    target_username = _recovery_username(original_username, config.id, force_suffix=True)
                    create_payload["username"] = target_username
                    response = await client.post(
                        "/api/user",
                        headers=headers,
                        json=create_payload,
                    )
                    if response.status_code == 409:
                        response = await client.get(
                            f"/api/user/{target_username}",
                            headers=headers,
                        )
            if response.is_error:
                raise _panel_error(response, f"بازیابی {original_username}")
            payload = response.json()

        config.panel_username = str(payload.get("username") or target_username)
        config.sub_link = _subscription_url(panel.base_url, payload)
        config.subscription_device_limit = device_limit
        config.panel_deleted_at = None
        config.expired_detected_at = None
        config.deletion_due_at = None
        await session.flush()
        purchase = await MexicoPanelMaintenanceService._latest_purchase(session, config.id)
        await SubscriptionLinkService.sync_to_panel(
            config,
            purchase.service_name if purchase else None,
            device_limit=device_limit,
            show_config_preview=plan.show_subscription_configs if plan else None,
            telegram_user_id=config.sold_to_user_id,
        )
        return payload if isinstance(payload, dict) else {}, "restored"

    @staticmethod
    async def _restore_external_missing(
        panel: ProvisionPanel,
        item: dict,
        device_limit: int,
    ) -> tuple[dict | None, str]:
        username = _synced_username(item)
        token = str(item.get("token") or "").strip()
        if not username or not token:
            return None, "missing_identity"
        status = str(item.get("upstream_status") or "").strip().lower()
        if status not in ACTIVE_SYNC_STATES:
            return None, "inactive"
        expire = _positive_int(item.get("upstream_expire"))
        now = int(datetime.now(timezone.utc).timestamp())
        if expire and expire <= now:
            return None, "expired"

        stable_id = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16)
        target_username = _recovery_username(username, stable_id)
        async with ProvisioningService._api_client(panel) as (client, api_token):
            headers = {"Authorization": f"Bearer {api_token}"}
            access_fields = await ProvisioningService._access_fields(client, panel, headers)
            access_fields["hwid_limit"] = device_limit
            create_payload = {
                "username": target_username,
                "status": "active",
                "expire": _restored_expire({"expire": expire}, None),
                "on_hold_expire_duration": None,
                "data_limit": MEXICO_UNLIMITED_DATA_LIMIT_BYTES,
                "data_limit_reset_strategy": "no_reset",
                **access_fields,
            }
            response = await client.post("/api/user", headers=headers, json=create_payload)
            if response.status_code == 409:
                response = await client.get(f"/api/user/{target_username}", headers=headers)
                if response.status_code == 404:
                    target_username = _recovery_username(username, stable_id, force_suffix=True)
                    create_payload["username"] = target_username
                    response = await client.post("/api/user", headers=headers, json=create_payload)
                    if response.status_code == 409:
                        response = await client.get(f"/api/user/{target_username}", headers=headers)
            if response.is_error:
                raise _panel_error(response, f"بازیابی لینک دستی {username}")
            payload = response.json()

        panel_username = str(payload.get("username") or target_username)
        upstream_url = _subscription_url(panel.base_url, payload)
        await SubscriptionLinkService.sync_external_to_panel(
            item,
            upstream_url=upstream_url,
            panel_username=panel_username,
            panel_key=panel.key,
            device_limit=device_limit,
            display_total_bytes=0,
        )
        return payload if isinstance(payload, dict) else {}, "restored"

    @staticmethod
    async def _update_external_existing(
        panel: ProvisionPanel,
        item: dict,
        user_payload: dict,
        device_limit: int,
    ) -> tuple[bool, bool]:
        username = str(user_payload.get("username") or _synced_username(item)).strip()
        update: dict[str, Any] = {}
        if _positive_int(user_payload.get("hwid_limit")) != device_limit:
            update["hwid_limit"] = device_limit
        if _positive_int(user_payload.get("data_limit")) != MEXICO_UNLIMITED_DATA_LIMIT_BYTES:
            update["data_limit"] = MEXICO_UNLIMITED_DATA_LIMIT_BYTES
            update["data_limit_reset_strategy"] = "no_reset"
        reset = _should_reset_unlimited(user_payload)

        if update or reset:
            async with ProvisioningService._api_client(panel) as (client, api_token):
                headers = {"Authorization": f"Bearer {api_token}"}
                if update:
                    response = await client.put(f"/api/user/{username}", headers=headers, json=update)
                    if response.is_error:
                        raise _panel_error(response, f"به‌روزرسانی لینک دستی {username}")
                if reset:
                    response = await client.post(f"/api/user/{username}/reset", headers=headers)
                    if response.status_code not in {200, 204}:
                        raise _panel_error(response, f"ریست لینک دستی {username}")

        needs_sync = (
            str(item.get("source_panel_key") or "") != panel.key
            or item.get("display_total_bytes") != 0
            or str(item.get("panel_username") or "").strip() != username
            or _positive_int(item.get("device_limit")) != device_limit
        )
        synced = False
        if needs_sync:
            synced = await SubscriptionLinkService.sync_external_to_panel(
                item,
                upstream_url=str(item.get("upstream_url") or "").strip(),
                panel_username=username,
                panel_key=panel.key,
                device_limit=device_limit,
                display_total_bytes=0,
            )
        return bool(update) or synced, reset

    @staticmethod
    async def _update_existing(
        session,
        panel: ProvisionPanel,
        config: Config,
        plan: ShopPlan | None,
        user_payload: dict,
        device_limit: int,
        synced: dict | None,
    ) -> tuple[bool, bool]:
        purchase = await MexicoPanelMaintenanceService._latest_purchase(session, config.id)
        update: dict[str, Any] = {}
        current_hwid = _positive_int(user_payload.get("hwid_limit"))
        if device_limit > 0 and current_hwid != device_limit:
            update["hwid_limit"] = device_limit

        reset = False
        if panel.key == "mexico_namahdod":
            current_limit = _positive_int(user_payload.get("data_limit"))
            if current_limit != MEXICO_UNLIMITED_DATA_LIMIT_BYTES:
                update["data_limit"] = MEXICO_UNLIMITED_DATA_LIMIT_BYTES
                update["data_limit_reset_strategy"] = "no_reset"
            reset = _should_reset_unlimited(user_payload)

        changed = bool(update)
        if update or reset:
            async with ProvisioningService._api_client(panel) as (client, token):
                headers = {"Authorization": f"Bearer {token}"}
                if update:
                    response = await client.put(
                        f"/api/user/{config.panel_username}",
                        headers=headers,
                        json=update,
                    )
                    if response.is_error:
                        raise _panel_error(response, f"به‌روزرسانی {config.panel_username}")
                if reset:
                    response = await client.post(
                        f"/api/user/{config.panel_username}/reset",
                        headers=headers,
                    )
                    if response.status_code not in {200, 204}:
                        raise _panel_error(response, f"ریست حجم {config.panel_username}")

        if config.subscription_device_limit != device_limit:
            config.subscription_device_limit = device_limit
            changed = True
        if panel.key == "mexico_namahdod" and config.display_total_bytes != 0:
            config.display_total_bytes = 0
            changed = True
        if _subscription_needs_sync(panel.key, synced, changed):
            await SubscriptionLinkService.sync_to_panel(
                config,
                purchase.service_name if purchase else None,
                device_limit=device_limit,
                show_config_preview=plan.show_subscription_configs if plan else None,
                telegram_user_id=config.sold_to_user_id,
            )
        return changed, reset

    @staticmethod
    async def _notify_reset(
        admin_bot,
        *,
        panel_username: str,
        telegram_user_id: int | None = None,
        source: str = "ربات/پنل ساب",
    ) -> None:
        async with async_session() as session:
            admin_ids = list(
                (
                    await session.execute(
                        select(Admin.telegram_id).where(Admin.is_active.is_(True))
                    )
                ).scalars().all()
            )
        text = (
            "ریست خودکار حجم سرویس نامحدود انجام شد.\n\n"
            f"Username پنل: {panel_username or '-'}\n"
            f"آیدی عددی کاربر: {telegram_user_id or '-'}\n"
            f"منبع ثبت: {source}\n"
            "سقف واقعی پنل: 300GB\n"
            "نمایش کاربر: نامحدود"
        )
        for admin_id in admin_ids:
            try:
                await admin_bot.send_message(chat_id=admin_id, text=text)
            except TelegramError as exc:
                logger.warning("Could not notify admin %s about unlimited reset: %s", admin_id, exc)

    @staticmethod
    async def run(admin_bot) -> dict[str, int]:
        stats = {
            "checked": 0,
            "restored": 0,
            "updated": 0,
            "reset": 0,
            "skipped": 0,
            "failed": 0,
            "external_checked": 0,
            "external_restored": 0,
            "external_updated": 0,
            "rebound": 0,
        }
        synced_configs = await SubscriptionLinkService.list_panel_configs()
        synced_by_token = {
            str(item.get("token") or ""): item
            for item in synced_configs
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
                        select(Config).where(
                            or_(
                                Config.is_sold.is_(True),
                                Config.provision_source == "external_subscription",
                            ),
                            Config.panel_key.in_(MEXICO_PANEL_KEYS),
                            Config.panel_deleted_at.is_(None),
                        )
                    )
                ).scalars().all()
            )
            plans = {
                plan.id: plan
                for plan in (
                    await session.execute(
                        select(ShopPlan).where(ShopPlan.id.in_([c.shop_plan_id for c in configs if c.shop_plan_id]))
                    )
                ).scalars().all()
            }

        panel_users: dict[str, dict[str, dict]] = {}
        for panel_key, panel in panels.items():
            try:
                panel_users[panel_key] = await MexicoPanelMaintenanceService._list_users(panel)
                active_groups = _dominant_group_ids(panel_users[panel_key])
                if active_groups:
                    encoded_groups = json.dumps(active_groups)
                    if panel.group_ids != encoded_groups:
                        async with async_session() as session:
                            stored_panel = await session.get(ProvisionPanel, panel.id)
                            if stored_panel is not None:
                                stored_panel.group_ids = encoded_groups
                                await session.commit()
                        panel.group_ids = encoded_groups
            except Exception as exc:  # noqa: BLE001
                logger.warning("Mexico panel user listing failed for %s: %s", panel_key, exc)
                stats["failed"] += 1

        for config in configs:
            stats["checked"] += 1
            panel = panels.get(config.panel_key or "")
            if panel is None or panel.key not in panel_users or not config.panel_username:
                stats["skipped"] += 1
                continue
            try:
                async with async_session() as session:
                    current = await session.get(Config, config.id)
                    if current is None:
                        stats["skipped"] += 1
                        continue
                    plan = plans.get(current.shop_plan_id)
                    synced = synced_by_token.get(current.public_sub_token or "")
                    device_limit = _desired_device_limit(current, plan, synced)
                    user_payload = panel_users.get(panel.key, {}).get(current.panel_username or "")
                    if user_payload is None:
                        base_username = _recovery_base_username(current.panel_username or "")
                        base_payload = panel_users.get(panel.key, {}).get(base_username)
                        if base_payload is not None and base_username != current.panel_username:
                            await MexicoPanelMaintenanceService._bind_config_to_existing(
                                session,
                                panel,
                                current,
                                plan,
                                base_payload,
                                device_limit,
                            )
                            user_payload = base_payload
                            stats["rebound"] += 1
                    if user_payload is None:
                        user_payload, outcome = await MexicoPanelMaintenanceService._restore_missing(
                            session,
                            panel,
                            current,
                            plan,
                            device_limit,
                            synced,
                        )
                        if outcome != "restored":
                            stats["skipped"] += 1
                            continue
                        stats["restored"] += 1
                        panel_users.setdefault(panel.key, {})[current.panel_username or ""] = user_payload or {}
                    else:
                        changed, reset = await MexicoPanelMaintenanceService._update_existing(
                            session,
                            panel,
                            current,
                            plan,
                            user_payload,
                            device_limit,
                            synced,
                        )
                        if changed:
                            stats["updated"] += 1
                        if reset:
                            stats["reset"] += 1
                            await MexicoPanelMaintenanceService._notify_reset(
                                admin_bot,
                                panel_username=current.panel_username or "",
                                telegram_user_id=current.sold_to_user_id,
                            )
                    await session.commit()
            except Exception as exc:  # noqa: BLE001
                stats["failed"] += 1
                logger.warning("Mexico maintenance failed for config=%s: %s", config.id, exc, exc_info=True)
            await asyncio.sleep(0.05)

        known_tokens = {str(config.public_sub_token or "") for config in configs}
        namahdod_panel = panels.get("mexico_namahdod")
        namahdod_users = panel_users.get("mexico_namahdod")
        if namahdod_panel is not None and namahdod_users is not None:
            for item in synced_configs:
                token = str(item.get("token") or "").strip()
                if not token or token in known_tokens:
                    continue
                if not _is_synced_namahdod_item(item, namahdod_users):
                    continue
                stats["external_checked"] += 1
                username = _synced_username(item)
                device_limit = _synced_device_limit(item)
                try:
                    user_payload = namahdod_users.get(username)
                    if user_payload is None:
                        user_payload, outcome = await MexicoPanelMaintenanceService._restore_external_missing(
                            namahdod_panel,
                            item,
                            device_limit,
                        )
                        if outcome != "restored":
                            stats["skipped"] += 1
                            continue
                        username = str(user_payload.get("username") or username)
                        namahdod_users[username] = user_payload or {}
                        stats["external_restored"] += 1
                    else:
                        changed, reset = await MexicoPanelMaintenanceService._update_external_existing(
                            namahdod_panel,
                            item,
                            user_payload,
                            device_limit,
                        )
                        if changed:
                            stats["external_updated"] += 1
                        if reset:
                            stats["reset"] += 1
                            await MexicoPanelMaintenanceService._notify_reset(
                                admin_bot,
                                panel_username=username,
                                telegram_user_id=_positive_int(item.get("telegram_user_id")) or None,
                                source="تبدیل دستی پنل ساب",
                            )
                except Exception as exc:  # noqa: BLE001
                    stats["failed"] += 1
                    logger.warning(
                        "Mexico maintenance failed for external token=%s: %s",
                        token,
                        exc,
                        exc_info=True,
                    )
                await asyncio.sleep(0.05)
        return stats


async def mexico_panel_maintenance_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    stats = await MexicoPanelMaintenanceService.run(context.bot)
    logger.info("Mexico panel maintenance finished: %s", stats)


def register_mexico_panel_maintenance_job(app: Application) -> None:
    if app.job_queue is None:
        logger.warning("JobQueue unavailable; Mexico panel maintenance was not registered.")
        return
    app.job_queue.run_repeating(
        mexico_panel_maintenance_job,
        interval=MAINTENANCE_INTERVAL_SECONDS,
        first=150,
        name="mexico_panel_maintenance",
        job_kwargs={"max_instances": 1, "coalesce": True},
    )
    logger.info("Registered Mexico panel maintenance job.")
