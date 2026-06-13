import logging

from telegram import BotCommand
from telegram.ext import Application
from .config_loader import BotConfig
from .handlers.admin_handlers import admin_handlers

logger = logging.getLogger(__name__)


async def log_error(update, context):
    error = context.error
    logger.error("Admin bot update failed", exc_info=(type(error), error, error.__traceback__))


async def setup_admin_bot():
    app = Application.builder().token(BotConfig.ADMIN_BOT_TOKEN).build()
    await app.bot.set_my_commands(
        [
            BotCommand("start", "ورود به پنل مدیریت"),
            BotCommand("chargeuser", "شارژ کیف پول کاربر"),
            BotCommand("admins", "لیست ادمین‌ها"),
            BotCommand("addadmin", "افزودن ادمین"),
            BotCommand("removeadmin", "حذف ادمین"),
            BotCommand("setadminperms", "تغییر دسترسی ادمین"),
            BotCommand("broadcast", "ارسال پیام همگانی"),
            BotCommand("cancel", "لغو عملیات"),
        ]
    )
    for handler in admin_handlers:
        app.add_handler(handler)
    app.add_error_handler(log_error)
    return app
