import os

from bot_package.config_loader import BotConfig  # noqa: F401  (re-export; also triggers .env load)


class ApiConfig:
    JWT_SECRET = os.getenv("API_JWT_SECRET", "").strip()
    JWT_ALGORITHM = "HS256"
    USER_TOKEN_TTL_HOURS = int(os.getenv("API_USER_TOKEN_TTL_HOURS", "24") or 24)
    ADMIN_TOKEN_TTL_MINUTES = int(os.getenv("API_ADMIN_TOKEN_TTL_MINUTES", "60") or 60)
    # Comma-separated list of allowed frontend origins.
    CORS_ORIGINS = tuple(
        origin.strip()
        for origin in os.getenv("API_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
        if origin.strip()
    )
    # initData older than this is rejected (replay protection).
    INIT_DATA_MAX_AGE_SECONDS = int(os.getenv("API_INIT_DATA_MAX_AGE_SECONDS", "3600") or 3600)

    @classmethod
    def validate(cls) -> None:
        errors = []
        if not cls.JWT_SECRET or len(cls.JWT_SECRET) < 32:
            errors.append("API_JWT_SECRET is required and must be at least 32 characters")
        if not BotConfig.MAIN_BOT_TOKEN:
            errors.append("MAIN_BOT_TOKEN is required to validate Telegram initData")
        if errors:
            raise RuntimeError("Invalid API configuration: " + "; ".join(errors))
