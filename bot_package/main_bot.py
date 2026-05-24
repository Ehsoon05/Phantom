import logging

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
    for handler in user_handlers:
        app.add_handler(handler)
    app.add_error_handler(log_error)
    
    return app
