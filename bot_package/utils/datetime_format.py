from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


TEHRAN_TZ = ZoneInfo("Asia/Tehran")

GREGORIAN_MONTHS = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
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
    month = GREGORIAN_MONTHS[local_value.month]
    date_text = f"{local_value.day} {month} {local_value.year}"
    if not include_time:
        return date_text
    return f"{date_text}، {local_value:%H:%M}"


def format_tehran_timestamp(timestamp: int | None, *, include_time: bool = True) -> str:
    if not timestamp:
        return "نامحدود"
    return format_tehran_datetime(datetime.fromtimestamp(timestamp, timezone.utc), include_time=include_time)
