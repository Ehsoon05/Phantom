import asyncio
import contextlib
import logging
import signal

from bot_package.admin_bot import setup_admin_bot
from bot_package.config_loader import BotConfig
from bot_package.database import async_session, engine
from bot_package.main_bot import setup_main_bot
from bot_package.receipt_bot import setup_receipt_bot
from bot_package.services.admin_service import AdminService
from bot_package.services.price_service import PriceService
from bot_package.services.crypto_jobs import register_crypto_jobs
from bot_package.services.required_channel_service import RequiredChannelService
from bot_package.services.schema_service import SchemaService
from bot_package.services.settings_service import SettingsService
from bot_package.services.shop_customization_service import ShopCustomizationService
from bot_package.services.service_reminder_service import register_service_reminder_jobs
from bot_package.services.panel_bridge_jobs import register_panel_bridge_jobs
from bot_package.services.panel_bridge_service import PanelBridgeService

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
        await ShopCustomizationService.init_defaults(session)
        await RequiredChannelService.init_defaults(session)
        await SettingsService.init_defaults(session)
        await PanelBridgeService.migrate_phantom_tunnel_hajmi_scope(session)
        await AdminService.sync_configured_admins(session)

    main_app = await setup_main_bot()
    admin_app = await setup_admin_bot()
    receipt_app = await setup_receipt_bot()

    # Crypto background jobs run on the main (user-facing) bot so payment
    # confirmations are delivered to users.
    register_crypto_jobs(main_app)
    await register_service_reminder_jobs(main_app)
    register_panel_bridge_jobs(main_app)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)

    apps = [main_app, admin_app]
    if receipt_app is not None:
        apps.append(receipt_app)
    await asyncio.gather(*(_start_polling(app) for app in apps))
    logger.info("%s Telegram bots are running", len(apps))
    print(f"{len(apps)} Telegram bots are running. Press Ctrl+C to stop.")

    try:
        await stop_event.wait()
    finally:
        await asyncio.gather(*(_stop_polling(app) for app in apps))


if __name__ == "__main__":
    asyncio.run(main())
