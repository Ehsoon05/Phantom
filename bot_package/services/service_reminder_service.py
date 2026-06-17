from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import Application, ContextTypes

from ..database import async_session
from ..models import Config, Purchase, ServiceReminderLog, User
from .settings_service import SettingsService
from .shop_customization_service import ShopCustomizationService
from .subscription_link_service import SubscriptionLinkService

logger = logging.getLogger(__name__)

RENEW_PREMIUM_EMOJI_ID = "6030657343744644592"
SERVICE_REMINDER_BATCH_SIZE = 120
SERVICE_REMINDER_SEND_DELAY_SECONDS = 0.35


class ServiceReminderService:
    @staticmethod
    async def scan_and_notify(bot) -> dict[str, int]:
        async with async_session() as session:
            if not await SettingsService.service_reminders_enabled(session):
                return {"checked": 0, "sent": 0, "skipped": 0}
            volume_thresholds = await SettingsService.get_service_reminder_volume_percents(session)
            time_thresholds = await SettingsService.get_service_reminder_time_days(session)

        checked = sent = skipped = 0
        last_id = 0
        while True:
            async with async_session() as session:
                result = await session.execute(
                    select(Purchase)
                    .join(User, User.telegram_id == Purchase.user_id)
                    .options(selectinload(Purchase.config))
                    .where(
                        Purchase.id > last_id,
                        Purchase.kind == "purchase",
                        User.is_blocked.is_(False),
                    )
                    .order_by(Purchase.id)
                    .limit(SERVICE_REMINDER_BATCH_SIZE)
                )
                purchases = result.scalars().all()
            if not purchases:
                break

            for purchase in purchases:
                checked += 1
                last_id = max(last_id, purchase.id)
                try:
                    delivered = await ServiceReminderService._process_purchase(
                        bot,
                        purchase,
                        volume_thresholds,
                        time_thresholds,
                    )
                    if delivered:
                        sent += 1
                        await asyncio.sleep(SERVICE_REMINDER_SEND_DELAY_SECONDS)
                    else:
                        skipped += 1
                except Exception as exc:  # noqa: BLE001
                    skipped += 1
                    logger.info("Service reminder skipped purchase %s: %s", purchase.id, exc)

        return {"checked": checked, "sent": sent, "skipped": skipped}

    @staticmethod
    async def _process_purchase(
        bot,
        purchase: Purchase,
        volume_thresholds: list[int],
        time_thresholds: list[int],
    ) -> bool:
        config = purchase.config
        if not config or not config.public_sub_token:
            return False

        metadata = await SubscriptionLinkService.fetch_metadata(config.public_sub_token)
        if not metadata:
            return False

        due_rules, template_values = await ServiceReminderService._due_rules(
            purchase,
            config,
            metadata,
            volume_thresholds,
            time_thresholds,
        )
        if not due_rules:
            return False

        async with async_session() as session:
            message = await ShopCustomizationService.get_message(
                session,
                "service_expiry_reminder",
                escape_markdown_values=True,
                **template_values,
            )

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "تمدید سرویس",
                        callback_data=f"renew_confirm:{purchase.id}",
                        api_kwargs={
                            "style": "primary",
                            "icon_custom_emoji_id": RENEW_PREMIUM_EMOJI_ID,
                        },
                    )
                ]
            ]
        )
        try:
            await bot.send_message(
                chat_id=purchase.user_id,
                text=message,
                reply_markup=keyboard,
                parse_mode=getattr(message, "parse_mode", None),
                disable_web_page_preview=True,
            )
        except TelegramError as exc:
            logger.info("Could not send service reminder to %s: %s", purchase.user_id, exc)
            return False

        async with async_session() as session:
            for rule_key in due_rules:
                session.add(
                    ServiceReminderLog(
                        purchase_id=purchase.id,
                        config_id=config.id,
                        user_id=purchase.user_id,
                        rule_key=rule_key,
                        remaining_percent=template_values["remaining_percent_value"],
                        remaining_seconds=template_values["remaining_seconds_value"],
                    )
                )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
        return True

    @staticmethod
    async def _due_rules(
        purchase: Purchase,
        config: Config,
        metadata: dict,
        volume_thresholds: list[int],
        time_thresholds: list[int],
    ) -> tuple[list[str], dict]:
        async with async_session() as session:
            result = await session.execute(
                select(ServiceReminderLog.rule_key).where(ServiceReminderLog.purchase_id == purchase.id)
            )
            sent_rules = set(result.scalars().all())

        due_rules: list[str] = []
        reasons: list[str] = []
        total = _to_int(metadata.get("total"))
        remaining = _to_int(metadata.get("remaining"))
        remaining_percent_value: int | None = None
        if total and total > 0 and remaining is not None:
            remaining_percent_value = max(0, min(100, int((remaining / total) * 100)))
            for threshold in sorted(volume_thresholds):
                rule_key = f"volume_{threshold}"
                if remaining_percent_value <= threshold and rule_key not in sent_rules:
                    due_rules.append(rule_key)
                    reasons.append(f"حجم باقی‌مانده سرویس به کمتر از {threshold}٪ رسیده است.")
                    break

        expire = _to_int(metadata.get("expire"))
        remaining_seconds_value: int | None = None
        if expire:
            remaining_seconds_value = int(expire - datetime.now(timezone.utc).timestamp())
            if remaining_seconds_value > 0:
                for days in sorted(time_thresholds):
                    rule_key = f"time_{days}d"
                    if remaining_seconds_value <= days * 86400 and rule_key not in sent_rules:
                        due_rules.append(rule_key)
                        reasons.append(f"کمتر از {days} روز تا پایان اعتبار سرویس باقی مانده است.")
                        break

        expiry_text, remaining_time = _format_expiry(expire)
        service_name = purchase.service_name or metadata.get("title") or f"{purchase.volume_gb} گیگ"
        values = {
            "service_name": service_name,
            "reason_lines": "\n".join(f"• {reason}" for reason in reasons),
            "total_volume": _format_service_bytes(total) if total else ("نامحدود" if purchase.volume_gb <= 0 else f"{purchase.volume_gb} گیگابایت"),
            "remaining_volume": _format_service_bytes(remaining),
            "remaining_percent": f"{remaining_percent_value}٪" if remaining_percent_value is not None else "نامشخص",
            "expiry_text": expiry_text,
            "remaining_time": remaining_time,
            "category_key": purchase.category_key or config.category_key or "default",
            "remaining_percent_value": remaining_percent_value,
            "remaining_seconds_value": remaining_seconds_value,
        }
        return due_rules, values


async def service_reminders_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        stats = await ServiceReminderService.scan_and_notify(context.bot)
        logger.info("Service reminder job finished: %s", stats)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Service reminder job failed: %s", exc, exc_info=True)


async def register_service_reminder_jobs(app: Application) -> None:
    if app.job_queue is None:
        logger.warning("JobQueue unavailable; service reminder jobs not registered.")
        return
    async with async_session() as session:
        interval = await SettingsService.get_service_reminder_interval_seconds(session)
    app.job_queue.run_repeating(
        service_reminders_job,
        interval=interval,
        first=90,
        name="service_expiry_reminders",
        job_kwargs={"max_instances": 1, "coalesce": True},
    )
    logger.info("Registered service reminder job with interval=%s seconds.", interval)


def _to_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _format_service_bytes(value: int | None) -> str:
    if value is None:
        return "نامشخص"
    units = ("بایت", "کیلوبایت", "مگابایت", "گیگابایت", "ترابایت")
    size = float(max(value, 0))
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f"{size:.1f} {units[index]}"


def _format_expiry(expire: int | None) -> tuple[str, str]:
    if not expire:
        return "نامحدود", "نامحدود"
    expiry = datetime.fromtimestamp(expire, timezone.utc)
    remaining = expiry - datetime.now(timezone.utc)
    if remaining.total_seconds() <= 0:
        return expiry.strftime("%Y-%m-%d %H:%M UTC"), "منقضی شده"
    days = remaining.days
    hours = remaining.seconds // 3600
    return expiry.strftime("%Y-%m-%d %H:%M UTC"), f"{days} روز و {hours} ساعت"
