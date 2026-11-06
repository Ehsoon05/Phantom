import logging

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot

from ..config_loader import BotConfig
from .shop_customization_service import ShopCustomizationService

logger = logging.getLogger(__name__)


class WalletNotificationService:
    @staticmethod
    async def send_charge_notification(
        session: AsyncSession,
        *,
        telegram_id: int,
        amount: int,
        wallet_balance: int,
        bot: Bot | None = None,
    ) -> bool:
        message = await ShopCustomizationService.get_message(
            session,
            "wallet_charge_notification",
            amount=f"{amount:,}",
            wallet_balance=f"{wallet_balance:,}",
        )
        keyboard = await ShopCustomizationService.main_menu_keyboard(session)

        try:
            if bot is not None:
                await bot.send_message(
                    chat_id=telegram_id,
                    text=message,
                    parse_mode=message.parse_mode,
                    reply_markup=keyboard,
                )
            else:
                async with Bot(BotConfig.MAIN_BOT_TOKEN) as main_bot:
                    await main_bot.send_message(
                        chat_id=telegram_id,
                        text=message,
                        parse_mode=message.parse_mode,
                        reply_markup=keyboard,
                    )
        except Exception as exc:
            logger.info(
                "Could not notify wallet charge for user %s: %s",
                telegram_id,
                exc,
            )
            return False
        return True
