import logging

from telegram import BotCommand, MenuButtonWebApp, WebAppInfo
from telegram.ext import Application
from .config_loader import BotConfig
from .database import engine
from .handlers.user_handlers import user_handlers
from .services.schema_service import SchemaService

logger = logging.getLogger(__name__)


async def log_error(update, context):
    error = context.error
    logger.error("Main bot update failed", exc_info=(type(error), error, error.__traceback__))


async def setup_main_bot():
    await SchemaService.ensure_schema(engine)
    
    app = Application.builder().token(BotConfig.MAIN_BOT_TOKEN).build()
    await app.bot.set_my_commands(
        [
            BotCommand("start", "شروع و نمایش منوی اصلی"),
            BotCommand("app", "باز کردن فروشگاه"),
            BotCommand("verifyphone", "تایید شماره برای پرداخت ریالی"),
            BotCommand("buy", "خرید سرویس"),
            BotCommand("wallet", "کیف پول"),
            BotCommand("rial", "پرداخت ریالی کارت‌به‌کارت"),
            BotCommand("referrals", "دعوت دوستان"),
            BotCommand("account", "اطلاعات حساب"),
            BotCommand("help", "راهنما"),
            BotCommand("support", "پشتیبانی"),
        ]
    )
    await app.bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="app",
            web_app=WebAppInfo(url=BotConfig.WEBAPP_URL),
        )
    )
    for handler in user_handlers:
        app.add_handler(handler)
    app.add_error_handler(log_error)
    
    return app
