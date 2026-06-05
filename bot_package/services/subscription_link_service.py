from __future__ import annotations

import secrets
import logging
from urllib.parse import quote, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config_loader import BotConfig
from ..models import Config


logger = logging.getLogger(__name__)


class SubscriptionLinkService:
    @staticmethod
    def public_link(token: str) -> str:
        return f"{BotConfig.SUBSCRIPTION_PUBLIC_BASE_URL}/token/{quote(token, safe='')}"

    @staticmethod
    def token_from_url(url: str) -> str:
        parsed = urlparse(url.strip())
        parts = [part for part in parsed.path.split("/") if part]
        if parts:
            candidate = parts[-1].strip()
            if candidate:
                return candidate
        return secrets.token_urlsafe(24)

    @staticmethod
    async def ensure_public_token(session: AsyncSession, config: Config) -> str:
        if config.public_sub_token:
            return config.public_sub_token

        base_token = SubscriptionLinkService.token_from_url(config.sub_link)
        token = base_token
        suffix = 1
        while True:
            result = await session.execute(select(Config).where(Config.public_sub_token == token))
            existing = result.scalar_one_or_none()
            if existing is None or existing.id == config.id:
                break
            suffix += 1
            token = f"{base_token}-{suffix}"

        config.public_sub_token = token
        await session.flush()
        return token

    @staticmethod
    async def public_link_for_config(session: AsyncSession, config: Config) -> str:
        token = await SubscriptionLinkService.ensure_public_token(session, config)
        return SubscriptionLinkService.public_link(token)

    @staticmethod
    async def sync_to_panel(config: Config, service_name: str | None = None) -> None:
        if not BotConfig.SUBSCRIPTION_PANEL_SYNC_URL or not BotConfig.SUBSCRIPTION_PANEL_SYNC_TOKEN:
            return
        if not config.public_sub_token:
            return

        payload = {
            "token": config.public_sub_token,
            "upstream_url": config.sub_link,
            "volume_gb": config.volume_gb,
            "category_key": config.category_key or "default",
            "is_sold": bool(config.is_sold),
            "service_name": service_name,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    BotConfig.SUBSCRIPTION_PANEL_SYNC_URL,
                    json=payload,
                    headers={"Authorization": f"Bearer {BotConfig.SUBSCRIPTION_PANEL_SYNC_TOKEN}"},
                )
                response.raise_for_status()
        except httpx.HTTPError:
            logger.warning("Failed to sync subscription config %s to panel", config.id, exc_info=True)
