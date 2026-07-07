from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


TEHRAN_TZ = ZoneInfo("Asia/Tehran")

GREGORIAN_MONTHS_FA = {
    1: "ژانویه",
    2: "فوریه",
    3: "مارس",
    4: "آوریل",
    5: "مه",
    6: "ژوئن",
    7: "جولای",
    8: "اوت",
    9: "سپتامبر",
    10: "اکتبر",
    11: "نوامبر",
    12: "دسامبر",
}


def as_tehran(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(TEHRAN_TZ)


def format_tehran_datetime(value: datetime | None, *, include_time: bool = True) -> str:
    local_value = as_tehran(value)
    if local_value is None:
        return "-"
    month = GREGORIAN_MONTHS_FA[local_value.month]
    date_text = f"{local_value.day} {month} {local_value.year}"
    if not include_time:
        return date_text
    return f"{date_text}، {local_value:%H:%M}"


def format_tehran_timestamp(timestamp: int | None, *, include_time: bool = True) -> str:
    if not timestamp:
        return "نامحدود"
    return format_tehran_datetime(datetime.fromtimestamp(timestamp, timezone.utc), include_time=include_time)
