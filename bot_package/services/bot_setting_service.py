from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import BotSetting


class BotSettingService:
    BRANDED_LINKS = "branded_subscription_links_enabled"

    @staticmethod
    async def get_bool(session: AsyncSession, key: str, default: bool = True) -> bool:
        result = await session.execute(select(BotSetting).where(BotSetting.key == key))
        setting = result.scalar_one_or_none()
        if setting is None:
            return default
        return setting.value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    async def set_bool(session: AsyncSession, key: str, value: bool) -> bool:
        result = await session.execute(select(BotSetting).where(BotSetting.key == key))
        setting = result.scalar_one_or_none()
        if setting is None:
            setting = BotSetting(key=key, value="true" if value else "false")
            session.add(setting)
        else:
            setting.value = "true" if value else "false"
        await session.commit()
        return value

    @staticmethod
    async def branded_links_enabled(session: AsyncSession) -> bool:
        return await BotSettingService.get_bool(session, BotSettingService.BRANDED_LINKS, True)
