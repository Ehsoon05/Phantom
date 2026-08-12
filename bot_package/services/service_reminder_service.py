from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import Application, ContextTypes

from ..database import async_session
from ..models import Config, Purchase, ServiceReminderLog, User
from .marzban_trial_service import MarzbanTrialError, MarzbanTrialService
from .provisioning_service import ProvisioningError, ProvisioningService
from .settings_service import SettingsService
from .shop_customization_service import ShopCustomizationService
from .subscription_link_service import SubscriptionLinkService
from ..utils.datetime_format import format_tehran_datetime, format_tehran_timestamp

logger = logging.getLogger(__name__)

RENEW_PREMIUM_EMOJI_ID = "6030657343744644592"
SERVICE_REMINDER_BATCH_SIZE = 120
SERVICE_REMINDER_SEND_DELAY_SECONDS = 0.35
SERVICE_DELETION_GRACE = timedelta(days=3)


class ServiceReminderService:
    @staticmethod
    async def scan_and_notify(bot) -> dict[str, int]:
        async with async_session() as session:
            if not await SettingsService.service_reminders_enabled(session):
                return {"checked": 0, "sent": 0, "skipped": 0}
            volume_thresholds = await SettingsService.get_service_reminder_volume_percents(session)
            time_day_thresholds = await SettingsService.get_service_reminder_time_days(session)
            time_hour_thresholds = await SettingsService.get_service_reminder_time_hours(session)

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
                        time_day_thresholds,
                        time_hour_thresholds,
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
        time_day_thresholds: list[int],
        time_hour_thresholds: list[int],
    ) -> bool:
        config = purchase.config
        if not config or not config.public_sub_token:
            return False

        metadata = await SubscriptionLinkService.fetch_metadata(config.public_sub_token)
        if not metadata:
            return False

        finished = ServiceReminderService._metadata_finished(metadata)
        trial = ServiceReminderService._is_trial(purchase, config)
        if trial and finished:
            return await ServiceReminderService._delete_expired_service(bot, purchase, config, metadata)

        config = await ServiceReminderService._sync_expiration_state(config, finished)
        if config.panel_deleted_at:
            return False

        now = datetime.now(timezone.utc)
        deletion_due_at = _as_utc(config.deletion_due_at)
        if deletion_due_at and deletion_due_at <= now:
            return await ServiceReminderService._delete_expired_service(bot, purchase, config, metadata)

        due_rules, template_values = await ServiceReminderService._due_rules(
            purchase,
            config,
            metadata,
            volume_thresholds,
            time_day_thresholds,
            time_hour_thresholds,
        )
        if not due_rules:
            return False

        trial = ServiceReminderService._is_trial(purchase, config)
        if trial:
            message = ServiceReminderService._trial_message(template_values)
        else:
            async with async_session() as session:
                message = await ShopCustomizationService.get_message(
                    session,
                    "service_expiry_reminder",
                    escape_markdown_values=True,
                    **template_values,
                )

        keyboard = ServiceReminderService._renew_keyboard(purchase, config)
        try:
            await bot.send_message(
                chat_id=purchase.user_id,
                text=message,
                reply_markup=keyboard,
                parse_mode=None if trial else getattr(message, "parse_mode", None),
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
    async def _sync_expiration_state(config: Config, finished: bool) -> Config:
        async with async_session() as session:
            db_config = await session.get(Config, config.id)
            if db_config is None:
                return config
            if db_config.panel_deleted_at:
                await session.commit()
                return db_config
            if finished:
                now = datetime.now(timezone.utc)
                if db_config.expired_detected_at is None:
                    db_config.expired_detected_at = now
                    db_config.deletion_due_at = now + SERVICE_DELETION_GRACE
            else:
                db_config.expired_detected_at = None
                db_config.deletion_due_at = None
            await session.commit()
            return db_config

    @staticmethod
    async def _delete_expired_service(bot, purchase: Purchase, config: Config, metadata: dict) -> bool:
        async with async_session() as session:
            db_config = await session.get(Config, config.id)
            if db_config is None or db_config.panel_deleted_at:
                return False
            try:
                if ServiceReminderService._is_trial(purchase, db_config):
                    if db_config.panel_key:
                        await ProvisioningService.delete_config(session, db_config)
                    else:
                        username = db_config.panel_username or MarzbanTrialService.username_for(purchase.user_id)
                        await MarzbanTrialService.delete(username)
                        db_config.panel_deleted_at = datetime.now(timezone.utc)
                        await session.flush()
                else:
                    await ProvisioningService.delete_config(session, db_config)
                await session.commit()
            except MarzbanTrialError as exc:
                await session.rollback()
                logger.warning("Could not delete trial config %s: %s", config.id, exc)
                return False
            except ProvisioningError as exc:
                await session.rollback()
                logger.warning("Could not delete expired config %s: %s", config.id, exc)
                return False
            except Exception as exc:  # noqa: BLE001
                await session.rollback()
                logger.warning("Panel delete failed for config %s: %s", config.id, exc, exc_info=True)
                return False

        _, values = await ServiceReminderService._due_rules(
            purchase,
            config,
            metadata,
            [],
            [],
            [],
        )
        if ServiceReminderService._is_trial(purchase, config):
            values["reason_lines"] = "• زمان سرویس تست تمام شد و سرویس از پنل حذف شد."
        else:
            values["reason_lines"] = "• مهلت ۳ روزه تمدید تمام شد و سرویس از پنل حذف شد."
        trial = ServiceReminderService._is_trial(purchase, config)
        if trial:
            message = ServiceReminderService._trial_message(values)
        else:
            async with async_session() as session:
                message = await ShopCustomizationService.get_message(
                    session,
                    "service_expiry_reminder",
                    escape_markdown_values=True,
                    **values,
                )
        try:
            await bot.send_message(
                chat_id=purchase.user_id,
                text=message,
                reply_markup=None,
                parse_mode=None if trial else getattr(message, "parse_mode", None),
                disable_web_page_preview=True,
            )
        except TelegramError as exc:
            logger.info("Could not notify deleted service to %s: %s", purchase.user_id, exc)
        async with async_session() as session:
            session.add(
                ServiceReminderLog(
                    purchase_id=purchase.id,
                    config_id=config.id,
                    user_id=purchase.user_id,
                    rule_key="panel_deleted",
                    remaining_percent=values["remaining_percent_value"],
                    remaining_seconds=0,
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
        time_day_thresholds: list[int],
        time_hour_thresholds: list[int],
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
            if remaining <= 0:
                rule_key = "volume_empty"
                if rule_key not in sent_rules:
                    due_rules.append(rule_key)
                    reasons.append("حجم سرویس شما تمام شده است.")
            else:
                sent_volume_thresholds = _sent_thresholds(sent_rules, "volume_", "")
                for threshold in sorted(volume_thresholds):
                    rule_key = f"volume_{threshold}"
                    if any(sent_threshold <= threshold for sent_threshold in sent_volume_thresholds):
                        continue
                    if remaining_percent_value <= threshold and rule_key not in sent_rules:
                        due_rules.append(rule_key)
                        reasons.append(f"حجم باقی‌مانده سرویس به کمتر از {threshold}٪ رسیده است.")
                        break

        expire = _to_int(metadata.get("expire"))
        remaining_seconds_value: int | None = None
        if expire:
            remaining_seconds_value = int(expire - datetime.now(timezone.utc).timestamp())
            if remaining_seconds_value <= 0:
                rule_key = "time_expired"
                if rule_key not in sent_rules:
                    due_rules.append(rule_key)
                    reasons.append("زمان اعتبار سرویس شما به پایان رسیده است.")
            else:
                sent_time_hours = _sent_thresholds(sent_rules, "time_", "h")
                hour_rule_added = False
                for hours in sorted(time_hour_thresholds):
                    rule_key = f"time_{hours}h"
                    if any(sent_hours <= hours for sent_hours in sent_time_hours):
                        continue
                    if remaining_seconds_value <= hours * 3600 and rule_key not in sent_rules:
                        due_rules.append(rule_key)
                        reasons.append(f"کمتر از {hours} ساعت تا پایان اعتبار سرویس باقی مانده است.")
                        hour_rule_added = True
                        break

                sent_time_days = _sent_thresholds(sent_rules, "time_", "d")
                for days in sorted(time_day_thresholds):
                    if hour_rule_added:
                        break
                    rule_key = f"time_{days}d"
                    if any(sent_hours <= days * 24 for sent_hours in sent_time_hours):
                        continue
                    if any(sent_days <= days for sent_days in sent_time_days):
                        continue
                    if remaining_seconds_value <= days * 86400 and rule_key not in sent_rules:
                        due_rules.append(rule_key)
                        reasons.append(f"کمتر از {days} روز تا پایان اعتبار سرویس باقی مانده است.")
                        break

        deletion_due_at = _as_utc(config.deletion_due_at)
        deletion_remaining_seconds: int | None = None
        if deletion_due_at and not config.panel_deleted_at and not ServiceReminderService._is_trial(purchase, config):
            deletion_remaining_seconds = int((deletion_due_at - datetime.now(timezone.utc)).total_seconds())
            if deletion_remaining_seconds > 0:
                deletion_rules = [
                    ("delete_2h", 2 * 3600, "2 ساعت تا حذف خودکار سرویس از پنل باقی مانده است."),
                    ("delete_1d", 86400, "1 روز تا حذف خودکار سرویس از پنل باقی مانده است."),
                    ("delete_2d", 2 * 86400, "2 روز تا حذف خودکار سرویس از پنل باقی مانده است."),
                    ("delete_3d", 3 * 86400, "مهلت تمدید شروع شد؛ 3 روز تا حذف خودکار سرویس از پنل باقی مانده است."),
                ]
                sent_delete_ranks = _sent_delete_ranks(sent_rules)
                for rule_key, threshold_seconds, reason in deletion_rules:
                    rank = DELETE_REMINDER_RANKS[rule_key]
                    if any(sent_rank <= rank for sent_rank in sent_delete_ranks):
                        continue
                    if deletion_remaining_seconds <= threshold_seconds and rule_key not in sent_rules:
                        due_rules.append(rule_key)
                        reasons.append(reason)
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
            "deletion_due_at": format_tehran_datetime(deletion_due_at) if deletion_due_at else "نامشخص",
            "deletion_remaining_time": _format_duration(deletion_remaining_seconds),
        }
        return due_rules, values

    @staticmethod
    def _renew_keyboard(purchase: Purchase, config: Config) -> InlineKeyboardMarkup | None:
        if ServiceReminderService._is_trial(purchase, config):
            return None
        if config.panel_deleted_at:
            return None
        if not config.shop_plan_id:
            return None
        return InlineKeyboardMarkup(
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

    @staticmethod
    def _metadata_finished(metadata: dict) -> bool:
        total = _to_int(metadata.get("total"))
        remaining = _to_int(metadata.get("remaining"))
        if total and total > 0 and remaining is not None and remaining <= 0:
            return True
        expire = _to_int(metadata.get("expire"))
        return bool(expire and expire <= int(datetime.now(timezone.utc).timestamp()))

    @staticmethod
    def _is_trial(purchase: Purchase, config: Config | None = None) -> bool:
        return (purchase.category_key or (config.category_key if config else None)) == "trial"

    @staticmethod
    def _trial_message(values: dict) -> str:
        return (
            "🔔 وضعیت سرویس تست\n\n"
            f"سرویس: {values.get('service_name', 'تست رایگان')}\n"
            f"{values.get('reason_lines') or '• وضعیت باقی‌مانده سرویس تست به‌روزرسانی شد.'}\n\n"
            f"حجم باقی‌مانده: {values.get('remaining_volume', 'نامشخص')}\n"
            f"درصد باقی‌مانده: {values.get('remaining_percent', 'نامشخص')}\n"
            f"تاریخ انقضا: {values.get('expiry_text', 'نامشخص')}\n"
            f"زمان باقی‌مانده: {values.get('remaining_time', 'نامشخص')}"
        )


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
        return format_tehran_datetime(expiry), "منقضی شده"
    days = remaining.days
    hours = remaining.seconds // 3600
    return format_tehran_timestamp(expire), f"{days} روز و {hours} ساعت"


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "نامشخص"
    if seconds <= 0:
        return "تمام شده"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    if days:
        return f"{days} روز و {hours} ساعت"
    if hours:
        return f"{hours} ساعت و {minutes} دقیقه"
    return f"{minutes} دقیقه"


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


DELETE_REMINDER_RANKS = {"delete_2h": 0, "delete_1d": 1, "delete_2d": 2, "delete_3d": 3}


def _sent_delete_ranks(sent_rules: set[str]) -> list[int]:
    return [DELETE_REMINDER_RANKS[rule] for rule in sent_rules if rule in DELETE_REMINDER_RANKS]


def _sent_thresholds(sent_rules: set[str], prefix: str, suffix: str) -> list[int]:
    thresholds: list[int] = []
    for rule in sent_rules:
        if not rule.startswith(prefix):
            continue
        value = rule[len(prefix):]
        if suffix:
            if not value.endswith(suffix):
                continue
            value = value[: -len(suffix)]
        try:
            thresholds.append(int(value))
        except ValueError:
            continue
    return thresholds
