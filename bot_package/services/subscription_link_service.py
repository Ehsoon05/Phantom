from __future__ import annotations

import secrets
from urllib.parse import quote, urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config_loader import BotConfig
from ..models import Config


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
