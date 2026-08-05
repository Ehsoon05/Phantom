from __future__ import annotations

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
RIAL_REQUIRE_SOURCE_CARD = "rial_require_source_card"
RIAL_SUPPORT_HANDLE = "rial_support_handle"
RIAL_PAYMENT_MODE = "rial_payment_mode"
RIAL_DESTINATION_CARD_NUMBER = "rial_destination_card_number"
RIAL_DESTINATION_CARD_HOLDER = "rial_destination_card_holder"
RIAL_RECEIPT_VALID_MINUTES = "rial_receipt_valid_minutes"
RIAL_RECEIPT_BOT_USERNAME = "rial_receipt_bot_username"
RIAL_RECEIPT_ADMIN_IDS = "rial_receipt_admin_ids"
HOOSHPAY_ENABLED = "hooshpay_enabled"
HOOSHPAY_API_KEY = "hooshpay_api_key"
HOOSHPAY_API_SECRET = "hooshpay_api_secret"
HOOSHPAY_API_BASE_URL = "hooshpay_api_base_url"
HOOSHPAY_CALLBACK_BASE_URL = "hooshpay_callback_base_url"
HOOSHPAY_FEE_MODE = "hooshpay_fee_mode"
HOOSHPAY_MIN_AMOUNT = "hooshpay_min_amount"
HOOSHPAY_TITLE = "hooshpay_title"
HOOSHPAY_SUBTITLE = "hooshpay_subtitle"
HOOSHPAY_AMOUNT_LABEL = "hooshpay_amount_label"
HOOSHPAY_CREATE_BUTTON = "hooshpay_create_button"
HOOSHPAY_PAY_BUTTON = "hooshpay_pay_button"
HOOSHPAY_PRESET_AMOUNTS = "hooshpay_preset_amounts"
TRIAL_ENABLED = "trial_enabled"
TRIAL_VOLUME_MB = "trial_volume_mb"
TRIAL_DURATION_HOURS = "trial_duration_hours"
TRIAL_PANEL_KEY = "trial_panel_key"
TRIAL_TIME_MODE = "trial_time_mode"
TRIAL_PANEL_PHANTOM_TUNNEL_MIGRATION = "_migration_trial_panel_phantom_tunnel_v1"
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
    RIAL_REQUIRE_SOURCE_CARD: "true",
    RIAL_SUPPORT_HANDLE: "@PhantomHubsSupport",
    RIAL_PAYMENT_MODE: "receipt_bot",
    RIAL_DESTINATION_CARD_NUMBER: "",
    RIAL_DESTINATION_CARD_HOLDER: "",
    RIAL_RECEIPT_VALID_MINUTES: "120",
    RIAL_RECEIPT_BOT_USERNAME: "PhantomVariziBot",
    RIAL_RECEIPT_ADMIN_IDS: "60585628,6987529339",
    HOOSHPAY_ENABLED: "true",
    HOOSHPAY_API_KEY: "",
    HOOSHPAY_API_SECRET: "",
    HOOSHPAY_API_BASE_URL: "https://hooshpay.xyz",
    HOOSHPAY_CALLBACK_BASE_URL: "https://webapi.phantomhubs.shop",
    HOOSHPAY_FEE_MODE: "split",
    HOOSHPAY_MIN_AMOUNT: "100000",
    HOOSHPAY_TITLE: "درگاه هوش‌پی",
    HOOSHPAY_SUBTITLE: "پرداخت کارت‌به‌کارت آنی، بدون احراز و همراه با کارمزد. کارمزد فعلی به صورت split محاسبه می‌شود.",
    HOOSHPAY_AMOUNT_LABEL: "مبلغ شارژ کیف پول (تومان)",
    HOOSHPAY_CREATE_BUTTON: "ساخت لینک پرداخت هوش‌پی",
    HOOSHPAY_PAY_BUTTON: "پرداخت با هوش‌پی",
    HOOSHPAY_PRESET_AMOUNTS: "100000,200000,500000,1000000",
    TRIAL_ENABLED: "true",
    TRIAL_VOLUME_MB: "500",
    TRIAL_DURATION_HOURS: "24",
    TRIAL_PANEL_KEY: "phantom_tunnel",
    TRIAL_TIME_MODE: "date",
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
        await session.flush()

        # Move the existing installation to Phantom Tunnel once. The marker
        # makes later admin changes authoritative across future restarts.
        migration = (
            await session.execute(
                select(BotSetting).where(BotSetting.key == TRIAL_PANEL_PHANTOM_TUNNEL_MIGRATION)
            )
        ).scalar_one_or_none()
        if migration is None:
            trial_panel = (
                await session.execute(select(BotSetting).where(BotSetting.key == TRIAL_PANEL_KEY))
            ).scalar_one()
            trial_panel.value = "phantom_tunnel"
            trial_panel.updated_at = datetime.now(timezone.utc)
            session.add(BotSetting(key=TRIAL_PANEL_PHANTOM_TUNNEL_MIGRATION, value="done"))
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
    async def rial_source_card_required(session: AsyncSession) -> bool:
        value = await SettingsService.get(session, RIAL_REQUIRE_SOURCE_CARD, "true")
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    async def set_rial_source_card_required(session: AsyncSession, enabled: bool) -> None:
        await SettingsService.set(session, RIAL_REQUIRE_SOURCE_CARD, "true" if enabled else "false")

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
    async def get_rial_payment_mode(session: AsyncSession) -> str:
        value = (await SettingsService.get(session, RIAL_PAYMENT_MODE, "receipt_bot") or "").strip()
        return value if value in {"receipt_bot", "direct_support"} else "receipt_bot"

    @staticmethod
    async def set_rial_payment_mode(session: AsyncSession, mode: str) -> None:
        await SettingsService.set(session, RIAL_PAYMENT_MODE, "direct_support" if mode == "direct_support" else "receipt_bot")

    @staticmethod
    async def get_rial_destination_card_number(session: AsyncSession) -> str:
        return (await SettingsService.get(session, RIAL_DESTINATION_CARD_NUMBER, "") or "").strip()

    @staticmethod
    async def set_rial_destination_card_number(session: AsyncSession, card_number: str) -> None:
        cleaned = "".join(ch for ch in card_number if ch.isdigit())
        if len(cleaned) != 16:
            return
        await SettingsService.set(session, RIAL_DESTINATION_CARD_NUMBER, cleaned)

    @staticmethod
    async def get_rial_destination_card_holder(session: AsyncSession) -> str:
        return (await SettingsService.get(session, RIAL_DESTINATION_CARD_HOLDER, "") or "").strip()

    @staticmethod
    async def set_rial_destination_card_holder(session: AsyncSession, holder: str) -> None:
        await SettingsService.set(session, RIAL_DESTINATION_CARD_HOLDER, holder.strip())

    @staticmethod
    async def get_rial_receipt_valid_minutes(session: AsyncSession) -> int:
        try:
            return max(1, int(await SettingsService.get(session, RIAL_RECEIPT_VALID_MINUTES, "120") or 120))
        except (TypeError, ValueError):
            return 120

    @staticmethod
    async def set_rial_receipt_valid_minutes(session: AsyncSession, minutes: int) -> None:
        await SettingsService.set(session, RIAL_RECEIPT_VALID_MINUTES, str(max(1, int(minutes))))

    @staticmethod
    async def get_rial_receipt_bot_username(session: AsyncSession) -> str:
        value = (await SettingsService.get(session, RIAL_RECEIPT_BOT_USERNAME, "PhantomVariziBot") or "").strip().lstrip("@")
        return value or "PhantomVariziBot"

    @staticmethod
    async def set_rial_receipt_bot_username(session: AsyncSession, username: str) -> None:
        await SettingsService.set(session, RIAL_RECEIPT_BOT_USERNAME, username.strip().lstrip("@"))

    @staticmethod
    async def get_rial_receipt_admin_ids(session: AsyncSession) -> list[int]:
        raw = await SettingsService.get(session, RIAL_RECEIPT_ADMIN_IDS, "60585628,6987529339")
        ids: list[int] = []
        for part in (raw or "").split(","):
            try:
                value = int(part.strip())
            except ValueError:
                continue
            if value > 0 and value not in ids:
                ids.append(value)
        return ids

    @staticmethod
    async def set_rial_receipt_admin_ids(session: AsyncSession, admin_ids: list[int]) -> None:
        cleaned = []
        for value in admin_ids:
            value = int(value)
            if value > 0 and value not in cleaned:
                cleaned.append(value)
        await SettingsService.set(session, RIAL_RECEIPT_ADMIN_IDS, ",".join(str(value) for value in cleaned))

    @staticmethod
    async def hooshpay_enabled(session: AsyncSession) -> bool:
        value = await SettingsService.get(session, HOOSHPAY_ENABLED, "true")
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    async def set_hooshpay_enabled(session: AsyncSession, enabled: bool) -> None:
        await SettingsService.set(session, HOOSHPAY_ENABLED, "true" if enabled else "false")

    @staticmethod
    async def get_hooshpay_api_key(session: AsyncSession) -> str:
        from ..config_loader import BotConfig

        return (await SettingsService.get(session, HOOSHPAY_API_KEY, "") or BotConfig.HOOSHPAY_API_KEY).strip()

    @staticmethod
    async def set_hooshpay_api_key(session: AsyncSession, value: str) -> None:
        await SettingsService.set(session, HOOSHPAY_API_KEY, value.strip())

    @staticmethod
    async def get_hooshpay_api_secret(session: AsyncSession) -> str:
        from ..config_loader import BotConfig

        return (await SettingsService.get(session, HOOSHPAY_API_SECRET, "") or BotConfig.HOOSHPAY_API_SECRET).strip()

    @staticmethod
    async def set_hooshpay_api_secret(session: AsyncSession, value: str) -> None:
        await SettingsService.set(session, HOOSHPAY_API_SECRET, value.strip())

    @staticmethod
    async def get_hooshpay_api_base_url(session: AsyncSession) -> str:
        from ..config_loader import BotConfig

        value = (await SettingsService.get(session, HOOSHPAY_API_BASE_URL, "") or BotConfig.HOOSHPAY_API_BASE_URL).strip()
        return (value or "https://hooshpay.xyz").rstrip("/")

    @staticmethod
    async def set_hooshpay_api_base_url(session: AsyncSession, value: str) -> None:
        await SettingsService.set(session, HOOSHPAY_API_BASE_URL, value.strip().rstrip("/"))

    @staticmethod
    async def get_hooshpay_callback_base_url(session: AsyncSession) -> str:
        from ..config_loader import BotConfig

        value = (await SettingsService.get(session, HOOSHPAY_CALLBACK_BASE_URL, "") or BotConfig.HOOSHPAY_CALLBACK_BASE_URL).strip()
        return (value or "https://webapi.phantomhubs.shop").rstrip("/")

    @staticmethod
    async def set_hooshpay_callback_base_url(session: AsyncSession, value: str) -> None:
        await SettingsService.set(session, HOOSHPAY_CALLBACK_BASE_URL, value.strip().rstrip("/"))

    @staticmethod
    async def get_hooshpay_fee_mode(session: AsyncSession) -> str:
        value = (await SettingsService.get(session, HOOSHPAY_FEE_MODE, "split") or "split").strip()
        return value if value in {"seller", "buyer", "split"} else "split"

    @staticmethod
    async def set_hooshpay_fee_mode(session: AsyncSession, value: str) -> None:
        await SettingsService.set(session, HOOSHPAY_FEE_MODE, value if value in {"seller", "buyer", "split"} else "split")

    @staticmethod
    async def get_hooshpay_min_amount(session: AsyncSession) -> int:
        try:
            return max(1000, int(await SettingsService.get(session, HOOSHPAY_MIN_AMOUNT, "100000") or 100000))
        except (TypeError, ValueError):
            return 100000

    @staticmethod
    async def set_hooshpay_min_amount(session: AsyncSession, amount: int) -> None:
        await SettingsService.set(session, HOOSHPAY_MIN_AMOUNT, str(max(1000, int(amount))))

    @staticmethod
    async def get_hooshpay_title(session: AsyncSession) -> str:
        return (await SettingsService.get(session, HOOSHPAY_TITLE, "درگاه هوش‌پی") or "درگاه هوش‌پی").strip()

    @staticmethod
    async def set_hooshpay_title(session: AsyncSession, value: str) -> None:
        await SettingsService.set(session, HOOSHPAY_TITLE, value.strip() or "درگاه هوش‌پی")

    @staticmethod
    async def get_hooshpay_subtitle(session: AsyncSession) -> str:
        default = DEFAULTS[HOOSHPAY_SUBTITLE]
        return (await SettingsService.get(session, HOOSHPAY_SUBTITLE, default) or default).strip()

    @staticmethod
    async def set_hooshpay_subtitle(session: AsyncSession, value: str) -> None:
        await SettingsService.set(session, HOOSHPAY_SUBTITLE, value.strip())

    @staticmethod
    async def get_hooshpay_amount_label(session: AsyncSession) -> str:
        default = DEFAULTS[HOOSHPAY_AMOUNT_LABEL]
        return (await SettingsService.get(session, HOOSHPAY_AMOUNT_LABEL, default) or default).strip()

    @staticmethod
    async def set_hooshpay_amount_label(session: AsyncSession, value: str) -> None:
        await SettingsService.set(session, HOOSHPAY_AMOUNT_LABEL, value.strip() or DEFAULTS[HOOSHPAY_AMOUNT_LABEL])

    @staticmethod
    async def get_hooshpay_create_button(session: AsyncSession) -> str:
        default = DEFAULTS[HOOSHPAY_CREATE_BUTTON]
        return (await SettingsService.get(session, HOOSHPAY_CREATE_BUTTON, default) or default).strip()

    @staticmethod
    async def set_hooshpay_create_button(session: AsyncSession, value: str) -> None:
        await SettingsService.set(session, HOOSHPAY_CREATE_BUTTON, value.strip() or DEFAULTS[HOOSHPAY_CREATE_BUTTON])

    @staticmethod
    async def get_hooshpay_pay_button(session: AsyncSession) -> str:
        default = DEFAULTS[HOOSHPAY_PAY_BUTTON]
        return (await SettingsService.get(session, HOOSHPAY_PAY_BUTTON, default) or default).strip()

    @staticmethod
    async def set_hooshpay_pay_button(session: AsyncSession, value: str) -> None:
        await SettingsService.set(session, HOOSHPAY_PAY_BUTTON, value.strip() or DEFAULTS[HOOSHPAY_PAY_BUTTON])

    @staticmethod
    async def get_hooshpay_preset_amounts(session: AsyncSession) -> list[int]:
        raw = await SettingsService.get(session, HOOSHPAY_PRESET_AMOUNTS, DEFAULTS[HOOSHPAY_PRESET_AMOUNTS])
        values: list[int] = []
        for part in str(raw or "").replace("،", ",").split(","):
            try:
                amount = int(part.strip())
            except ValueError:
                continue
            if amount > 0 and amount not in values:
                values.append(amount)
        return values

    @staticmethod
    async def set_hooshpay_preset_amounts(session: AsyncSession, values: list[int]) -> None:
        cleaned = []
        for value in values:
            amount = int(value)
            if amount > 0 and amount not in cleaned:
                cleaned.append(amount)
        await SettingsService.set(session, HOOSHPAY_PRESET_AMOUNTS, ",".join(str(value) for value in cleaned))

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
    async def get_trial_panel_key(session: AsyncSession) -> str:
        panel_key = str(
            await SettingsService.get(session, TRIAL_PANEL_KEY, "phantom_tunnel") or "phantom_tunnel"
        ).strip()
        return "easy" if panel_key == "asan" else panel_key

    @staticmethod
    async def set_trial_panel_key(session: AsyncSession, panel_key: str) -> None:
        await SettingsService.set(session, TRIAL_PANEL_KEY, str(panel_key or "").strip())

    @staticmethod
    async def get_trial_time_mode(session: AsyncSession) -> str:
        mode = str(await SettingsService.get(session, TRIAL_TIME_MODE, "date") or "date").strip()
        return mode if mode in {"date", "on_hold", "unlimited"} else "date"

    @staticmethod
    async def set_trial_time_mode(session: AsyncSession, mode: str) -> None:
        mode = str(mode or "date").strip()
        if mode not in {"date", "on_hold", "unlimited"}:
            mode = "date"
        await SettingsService.set(session, TRIAL_TIME_MODE, mode)

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
