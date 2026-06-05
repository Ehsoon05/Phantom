import os

from dotenv import load_dotenv

load_dotenv()


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


class BotConfig:
    MAIN_BOT_TOKEN = os.getenv("MAIN_BOT_TOKEN", "").strip()
    ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "").strip()
    ADMIN_USER_IDS = _parse_admin_user_ids()
    ADMIN_USER_ID = ADMIN_USER_IDS[0] if ADMIN_USER_IDS else 0
    OWNER_USER_IDS = _parse_owner_user_ids()
    OWNER_USER_ID = OWNER_USER_IDS[0] if OWNER_USER_IDS else 0
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()
    DB_URL = os.getenv("DB_URL", "sqlite+aiosqlite:///vpn_shop.db").strip()
    SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/YourSupport").strip()
    SUPPORT_HANDLE = os.getenv("SUPPORT_HANDLE", "@YourSupport").strip()
    CHANNEL_HANDLE = os.getenv("CHANNEL_HANDLE", "@YourChannel").strip()
    SUBSCRIPTION_PUBLIC_BASE_URL = os.getenv("SUBSCRIPTION_PUBLIC_BASE_URL", "https://api.phantomhubs.shop").strip().rstrip("/")
    SESSION_TIMEOUT_MINUTES = _parse_int_env("SESSION_TIMEOUT_MINUTES", 60)
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()

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
