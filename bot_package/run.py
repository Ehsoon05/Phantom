import asyncio
import contextlib
import logging
import signal

from bot_package.admin_bot import setup_admin_bot
from bot_package.config_loader import BotConfig
from bot_package.database import async_session, engine
from bot_package.main_bot import setup_main_bot
from bot_package.services.admin_service import AdminService
from bot_package.services.price_service import PriceService
from bot_package.services.schema_service import SchemaService

logger = logging.getLogger(__name__)


def configure_logging():
    logging.basicConfig(
        level=getattr(logging, BotConfig.LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


async def _start_polling(app):
    await app.initialize()
    await app.start()
    if app.updater is None:
        raise RuntimeError("Application updater is not available for polling")
    await app.updater.start_polling()


async def _stop_polling(app):
    if app.updater is not None and app.updater.running:
        await app.updater.stop()
    if app.running:
        await app.stop()
    await app.shutdown()


async def main():
    BotConfig.validate()
    configure_logging()

    await SchemaService.ensure_schema(engine)

    async with async_session() as session:
        await PriceService.init_default_prices(session)
        await AdminService.sync_configured_admins(session)

    main_app = await setup_main_bot()
    admin_app = await setup_admin_bot()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)

    await asyncio.gather(_start_polling(main_app), _start_polling(admin_app))
    logger.info("Both Telegram bots are running")
    print("Both Telegram bots are running. Press Ctrl+C to stop.")

    try:
        await stop_event.wait()
    finally:
        await asyncio.gather(_stop_polling(main_app), _stop_polling(admin_app))


if __name__ == "__main__":
    asyncio.run(main())
