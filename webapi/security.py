"""Telegram initData validation and JWT issuing/verification."""

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl

import jwt

from .config import ApiConfig, BotConfig


class AuthError(Exception):
    pass


def validate_init_data(init_data: str) -> dict:
    """Validate a Telegram Mini App initData string per the official spec.

    Returns the parsed payload (with ``user`` decoded to a dict) on success.
    """
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        raise AuthError("initData is not a valid query string")

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise AuthError("initData is missing hash")

    data_check_string = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", BotConfig.MAIN_BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise AuthError("initData signature mismatch")

    auth_date = int(pairs.get("auth_date", "0") or 0)
    if auth_date <= 0 or time.time() - auth_date > ApiConfig.INIT_DATA_MAX_AGE_SECONDS:
        raise AuthError("initData is expired")

    if "user" in pairs:
        try:
            pairs["user"] = json.loads(pairs["user"])
        except json.JSONDecodeError:
            raise AuthError("initData user payload is not valid JSON")
    return pairs


def issue_user_token(telegram_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(telegram_id),
        "role": "user",
        "iat": now,
        "exp": now + timedelta(hours=ApiConfig.USER_TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, ApiConfig.JWT_SECRET, algorithm=ApiConfig.JWT_ALGORITHM)


def issue_admin_token(telegram_id: int, permissions: str, is_owner: bool) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(telegram_id),
        "role": "admin",
        "perms": permissions,
        "owner": is_owner,
        "iat": now,
        "exp": now + timedelta(minutes=ApiConfig.ADMIN_TOKEN_TTL_MINUTES),
    }
    return jwt.encode(payload, ApiConfig.JWT_SECRET, algorithm=ApiConfig.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, ApiConfig.JWT_SECRET, algorithms=[ApiConfig.JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise AuthError(f"invalid token: {exc}")
