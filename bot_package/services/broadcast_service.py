from __future__ import annotations

import asyncio
from datetime import timedelta

from sqlalchemy import select
from telegram import Bot
from telegram.error import BadRequest, Forbidden, NetworkError, RetryAfter, TelegramError

from ..config_loader import BotConfig
from ..models import User


class BroadcastService:
    @staticmethod
    async def recipient_ids(session) -> list[int]:
        result = await session.execute(
            select(User.telegram_id)
            .where(User.is_blocked.is_(False))
            .order_by(User.id)
        )
        return [int(user_id) for user_id in result.scalars().all()]

    @staticmethod
    def _retry_seconds(error: RetryAfter) -> float:
        retry_after = error.retry_after
        if isinstance(retry_after, timedelta):
            return max(retry_after.total_seconds(), 0.0)
        return max(float(retry_after), 0.0)

    @staticmethod
    async def send_text(user_ids: list[int], *, text: str, parse_mode: str | None) -> dict[str, int]:
        stats = {"total": len(user_ids), "sent": 0, "blocked": 0, "failed": 0}
        async with Bot(BotConfig.MAIN_BOT_TOKEN) as bot:
            for user_id in user_ids:
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=text,
                        parse_mode=parse_mode,
                        disable_web_page_preview=True,
                    )
                    stats["sent"] += 1
                except RetryAfter as exc:
                    await asyncio.sleep(BroadcastService._retry_seconds(exc) + 0.25)
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=text,
                            parse_mode=parse_mode,
                            disable_web_page_preview=True,
                        )
                        stats["sent"] += 1
                    except (Forbidden, BadRequest):
                        stats["blocked"] += 1
                    except TelegramError:
                        stats["failed"] += 1
                except (Forbidden, BadRequest):
                    stats["blocked"] += 1
                except (NetworkError, TelegramError):
                    stats["failed"] += 1
                await asyncio.sleep(0.05)
        return stats
