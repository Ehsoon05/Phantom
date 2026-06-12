from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from ..config_loader import BotConfig


class MarzbanTrialError(RuntimeError):
    pass


@dataclass(frozen=True)
class MarzbanTrial:
    username: str
    subscription_url: str


class MarzbanTrialService:
    @staticmethod
    def username_for(telegram_id: int) -> str:
        return f"PhantomHubs_test_{telegram_id}"

    @staticmethod
    def inbound_tags(payload) -> list[str]:
        if isinstance(payload, list):
            return [str(tag).strip() for tag in payload if str(tag).strip()]
        if isinstance(payload, dict):
            return [
                item["tag"]
                for item in payload.get("vless", [])
                if isinstance(item, dict) and item.get("tag")
            ]
        return []

    @staticmethod
    async def _token(client: httpx.AsyncClient) -> str:
        if not all(
            (
                BotConfig.MARZBAN_API_URL,
                BotConfig.MARZBAN_API_USERNAME,
                BotConfig.MARZBAN_API_PASSWORD,
            )
        ):
            raise MarzbanTrialError("Marzban API credentials are not configured")
        response = await client.post(
            f"{BotConfig.MARZBAN_API_URL}/api/admin/token",
            data={
                "username": BotConfig.MARZBAN_API_USERNAME,
                "password": BotConfig.MARZBAN_API_PASSWORD,
            },
        )
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            raise MarzbanTrialError("Marzban did not return an access token")
        return token

    @staticmethod
    def _result(payload: dict) -> MarzbanTrial:
        subscription_url = str(payload.get("subscription_url") or "").strip()
        username = str(payload.get("username") or "").strip()
        if not username or not subscription_url:
            raise MarzbanTrialError("Marzban response does not contain a subscription URL")
        return MarzbanTrial(
            username=username,
            subscription_url=urljoin(f"{BotConfig.MARZBAN_API_URL}/", subscription_url),
        )

    @staticmethod
    async def create_or_get(telegram_id: int, volume_mb: int, duration_hours: int) -> MarzbanTrial:
        username = MarzbanTrialService.username_for(telegram_id)
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                token = await MarzbanTrialService._token(client)
                headers = {"Authorization": f"Bearer {token}"}
                inbounds_response = await client.get(
                    f"{BotConfig.MARZBAN_API_URL}/api/inbounds",
                    headers=headers,
                )
                inbounds_response.raise_for_status()
                inbound_payload = inbounds_response.json()
                vless_tags = MarzbanTrialService.inbound_tags(inbound_payload)
                if not vless_tags:
                    raise MarzbanTrialError("No VLESS inbound is available")

                response = await client.post(
                    f"{BotConfig.MARZBAN_API_URL}/api/user",
                    headers=headers,
                    json={
                        "username": username,
                        "status": "on_hold",
                        "data_limit": int(volume_mb) * 1024 * 1024,
                        "data_limit_reset_strategy": "no_reset",
                        "on_hold_expire_duration": int(duration_hours) * 3600,
                        "proxies": {"vless": {}},
                        "inbounds": {"vless": vless_tags},
                        "note": f"Telegram trial for {telegram_id}",
                    },
                )
                if response.status_code == 409:
                    response = await client.get(
                        f"{BotConfig.MARZBAN_API_URL}/api/user/{username}",
                        headers=headers,
                    )
                response.raise_for_status()
                return MarzbanTrialService._result(response.json())
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise MarzbanTrialError("Could not create the Marzban trial") from exc
