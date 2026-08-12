"""Background JobQueue tasks for crypto top-ups.

Registered on a single Application's job queue (it shares the bots' event loop):
  - refresh_rates_job:   pulls live rates into the cache every 10 minutes.
  - poll_payments_job:   scans pending invoices for on-chain payments and
                         credits wallets, notifying the user on success.
"""
import logging

from telegram.ext import Application, ContextTypes

from ..config_loader import BotConfig
from ..database import async_session
from .crypto_payment_service import CryptoPaymentService
from .rate_service import RateService
from .shop_customization_service import ShopCustomizationService

logger = logging.getLogger(__name__)


async def refresh_rates_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        rates = await RateService.refresh_online_rates()
        logger.debug("Refreshed crypto rates: %s", {k: str(v) for k, v in rates.items()})
    except Exception as exc:  # noqa: BLE001
        logger.warning("Rate refresh job failed: %s", exc)


async def poll_payments_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        async with async_session() as session:
            credited_invoices = await CryptoPaymentService.poll_pending(session)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Payment poll job failed: %s", exc)
        return

    # Notify users whose wallets were just credited (best-effort).
    for invoice in credited_invoices:
        try:
            toman = invoice["credited_toman"]
            async with async_session() as session:
                message = await ShopCustomizationService.get_message(
                    session,
                    "wallet_charge_notification",
                    amount=f"{toman:,}",
                    wallet_balance=f"{invoice['wallet_balance']:,}",
                )
                keyboard = await ShopCustomizationService.main_menu_keyboard(session)
            await context.bot.send_message(
                chat_id=invoice["user_id"],
                text=message,
                parse_mode=getattr(message, "parse_mode", None),
                reply_markup=keyboard,
            )
        except Exception as exc:  # noqa: BLE001
            logger.info("Could not notify user %s: %s", invoice.get("user_id"), exc)


def register_crypto_jobs(app: Application) -> None:
    """Attach the rate-refresh and payment-poll jobs to ``app``'s job queue."""
    if not BotConfig.CRYPTO_ENABLED:
        logger.info("Crypto disabled; skipping crypto job registration.")
        return
    if app.job_queue is None:
        logger.warning("JobQueue unavailable; crypto jobs not registered.")
        return
    # coalesce + max_instances=1 prevent overlapping runs from piling up if a
    # pass runs long (defense-in-depth; the UNIQUE tx_hash already blocks any
    # double-credit, but this also avoids wasting upstream API quota).
    app.job_queue.run_repeating(
        refresh_rates_job,
        interval=BotConfig.CRYPTO_RATE_REFRESH_SECONDS,
        first=1,
        name="crypto_refresh_rates",
        job_kwargs={"max_instances": 1, "coalesce": True},
    )
    app.job_queue.run_repeating(
        poll_payments_job,
        interval=BotConfig.CRYPTO_POLL_SECONDS,
        first=5,
        name="crypto_poll_payments",
        job_kwargs={"max_instances": 1, "coalesce": True},
    )
    logger.info("Registered crypto jobs (rate refresh + payment poll).")
