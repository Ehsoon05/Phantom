import os

from dotenv import load_dotenv

if os.environ.get("_PHANTOM_DOTENV_LOADED") != "1":
    load_dotenv()
    os.environ["_PHANTOM_DOTENV_LOADED"] = "1"


def _parse_int(value: str) -> int:
    try:
        return int(value.strip())
    except ValueError:
        return 0


def _parse_admin_user_ids() -> tuple[int, ...]:
    raw_values = []
    legacy_admin_id = os.getenv("ADMIN_USER_ID", "").strip()
    admin_ids = os.getenv("ADMIN_USER_IDS", "").strip()
    if legacy_admin_id:
        raw_values.append(legacy_admin_id)
    if admin_ids:
        raw_values.extend(part.strip() for part in admin_ids.split(","))

    seen = set()
    parsed_ids = []
    for raw_value in raw_values:
        admin_id = _parse_int(raw_value)
        if admin_id > 0 and admin_id not in seen:
            seen.add(admin_id)
            parsed_ids.append(admin_id)
    return tuple(parsed_ids)


def _parse_owner_user_ids() -> tuple[int, ...]:
    raw_owner_ids = os.getenv("OWNER_USER_IDS", "").strip()
    if raw_owner_ids:
        raw_values = [part.strip() for part in raw_owner_ids.split(",")]
    else:
        raw_values = [
            os.getenv("OWNER_USER_ID", "").strip(),
            os.getenv("ADMIN_USER_ID", "").strip(),
            os.getenv("ADMIN_USER_IDS", "").split(",")[0].strip(),
        ]

    seen = set()
    parsed_ids = []
    for raw_value in raw_values:
        owner_id = _parse_int(raw_value)
        if owner_id > 0 and owner_id not in seen:
            seen.add(owner_id)
            parsed_ids.append(owner_id)
    return tuple(parsed_ids)


def _parse_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        return int(raw_value)
    except ValueError:
        return default


def _parse_bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name, "").strip().lower()
    if raw_value in {"1", "true", "yes", "on"}:
        return True
    if raw_value in {"0", "false", "no", "off"}:
        return False
    return default


class BotConfig:
    MAIN_BOT_TOKEN = os.getenv("MAIN_BOT_TOKEN", "").strip()
    MAIN_BOT_USERNAME = os.getenv("MAIN_BOT_USERNAME", "PhantomHubs_bot").strip().lstrip("@")
    ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "").strip()
    RIAL_RECEIPT_BOT_TOKEN = os.getenv("RIAL_RECEIPT_BOT_TOKEN", "").strip()
    ADMIN_USER_IDS = _parse_admin_user_ids()
    ADMIN_USER_ID = ADMIN_USER_IDS[0] if ADMIN_USER_IDS else 0
    OWNER_USER_IDS = _parse_owner_user_ids()
    OWNER_USER_ID = OWNER_USER_IDS[0] if OWNER_USER_IDS else 0
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()
    DB_URL = os.getenv("DB_URL", "sqlite+aiosqlite:///vpn_shop.db").strip()
    SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/YourSupport").strip()
    SUPPORT_HANDLE = os.getenv("SUPPORT_HANDLE", "@YourSupport").strip()
    CHANNEL_HANDLE = os.getenv("CHANNEL_HANDLE", "@YourChannel").strip()
    WEBAPP_URL = os.getenv("WEBAPP_URL", "https://app.phantomhubs.shop").strip().rstrip("/")
    SUBSCRIPTION_PUBLIC_BASE_URL = os.getenv("SUBSCRIPTION_PUBLIC_BASE_URL", "https://api.phantomhubs.shop").strip().rstrip("/")
    SUBSCRIPTION_PANEL_SYNC_URL = os.getenv("SUBSCRIPTION_PANEL_SYNC_URL", "").strip().rstrip("/")
    SUBSCRIPTION_PANEL_SYNC_TOKEN = os.getenv("SUBSCRIPTION_PANEL_SYNC_TOKEN", "").strip()
    HOOSHPAY_API_KEY = os.getenv("HOOSHPAY_API_KEY", "").strip()
    HOOSHPAY_API_SECRET = os.getenv("HOOSHPAY_API_SECRET", "").strip()
    HOOSHPAY_API_BASE_URL = os.getenv("HOOSHPAY_API_BASE_URL", "https://hooshpay.xyz").strip().rstrip("/")
    HOOSHPAY_CALLBACK_BASE_URL = os.getenv("HOOSHPAY_CALLBACK_BASE_URL", "https://webapi.phantomhubs.shop").strip().rstrip("/")
    MARZBAN_API_URL = os.getenv("MARZBAN_API_URL", "").strip().rstrip("/")
    MARZBAN_API_USERNAME = os.getenv("MARZBAN_API_USERNAME", "").strip()
    MARZBAN_API_PASSWORD = os.getenv("MARZBAN_API_PASSWORD", "").strip()
    ALIEN_PANEL_URL = os.getenv("ALIEN_PANEL_URL", "").strip().rstrip("/")
    ALIEN_PANEL_USERNAME = os.getenv("ALIEN_PANEL_USERNAME", "").strip()
    ALIEN_PANEL_PASSWORD = os.getenv("ALIEN_PANEL_PASSWORD", "").strip()
    EASY_PANEL_URL = os.getenv("EASY_PANEL_URL", "").strip().rstrip("/")
    EASY_PANEL_USERNAME = os.getenv("EASY_PANEL_USERNAME", "").strip()
    EASY_PANEL_PASSWORD = os.getenv("EASY_PANEL_PASSWORD", "").strip()
    MEXICO_HAJMI_PANEL_URL = os.getenv("MEXICO_HAJMI_PANEL_URL", "").strip().rstrip("/")
    MEXICO_HAJMI_PANEL_USERNAME = os.getenv("MEXICO_HAJMI_PANEL_USERNAME", "").strip()
    MEXICO_HAJMI_PANEL_PASSWORD = os.getenv("MEXICO_HAJMI_PANEL_PASSWORD", "").strip()
    MEXICO_HAJMI_PANEL_HWID_LIMIT = _parse_int_env("MEXICO_HAJMI_PANEL_HWID_LIMIT", 2)
    MEXICO_NAMAHDOD_PANEL_URL = os.getenv("MEXICO_NAMAHDOD_PANEL_URL", "").strip().rstrip("/")
    MEXICO_NAMAHDOD_PANEL_USERNAME = os.getenv("MEXICO_NAMAHDOD_PANEL_USERNAME", "").strip()
    MEXICO_NAMAHDOD_PANEL_PASSWORD = os.getenv("MEXICO_NAMAHDOD_PANEL_PASSWORD", "").strip()
    MEXICO_NAMAHDOD_PANEL_HWID_LIMIT = _parse_int_env("MEXICO_NAMAHDOD_PANEL_HWID_LIMIT", 2)
    SESSION_TIMEOUT_MINUTES = _parse_int_env("SESSION_TIMEOUT_MINUTES", 60)
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()

    # --- Crypto top-ups (self-hosted, watch-only) --------------------------------
    CRYPTO_ENABLED = _parse_bool_env("CRYPTO_ENABLED", False)
    # Tron (TRC-20 USDT): account-level extended PUBLIC key for watch-only address
    # derivation. The private seed must never live on the server.
    TRON_XPUB = os.getenv("TRON_XPUB", "").strip()
    TRON_API_KEY = os.getenv("TRON_API_KEY", "").strip()  # optional TronGrid key
    TRON_USDT_CONTRACT = os.getenv(
        "TRON_USDT_CONTRACT", "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    ).strip()
    # TON: single receiving address; per-invoice memo identifies the payer.
    TON_DEPOSIT_ADDRESS = os.getenv("TON_DEPOSIT_ADDRESS", "").strip()
    TON_API_KEY = os.getenv("TON_API_KEY", "").strip()    # optional Toncenter key
    # USDT jetton master on TON (for USDT-on-TON deposits); empty disables it.
    TON_USDT_JETTON_MASTER = os.getenv("TON_USDT_JETTON_MASTER", "").strip()

    CRYPTO_INVOICE_TTL_MINUTES = _parse_int_env("CRYPTO_INVOICE_TTL_MINUTES", 20)
    CRYPTO_MIN_CONFIRMATIONS = _parse_int_env("CRYPTO_MIN_CONFIRMATIONS", 1)
    CRYPTO_POLL_SECONDS = _parse_int_env("CRYPTO_POLL_SECONDS", 30)
    CRYPTO_RATE_REFRESH_SECONDS = _parse_int_env("CRYPTO_RATE_REFRESH_SECONDS", 600)
    # Tolerance band (%) for treating a payment as fully matching the invoice.
    CRYPTO_UNDERPAY_TOLERANCE = _parse_int_env("CRYPTO_UNDERPAY_TOLERANCE", 2)

    # --- USDC on BNB Smart Chain (BEP-20), watch-only EVM xpub -------------------
    # Account-level EVM extended PUBLIC key (BIP44 coin type 60). Seed stays offline.
    BSC_XPUB = os.getenv("BSC_XPUB", "").strip()
    BSCSCAN_API_KEY = os.getenv("BSCSCAN_API_KEY", "").strip()  # recommended for prod
    BSC_USDC_CONTRACT = os.getenv(
        "BSC_USDC_CONTRACT", "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d"
    ).strip()
    BSC_USDC_DECIMALS = _parse_int_env("BSC_USDC_DECIMALS", 18)

    TON_USDT_DECIMALS = _parse_int_env("TON_USDT_DECIMALS", 6)

    @classmethod
    def validate(cls) -> None:
        errors = []
        if not cls.MAIN_BOT_TOKEN:
            errors.append("MAIN_BOT_TOKEN is required")
        if not cls.ADMIN_BOT_TOKEN:
            errors.append("ADMIN_BOT_TOKEN is required")
        if not cls.OWNER_USER_IDS:
            errors.append("OWNER_USER_ID, OWNER_USER_IDS, or ADMIN_USER_ID must contain at least one owner Telegram user ID")
        if not cls.ADMIN_PASSWORD:
            errors.append("ADMIN_PASSWORD is required")
        if cls.ADMIN_PASSWORD == "admin123":
            errors.append("ADMIN_PASSWORD must not use the unsafe default 'admin123'")
        if not cls.DB_URL:
            errors.append("DB_URL is required")
        if not cls.SUPPORT_URL.startswith(("https://t.me/", "http://", "https://")):
            errors.append("SUPPORT_URL must be a valid URL")
        if not cls.WEBAPP_URL.startswith("https://"):
            errors.append("WEBAPP_URL must be a valid HTTPS URL")
        if cls.SESSION_TIMEOUT_MINUTES <= 0:
            errors.append("SESSION_TIMEOUT_MINUTES must be positive")
        if cls.LOG_LEVEL not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            errors.append("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
        if errors:
            raise RuntimeError("Invalid bot configuration: " + "; ".join(errors))

    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        return user_id in cls.ADMIN_USER_IDS or user_id in cls.OWNER_USER_IDS

    @classmethod
    def is_owner(cls, user_id: int) -> bool:
        return user_id in cls.OWNER_USER_IDS
