from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import BotSetting

# Setting keys
RATE_MODE = "crypto_rate_mode"            # "online" | "manual"
RATE_MARGIN = "crypto_margin_percent"     # float string, e.g. "2.5"
MANUAL_RATE_USDT = "crypto_manual_rate_usdt"  # toman per 1 USDT
MANUAL_RATE_TON = "crypto_manual_rate_ton"    # toman per 1 TON
BRANDED_SUBSCRIPTION_LINKS = "branded_subscription_links_enabled"
SUBSCRIPTION_PROFILE_TITLE = "subscription_profile_title"
SUBSCRIPTION_DEVICE_LIMIT = "subscription_device_limit"
RIAL_MIN_AMOUNT = "rial_min_amount"
RIAL_REQUIRE_PHONE = "rial_require_phone"
RIAL_SUPPORT_HANDLE = "rial_support_handle"
TRIAL_ENABLED = "trial_enabled"
TRIAL_VOLUME_MB = "trial_volume_mb"
TRIAL_DURATION_HOURS = "trial_duration_hours"
SERVICE_REMINDERS_ENABLED = "service_reminders_enabled"
SERVICE_REMINDER_VOLUME_PERCENTS = "service_reminder_volume_percents"
SERVICE_REMINDER_TIME_DAYS = "service_reminder_time_days"
SERVICE_REMINDER_TIME_HOURS = "service_reminder_time_hours"
SERVICE_REMINDER_JOB_INTERVAL_SECONDS = "service_reminder_job_interval_seconds"
REFERRAL_COMMISSION_ENABLED = "referral_commission_enabled"
REFERRAL_COMMISSION_PERCENT = "referral_commission_percent"

DEFAULTS = {
    RATE_MODE: "online",
    RATE_MARGIN: "2.5",
    MANUAL_RATE_USDT: "0",
    MANUAL_RATE_TON: "0",
    BRANDED_SUBSCRIPTION_LINKS: "true",
    SUBSCRIPTION_PROFILE_TITLE: "",
    SUBSCRIPTION_DEVICE_LIMIT: "0",
    RIAL_MIN_AMOUNT: "100000",
    RIAL_REQUIRE_PHONE: "true",
    RIAL_SUPPORT_HANDLE: "@PhantomHubsSupport",
    TRIAL_ENABLED: "true",
    TRIAL_VOLUME_MB: "500",
    TRIAL_DURATION_HOURS: "24",
    SERVICE_REMINDERS_ENABLED: "true",
    SERVICE_REMINDER_VOLUME_PERCENTS: "20,10",
    SERVICE_REMINDER_TIME_DAYS: "3,1",
    SERVICE_REMINDER_TIME_HOURS: "2,1",
    SERVICE_REMINDER_JOB_INTERVAL_SECONDS: "3600",
    REFERRAL_COMMISSION_ENABLED: "true",
    REFERRAL_COMMISSION_PERCENT: "15",
}


class SettingsService:
    @staticmethod
    async def init_defaults(session: AsyncSession) -> None:
        for key, value in DEFAULTS.items():
            stmt = select(BotSetting).where(BotSetting.key == key)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing is None:
                session.add(BotSetting(key=key, value=value))
        await session.commit()

    @staticmethod
    async def get(session: AsyncSession, key: str, default: Optional[str] = None) -> Optional[str]:
        stmt = select(BotSetting).where(BotSetting.key == key)
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is not None and row.value is not None:
            return row.value
        return default if default is not None else DEFAULTS.get(key)

    @staticmethod
    async def set(session: AsyncSession, key: str, value: str) -> None:
        stmt = select(BotSetting).where(BotSetting.key == key)
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            session.add(BotSetting(key=key, value=value))
        else:
            row.value = value
            row.updated_at = datetime.now(timezone.utc)
        await session.commit()

    # --- Typed crypto-rate helpers -------------------------------------------------

    @staticmethod
    async def get_rate_mode(session: AsyncSession) -> str:
        mode = await SettingsService.get(session, RATE_MODE)
        return mode if mode in {"online", "manual"} else "online"

    @staticmethod
    async def set_rate_mode(session: AsyncSession, mode: str) -> None:
        await SettingsService.set(session, RATE_MODE, "manual" if mode == "manual" else "online")

    @staticmethod
    async def get_margin(session: AsyncSession) -> float:
        try:
            return float(await SettingsService.get(session, RATE_MARGIN) or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    async def set_margin(session: AsyncSession, percent: float) -> None:
        await SettingsService.set(session, RATE_MARGIN, str(percent))

    @staticmethod
    async def get_manual_rate(session: AsyncSession, coin: str) -> int:
        key = MANUAL_RATE_TON if coin.upper() == "TON" else MANUAL_RATE_USDT
        try:
            return int(float(await SettingsService.get(session, key) or 0))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    async def set_manual_rate(session: AsyncSession, coin: str, toman_per_unit: int) -> None:
        key = MANUAL_RATE_TON if coin.upper() == "TON" else MANUAL_RATE_USDT
        await SettingsService.set(session, key, str(int(toman_per_unit)))

    @staticmethod
    async def branded_links_enabled(session: AsyncSession) -> bool:
        value = await SettingsService.get(session, BRANDED_SUBSCRIPTION_LINKS, "true")
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    async def set_branded_links_enabled(session: AsyncSession, enabled: bool) -> None:
        await SettingsService.set(session, BRANDED_SUBSCRIPTION_LINKS, "true" if enabled else "false")

    @staticmethod
    async def get_subscription_profile_title(session: AsyncSession) -> str:
        return (await SettingsService.get(session, SUBSCRIPTION_PROFILE_TITLE, "") or "").strip()

    @staticmethod
    async def set_subscription_profile_title(session: AsyncSession, title: str) -> None:
        await SettingsService.set(session, SUBSCRIPTION_PROFILE_TITLE, title.strip())

    @staticmethod
    async def get_subscription_device_limit(session: AsyncSession) -> int:
        try:
            return max(0, int(await SettingsService.get(session, SUBSCRIPTION_DEVICE_LIMIT, "0") or 0))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    async def set_subscription_device_limit(session: AsyncSession, limit: int) -> None:
        await SettingsService.set(session, SUBSCRIPTION_DEVICE_LIMIT, str(max(0, int(limit))))

    @staticmethod
    async def get_rial_min_amount(session: AsyncSession) -> int:
        try:
            return max(1, int(await SettingsService.get(session, RIAL_MIN_AMOUNT) or 100000))
        except (TypeError, ValueError):
            return 100000

    @staticmethod
    async def set_rial_min_amount(session: AsyncSession, amount: int) -> None:
        await SettingsService.set(session, RIAL_MIN_AMOUNT, str(max(1, int(amount))))

    @staticmethod
    async def rial_phone_required(session: AsyncSession) -> bool:
        value = await SettingsService.get(session, RIAL_REQUIRE_PHONE, "true")
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    async def set_rial_phone_required(session: AsyncSession, enabled: bool) -> None:
        await SettingsService.set(session, RIAL_REQUIRE_PHONE, "true" if enabled else "false")

    @staticmethod
    async def get_rial_support_handle(session: AsyncSession) -> str:
        value = (await SettingsService.get(session, RIAL_SUPPORT_HANDLE, "@PhantomHubsSupport") or "").strip()
        if not value:
            return "@PhantomHubsSupport"
        return value if value.startswith("@") else f"@{value}"

    @staticmethod
    async def set_rial_support_handle(session: AsyncSession, handle: str) -> None:
        value = handle.strip().lstrip("@")
        await SettingsService.set(session, RIAL_SUPPORT_HANDLE, f"@{value}")

    @staticmethod
    async def trial_enabled(session: AsyncSession) -> bool:
        value = await SettingsService.get(session, TRIAL_ENABLED, "true")
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    async def referral_commission_enabled(session: AsyncSession) -> bool:
        value = await SettingsService.get(session, REFERRAL_COMMISSION_ENABLED, "true")
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    async def set_referral_commission_enabled(session: AsyncSession, enabled: bool) -> None:
        await SettingsService.set(session, REFERRAL_COMMISSION_ENABLED, "true" if enabled else "false")

    @staticmethod
    async def get_referral_commission_percent(session: AsyncSession) -> int:
        try:
            return max(0, min(100, int(await SettingsService.get(session, REFERRAL_COMMISSION_PERCENT, "15") or 15)))
        except (TypeError, ValueError):
            return 15

    @staticmethod
    async def set_referral_commission_percent(session: AsyncSession, percent: int) -> None:
        await SettingsService.set(session, REFERRAL_COMMISSION_PERCENT, str(max(0, min(100, int(percent)))))

    @staticmethod
    async def set_trial_enabled(session: AsyncSession, enabled: bool) -> None:
        await SettingsService.set(session, TRIAL_ENABLED, "true" if enabled else "false")

    @staticmethod
    async def get_trial_volume_mb(session: AsyncSession) -> int:
        try:
            return max(1, int(await SettingsService.get(session, TRIAL_VOLUME_MB) or 500))
        except (TypeError, ValueError):
            return 500

    @staticmethod
    async def set_trial_volume_mb(session: AsyncSession, volume_mb: int) -> None:
        await SettingsService.set(session, TRIAL_VOLUME_MB, str(max(1, int(volume_mb))))

    @staticmethod
    async def get_trial_duration_hours(session: AsyncSession) -> int:
        try:
            return max(1, int(await SettingsService.get(session, TRIAL_DURATION_HOURS) or 24))
        except (TypeError, ValueError):
            return 24

    @staticmethod
    async def set_trial_duration_hours(session: AsyncSession, hours: int) -> None:
        await SettingsService.set(session, TRIAL_DURATION_HOURS, str(max(1, int(hours))))

    @staticmethod
    async def service_reminders_enabled(session: AsyncSession) -> bool:
        value = await SettingsService.get(session, SERVICE_REMINDERS_ENABLED, "true")
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    async def set_service_reminders_enabled(session: AsyncSession, enabled: bool) -> None:
        await SettingsService.set(session, SERVICE_REMINDERS_ENABLED, "true" if enabled else "false")

    @staticmethod
    async def get_service_reminder_volume_percents(session: AsyncSession) -> list[int]:
        return _parse_int_list(await SettingsService.get(session, SERVICE_REMINDER_VOLUME_PERCENTS, "20,10"), minimum=1)

    @staticmethod
    async def set_service_reminder_volume_percents(session: AsyncSession, values: list[int]) -> None:
        cleaned = sorted({max(1, min(100, int(value))) for value in values}, reverse=True)
        await SettingsService.set(session, SERVICE_REMINDER_VOLUME_PERCENTS, ",".join(str(value) for value in cleaned))

    @staticmethod
    async def get_service_reminder_time_days(session: AsyncSession) -> list[int]:
        return _parse_int_list(await SettingsService.get(session, SERVICE_REMINDER_TIME_DAYS, "3,1"), minimum=1)

    @staticmethod
    async def set_service_reminder_time_days(session: AsyncSession, values: list[int]) -> None:
        cleaned = sorted({max(1, int(value)) for value in values}, reverse=True)
        await SettingsService.set(session, SERVICE_REMINDER_TIME_DAYS, ",".join(str(value) for value in cleaned))

    @staticmethod
    async def get_service_reminder_time_hours(session: AsyncSession) -> list[int]:
        return _parse_int_list(await SettingsService.get(session, SERVICE_REMINDER_TIME_HOURS, "2,1"), minimum=1)

    @staticmethod
    async def set_service_reminder_time_hours(session: AsyncSession, values: list[int]) -> None:
        cleaned = sorted({max(1, int(value)) for value in values}, reverse=True)
        await SettingsService.set(session, SERVICE_REMINDER_TIME_HOURS, ",".join(str(value) for value in cleaned))

    @staticmethod
    async def get_service_reminder_interval_seconds(session: AsyncSession) -> int:
        try:
            return max(300, int(await SettingsService.get(session, SERVICE_REMINDER_JOB_INTERVAL_SECONDS) or 3600))
        except (TypeError, ValueError):
            return 3600


def _parse_int_list(value: str | None, *, minimum: int) -> list[int]:
    result: list[int] = []
    for part in str(value or "").replace("،", ",").split(","):
        try:
            item = int(part.strip())
        except ValueError:
            continue
        if item >= minimum:
            result.append(item)
    return sorted(set(result), reverse=True)
