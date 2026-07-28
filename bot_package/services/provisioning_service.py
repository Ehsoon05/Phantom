from __future__ import annotations

import base64
import json
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config_loader import BotConfig
from ..models import BotSetting, Config, ProvisionPanel, ShopPlan, ShopPlanCategory


class ProvisioningError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProvisionedSubscription:
    panel_key: str
    username: str
    subscription_url: str


def _clean_username(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_-")
    return cleaned or "PhantomHubs"


def _username_base_and_start(value: str) -> tuple[str, int]:
    cleaned = _clean_username(value)
    match = re.fullmatch(r"^(.*?)([0-9]+)$", cleaned)
    if not match:
        return cleaned, 1
    base = match.group(1) or cleaned
    return base, max(1, int(match.group(2)))


def effective_volume_gb(plan: ShopPlan) -> int:
    return int(plan.provision_volume_gb if plan.provision_volume_gb is not None else plan.volume_gb)


def effective_duration_days(plan: ShopPlan) -> int:
    return int(
        plan.provision_duration_days
        if plan.provision_duration_days is not None
        else (plan.duration_days if plan.duration_days is not None else 30)
    )


def effective_time_mode(plan: ShopPlan) -> str:
    mode = (plan.provision_time_mode or "on_hold").strip()
    return mode if mode in {"on_hold", "date", "unlimited"} else "on_hold"


def has_unlimited_time(plan: ShopPlan) -> bool:
    return effective_duration_days(plan) <= 0 or effective_time_mode(plan) == "unlimited"


def _create_timing_payload(plan: ShopPlan) -> dict[str, Any]:
    mode = effective_time_mode(plan)
    if has_unlimited_time(plan):
        return {
            "status": "active",
            "expire": 0,
            "on_hold_expire_duration": None,
        }
    duration_days = effective_duration_days(plan)
    if mode == "date":
        return {
            "status": "active",
            "expire": int((datetime.now(timezone.utc) + timedelta(days=duration_days)).timestamp()),
            "on_hold_expire_duration": None,
        }
    return {
        "status": "on_hold",
        "expire": 0,
        "on_hold_expire_duration": duration_days * 86400,
    }


def _renew_timing_payload(plan: ShopPlan) -> dict[str, Any]:
    if has_unlimited_time(plan):
        return {
            "status": "active",
            "expire": 0,
            "on_hold_expire_duration": None,
        }
    duration_days = effective_duration_days(plan)
    return {
        "status": "active",
        "expire": int((datetime.now(timezone.utc) + timedelta(days=duration_days)).timestamp()),
        "on_hold_expire_duration": None,
    }


def _json_list(value: str | None) -> list:
    if not value:
        return []
    try:
        payload = json.loads(value)
    except ValueError:
        return []
    return payload if isinstance(payload, list) else []


def _json_dict(value: str | None) -> dict:
    if not value:
        return {}
    try:
        payload = json.loads(value)
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _panel_error(response: httpx.Response, action: str) -> ProvisioningError:
    detail = response.text.strip()
    if len(detail) > 500:
        detail = f"{detail[:500]}..."
    return ProvisioningError(f"{action} انجام نشد: HTTP {response.status_code} - {detail}")


def _panel_api_base_url(panel: ProvisionPanel) -> str:
    return _panel_api_base_urls(panel)[0]


def _panel_api_base_urls(panel: ProvisionPanel) -> list[str]:
    candidates = [panel.base_url.rstrip("/")]
    if panel.key == "svn" and BotConfig.SVN_PANEL_API_URL:
        candidates.append(BotConfig.SVN_PANEL_API_URL.rstrip("/"))
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def _panel_http_headers(panel: ProvisionPanel) -> dict[str, str]:
    if panel.key != "svn":
        return {}
    return {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
    }


def _subscription_url(base_url: str, payload: dict[str, Any]) -> str:
    subscription_url = str(payload.get("subscription_url") or "").strip()
    if not subscription_url:
        raise ProvisioningError("پنل لینک اشتراک برنگرداند.")
    parsed = urlparse(subscription_url)
    if parsed.scheme and parsed.netloc:
        subscription_url = urlunparse(
            ("", "", parsed.path, parsed.params, parsed.query, parsed.fragment)
        )
    return urljoin(f"{base_url.rstrip('/')}/", subscription_url)


def username_from_subscription_url(url: str) -> str | None:
    parsed = urlparse(url.strip())
    parts = [part for part in parsed.path.split("/") if part]
    if not parts:
        return None

    token = parts[-1]
    candidates = [token]
    padded = token + "=" * (-len(token) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded.encode()).decode(errors="ignore")
        candidates.append(decoded)
    except Exception:
        pass

    for candidate in candidates:
        match = re.search(r"([A-Za-z][A-Za-z0-9_]{2,80})", candidate)
        if match:
            return _clean_username(match.group(1))
    return None


class ProvisioningService:
    @staticmethod
    @asynccontextmanager
    async def _api_client(
        panel: ProvisionPanel,
        *,
        timeout_seconds: float = 35,
        connect_timeout_seconds: float = 15,
    ):
        last_error: ProvisioningError | None = None
        for candidate_index, base_url in enumerate(_panel_api_base_urls(panel)):
            candidate_connect_timeout = connect_timeout_seconds
            if panel.key == "svn" and candidate_index > 0:
                # A private management relay is a fallback. Do not let a stale
                # or stopped relay hold the Telegram flow for a long time.
                candidate_connect_timeout = min(connect_timeout_seconds, 5)
            client = httpx.AsyncClient(
                base_url=base_url,
                timeout=httpx.Timeout(
                    timeout_seconds,
                    connect=candidate_connect_timeout,
                ),
                verify=False,
                headers=_panel_http_headers(panel),
            )
            try:
                token = await ProvisioningService._token(client, panel)
            except ProvisioningError as exc:
                last_error = exc
                await client.aclose()
                continue
            try:
                yield client, token
            finally:
                await client.aclose()
            return
        raise last_error or ProvisioningError("ارتباط با API پنل برقرار نشد.")

    @staticmethod
    async def ensure_env_panels(session: AsyncSession) -> None:
        defaults = [
            (
                "alien",
                "Alien",
                "pasarguard",
                BotConfig.ALIEN_PANEL_URL or BotConfig.MARZBAN_API_URL,
                BotConfig.ALIEN_PANEL_USERNAME or BotConfig.MARZBAN_API_USERNAME,
                BotConfig.ALIEN_PANEL_PASSWORD or BotConfig.MARZBAN_API_PASSWORD,
                None,
                None,
            ),
            (
                "easy",
                "آسان پنل",
                "easy",
                BotConfig.EASY_PANEL_URL,
                BotConfig.EASY_PANEL_USERNAME,
                BotConfig.EASY_PANEL_PASSWORD,
                "[1]",
                None,
            ),
            (
                "mexico_hajmi",
                "Mexico Hajmi",
                "pasarguard",
                BotConfig.MEXICO_HAJMI_PANEL_URL,
                BotConfig.MEXICO_HAJMI_PANEL_USERNAME,
                BotConfig.MEXICO_HAJMI_PANEL_PASSWORD,
                "[1]",
                BotConfig.MEXICO_HAJMI_PANEL_HWID_LIMIT,
            ),
            (
                "mexico_namahdod",
                "Mexico Namahdod",
                "pasarguard",
                BotConfig.MEXICO_NAMAHDOD_PANEL_URL,
                BotConfig.MEXICO_NAMAHDOD_PANEL_USERNAME,
                BotConfig.MEXICO_NAMAHDOD_PANEL_PASSWORD,
                "[1]",
                BotConfig.MEXICO_NAMAHDOD_PANEL_HWID_LIMIT,
            ),
            (
                "svn",
                "SVN",
                "marzban",
                BotConfig.SVN_PANEL_URL,
                BotConfig.SVN_PANEL_USERNAME,
                BotConfig.SVN_PANEL_PASSWORD,
                None,
                None,
            ),
        ]
        for key, title, panel_type, base_url, username, password, group_ids, hwid_limit in defaults:
            if not (base_url and username and password):
                continue
            existing = (
                await session.execute(select(ProvisionPanel).where(ProvisionPanel.key == key))
            ).scalar_one_or_none()
            if existing:
                existing.title = title
                existing.panel_type = panel_type
                existing.base_url = base_url
                existing.username = username
                existing.password = password
                if not existing.group_ids and group_ids:
                    existing.group_ids = group_ids
                if existing.hwid_limit is None and hwid_limit is not None:
                    existing.hwid_limit = hwid_limit
                continue
            session.add(
                ProvisionPanel(
                    key=key,
                    title=title,
                    panel_type=panel_type,
                    base_url=base_url,
                    username=username,
                    password=password,
                    group_ids=group_ids,
                    hwid_limit=hwid_limit,
                    is_enabled=True,
                )
            )
        await session.flush()

    @staticmethod
    async def get_panel(session: AsyncSession, key: str | None) -> ProvisionPanel | None:
        await ProvisioningService.ensure_env_panels(session)
        if not key:
            return None
        return (
            await session.execute(
                select(ProvisionPanel).where(
                    ProvisionPanel.key == key,
                    ProvisionPanel.is_enabled.is_(True),
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def panel_for_plan(session: AsyncSession, plan: ShopPlan) -> ProvisionPanel | None:
        category = (
            await session.execute(
                select(ShopPlanCategory).where(ShopPlanCategory.key == plan.category_key)
            )
        ).scalar_one_or_none()
        key = plan.provision_panel_key or (category.provision_panel_key if category else None)
        return await ProvisioningService.get_panel(session, key)

    @staticmethod
    def plan_provision_enabled(plan: ShopPlan, category: ShopPlanCategory | None = None) -> bool:
        return bool(plan.provision_enabled or (category and category.provision_enabled))

    @staticmethod
    async def next_username(session: AsyncSession, plan: ShopPlan) -> str:
        raw_prefix = (
            plan.name_prefix
            or f"PhantomHubs_{plan.category_key}_{plan.title}_{plan.volume_gb}GB"
        )
        base_name, start_number = _username_base_and_start(
            raw_prefix
        )
        key = f"provision_counter:{plan.id}"
        name_key = f"provision_counter_name:{plan.id}"
        setting = (
            await session.execute(select(BotSetting).where(BotSetting.key == key).with_for_update())
        ).scalar_one_or_none()
        name_setting = (
            await session.execute(select(BotSetting).where(BotSetting.key == name_key).with_for_update())
        ).scalar_one_or_none()
        prefix_changed = bool(name_setting and name_setting.value != base_name)
        if not name_setting and setting and plan.name_prefix and re.search(r"[0-9]+$", _clean_username(raw_prefix)):
            prefix_changed = True

        current = (
            int(setting.value)
            if setting and str(setting.value or "").isdigit() and not prefix_changed
            else start_number - 1
        )
        if current < start_number - 1:
            current = start_number - 1
        current += 1
        if setting:
            setting.value = str(current)
            setting.updated_at = datetime.now(timezone.utc)
        else:
            session.add(BotSetting(key=key, value=str(current)))
        if name_setting:
            name_setting.value = base_name
            name_setting.updated_at = datetime.now(timezone.utc)
        else:
            session.add(BotSetting(key=name_key, value=base_name))
        await session.flush()
        return f"{base_name}{current}"

    @staticmethod
    async def _token(client: httpx.AsyncClient, panel: ProvisionPanel) -> str:
        try:
            response = await client.post(
                "/api/admin/token",
                data={"username": panel.username, "password": panel.password},
            )
        except httpx.HTTPError as exc:
            raise ProvisioningError("ارتباط با API پنل برقرار نشد.") from exc

        challenge = (
            response.headers.get("cf-mitigated", "").lower() == "challenge"
            or (
                "text/html" in response.headers.get("content-type", "").lower()
                and "just a moment" in response.text.lower()
            )
        )
        if challenge:
            raise ProvisioningError(
                "Cloudflare دسترسی API پنل را با چالش تعاملی مسدود کرده است؛ "
                "برای /api/* باید WAF Skip یا یک آدرس مستقیم API تنظیم شود."
            )
        if response.status_code in {401, 403}:
            raise ProvisioningError("نام کاربری یا رمز پنل معتبر نیست، یا دسترسی API محدود شده است.")
        if response.is_error:
            raise _panel_error(response, "ورود به پنل")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProvisioningError("پاسخ ورود پنل JSON معتبر نیست.") from exc
        token = payload.get("access_token")
        if not token:
            raise ProvisioningError("پنل توکن دسترسی برنگرداند.")
        return str(token)

    @staticmethod
    async def _access_fields(client: httpx.AsyncClient, panel: ProvisionPanel, headers: dict) -> dict:
        grouped_panel = panel.panel_type in {"easy", "pasarguard"}
        fields: dict[str, Any] = {}
        if grouped_panel:
            group_ids = [int(item) for item in _json_list(panel.group_ids) if str(item).isdigit()]
            if panel.panel_type == "easy" and not group_ids:
                group_ids = [1]
            if group_ids:
                fields["group_ids"] = group_ids
            if panel.hwid_limit is not None and int(panel.hwid_limit) > 0:
                fields["hwid_limit"] = int(panel.hwid_limit)
            # Pasarguard groups own the inbound selection. Sending a legacy
            # inbound filter alongside them can unintentionally narrow a group.
            if panel.panel_type == "easy" or fields.get("group_ids"):
                return fields

        allowed_protocols = set(_json_list(panel.protocols_json))
        configured = _json_dict(panel.inbounds_json)
        if configured:
            protocols = sorted(configured)
            fields.update(
                {
                    "proxies": {protocol: {} for protocol in protocols},
                    "inbounds": configured,
                }
            )
            return fields

        try:
            response = await client.get("/api/inbounds", headers=headers)
            response.raise_for_status()
        except httpx.HTTPError:
            if grouped_panel and allowed_protocols:
                fields["proxies"] = {protocol: {} for protocol in sorted(allowed_protocols)}
            if grouped_panel:
                return fields
            raise
        payload = response.json()
        inbounds: dict[str, list[str]] = {}
        if isinstance(payload, dict):
            for protocol, items in payload.items():
                protocol = str(protocol)
                if allowed_protocols and protocol not in allowed_protocols:
                    continue
                if not isinstance(items, list):
                    continue
                tags = [
                    str(item.get("tag")).strip()
                    for item in items
                    if isinstance(item, dict) and item.get("tag")
                ]
                if tags:
                    inbounds[protocol] = tags
        elif isinstance(payload, list):
            tags = [str(item).strip() for item in payload if str(item).strip()]
            if tags:
                inbounds["vless"] = tags
        if not inbounds:
            if grouped_panel and allowed_protocols:
                fields["proxies"] = {protocol: {} for protocol in sorted(allowed_protocols)}
            if grouped_panel:
                return fields
            raise ProvisioningError("هیچ اینباند فعالی از پنل دریافت نشد.")
        fields.update({"proxies": {protocol: {} for protocol in inbounds}, "inbounds": inbounds})
        return fields

    @staticmethod
    async def fetch_inbounds(panel: ProvisionPanel) -> dict[str, list[str]]:
        if panel.panel_type == "easy":
            return {}
        async with ProvisioningService._api_client(panel) as (client, token):
            response = await client.get("/api/inbounds", headers={"Authorization": f"Bearer {token}"})
            response.raise_for_status()
            payload = response.json()

        inbounds: dict[str, list[str]] = {}
        if isinstance(payload, dict):
            for protocol, items in payload.items():
                if not isinstance(items, list):
                    continue
                tags = [
                    str(item.get("tag")).strip()
                    for item in items
                    if isinstance(item, dict) and item.get("tag")
                ]
                if tags:
                    inbounds[str(protocol)] = tags
        elif isinstance(payload, list):
            tags = [str(item).strip() for item in payload if str(item).strip()]
            if tags:
                inbounds["vless"] = tags
        return inbounds

    @staticmethod
    async def create_for_plan(
        session: AsyncSession,
        plan: ShopPlan,
        *,
        service_name: str | None = None,
    ) -> ProvisionedSubscription:
        panel = await ProvisioningService.panel_for_plan(session, plan)
        if panel is None:
            raise ProvisioningError("برای این دسته/پلن پنل فعال تنظیم نشده است.")
        username = await ProvisioningService.next_username(session, plan)
        volume_gb = effective_volume_gb(plan)
        data_limit = volume_gb * 1024**3 if volume_gb > 0 else 0
        async with ProvisioningService._api_client(panel) as (client, token):
            headers = {"Authorization": f"Bearer {token}"}
            access_fields = await ProvisioningService._access_fields(client, panel, headers)
            response = await client.post(
                "/api/user",
                headers=headers,
                json={
                    "username": username,
                    "data_limit": data_limit,
                    "data_limit_reset_strategy": "no_reset",
                    **_create_timing_payload(plan),
                    **access_fields,
                },
            )
            if response.is_error:
                raise _panel_error(response, "ساخت سرویس از پنل")
            payload = response.json()
        return ProvisionedSubscription(
            panel_key=panel.key,
            username=str(payload.get("username") or username),
            subscription_url=_subscription_url(panel.base_url, payload),
        )

    @staticmethod
    async def create_trial(
        session: AsyncSession,
        *,
        panel_key: str,
        username: str,
        volume_mb: int,
        duration_hours: int,
        time_mode: str = "date",
    ) -> ProvisionedSubscription:
        panel = await ProvisioningService.get_panel(session, panel_key)
        if panel is None:
            raise ProvisioningError("برای کانفیگ تست پنل فعال و معتبر تنظیم نشده است.")
        mode = time_mode if time_mode in {"date", "on_hold", "unlimited"} else "date"
        if mode == "unlimited":
            timing = {"status": "active", "expire": 0, "on_hold_expire_duration": None}
        elif mode == "on_hold":
            timing = {
                "status": "on_hold",
                "expire": 0,
                "on_hold_expire_duration": int(duration_hours) * 3600,
            }
        else:
            timing = {
                "status": "active",
                "expire": int((datetime.now(timezone.utc) + timedelta(hours=duration_hours)).timestamp()),
                "on_hold_expire_duration": None,
            }
        async with ProvisioningService._api_client(panel) as (client, token):
            headers = {"Authorization": f"Bearer {token}"}
            access_fields = await ProvisioningService._access_fields(client, panel, headers)
            response = await client.post(
                "/api/user",
                headers=headers,
                json={
                    "username": username,
                    "data_limit": int(volume_mb) * 1024 * 1024,
                    "data_limit_reset_strategy": "no_reset",
                    **timing,
                    **access_fields,
                },
            )
            if response.status_code == 409:
                response = await client.get(f"/api/user/{username}", headers=headers)
            if response.is_error:
                raise _panel_error(response, "ساخت کانفیگ تست از پنل")
            payload = response.json()
        return ProvisionedSubscription(
            panel_key=panel.key,
            username=str(payload.get("username") or username),
            subscription_url=_subscription_url(panel.base_url, payload),
        )

    @staticmethod
    async def renew_config(session: AsyncSession, config: Config, plan: ShopPlan) -> None:
        panel = await ProvisioningService.get_panel(session, config.panel_key)
        if panel is None:
            panel = await ProvisioningService.panel_for_plan(session, plan)
        username = config.panel_username or username_from_subscription_url(config.sub_link)
        if panel is None or not username:
            raise ProvisioningError("برای این سرویس اطلاعات پنل یا نام کاربری قابل تشخیص نیست.")
        volume_gb = effective_volume_gb(plan)
        data_limit = volume_gb * 1024**3 if volume_gb > 0 else 0
        async with ProvisioningService._api_client(panel) as (client, token):
            headers = {"Authorization": f"Bearer {token}"}
            response = await client.put(
                f"/api/user/{username}",
                headers=headers,
                json={
                    "data_limit": data_limit,
                    "data_limit_reset_strategy": "no_reset",
                    **_renew_timing_payload(plan),
                },
            )
            if response.is_error:
                raise _panel_error(response, "تمدید سرویس در پنل")
            reset = await client.post(f"/api/user/{username}/reset", headers=headers)
            if reset.status_code not in {200, 204, 404, 405}:
                raise _panel_error(reset, "ریست حجم سرویس در پنل")

        config.panel_key = panel.key
        config.panel_username = username
        config.expired_detected_at = None
        config.deletion_due_at = None
        config.panel_deleted_at = None
        await session.flush()

    @staticmethod
    async def fetch_config_status(session: AsyncSession, config: Config) -> str | None:
        panel = await ProvisioningService.get_panel(session, config.panel_key)
        username = config.panel_username or username_from_subscription_url(config.sub_link)
        if panel is None or not username:
            return None
        async with ProvisioningService._api_client(
            panel,
            timeout_seconds=25,
            connect_timeout_seconds=10,
        ) as (client, token):
            response = await client.get(
                f"/api/user/{username}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code == 404:
                return "deleted"
            if response.is_error:
                raise _panel_error(response, "دریافت وضعیت سرویس از پنل")
            payload = response.json()
        config.panel_key = panel.key
        config.panel_username = username
        await session.flush()
        return str(payload.get("status") or "").strip() or None

    @staticmethod
    async def set_config_enabled(session: AsyncSession, config: Config, enabled: bool) -> str:
        panel = await ProvisioningService.get_panel(session, config.panel_key)
        username = config.panel_username or username_from_subscription_url(config.sub_link)
        if panel is None or not username:
            raise ProvisioningError("برای تغییر وضعیت سرویس، اطلاعات پنل یا نام کاربری قابل تشخیص نیست.")
        new_status = "active" if enabled else "disabled"
        async with ProvisioningService._api_client(panel) as (client, token):
            response = await client.put(
                f"/api/user/{username}",
                headers={"Authorization": f"Bearer {token}"},
                json={"status": new_status},
            )
            if response.is_error:
                raise _panel_error(response, "تغییر وضعیت سرویس در پنل")
        config.panel_key = panel.key
        config.panel_username = username
        await session.flush()
        return new_status

    @staticmethod
    async def delete_config(session: AsyncSession, config: Config) -> bool:
        panel = await ProvisioningService.get_panel(session, config.panel_key)
        username = config.panel_username or username_from_subscription_url(config.sub_link)
        if panel is None or not username:
            raise ProvisioningError("برای حذف سرویس، اطلاعات پنل یا نام کاربری قابل تشخیص نیست.")
        async with ProvisioningService._api_client(panel) as (client, token):
            response = await client.delete(
                f"/api/user/{username}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code not in {200, 204, 404}:
                raise _panel_error(response, "حذف سرویس از پنل")

        now = datetime.now(timezone.utc)
        config.panel_key = panel.key
        config.panel_username = username
        config.panel_deleted_at = now
        await session.flush()
        return True
