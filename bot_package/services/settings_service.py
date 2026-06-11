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
RIAL_MIN_AMOUNT = "rial_min_amount"
RIAL_REQUIRE_PHONE = "rial_require_phone"
RIAL_SUPPORT_HANDLE = "rial_support_handle"
TRIAL_ENABLED = "trial_enabled"
TRIAL_VOLUME_MB = "trial_volume_mb"
TRIAL_DURATION_HOURS = "trial_duration_hours"

DEFAULTS = {
    RATE_MODE: "online",
    RATE_MARGIN: "2.5",
    MANUAL_RATE_USDT: "0",
    MANUAL_RATE_TON: "0",
    BRANDED_SUBSCRIPTION_LINKS: "true",
    RIAL_MIN_AMOUNT: "100000",
    RIAL_REQUIRE_PHONE: "true",
    RIAL_SUPPORT_HANDLE: "@PhantomHubsSupport",
    TRIAL_ENABLED: "true",
    TRIAL_VOLUME_MB: "500",
    TRIAL_DURATION_HOURS: "24",
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
