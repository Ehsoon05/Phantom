from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatMemberStatus

from ..models import RequiredChannel


ACTIVE_MEMBER_STATUSES = {
    ChatMemberStatus.OWNER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
}


class RequiredChannelService:
    @staticmethod
    async def list_channels(session: AsyncSession, active_only: bool = False) -> list[RequiredChannel]:
        stmt = select(RequiredChannel)
        if active_only:
            stmt = stmt.where(RequiredChannel.is_active == True)
        result = await session.execute(stmt.order_by(RequiredChannel.id))
        return list(result.scalars().all())

    @staticmethod
    async def get_channel(session: AsyncSession, channel_id: int) -> RequiredChannel | None:
        result = await session.execute(select(RequiredChannel).where(RequiredChannel.id == channel_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert_channel(session: AsyncSession, chat_id: str, title: str, join_url: str) -> RequiredChannel:
        chat_id = chat_id.strip()
        result = await session.execute(select(RequiredChannel).where(RequiredChannel.chat_id == chat_id))
        channel = result.scalar_one_or_none()
        if channel:
            channel.title = title.strip()
            channel.join_url = join_url.strip()
            channel.is_active = True
            channel.updated_at = datetime.now(timezone.utc)
            await session.commit()
            return channel

        channel = RequiredChannel(
            chat_id=chat_id,
            title=title.strip(),
            join_url=join_url.strip(),
            is_active=True,
        )
        session.add(channel)
        await session.commit()
        return channel

    @staticmethod
    async def delete_channel(session: AsyncSession, channel_id: int) -> bool:
        channel = await RequiredChannelService.get_channel(session, channel_id)
        if not channel:
            return False
        await session.delete(channel)
        await session.commit()
        return True

    @staticmethod
    async def toggle_channel(session: AsyncSession, channel_id: int) -> RequiredChannel | None:
        channel = await RequiredChannelService.get_channel(session, channel_id)
        if not channel:
            return None
        channel.is_active = not channel.is_active
        channel.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return channel

    @staticmethod
    async def missing_channels(bot, user_id: int, channels: list[RequiredChannel]) -> list[RequiredChannel]:
        missing = []
        for channel in channels:
            try:
                member = await bot.get_chat_member(channel.chat_id, user_id)
            except Exception:
                missing.append(channel)
                continue
            if member.status not in ACTIVE_MEMBER_STATUSES:
                missing.append(channel)
        return missing

    @staticmethod
    def join_keyboard(channels: list[RequiredChannel]) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton(f"عضویت در {channel.title}", url=channel.join_url)] for channel in channels]
        )
