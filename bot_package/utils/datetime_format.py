from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


TEHRAN_TZ = ZoneInfo("Asia/Tehran")
LTR_MARK = "\u200e"

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

JALALI_MONTHS = {
    1: "فروردین",
    2: "اردیبهشت",
    3: "خرداد",
    4: "تیر",
    5: "مرداد",
    6: "شهریور",
    7: "مهر",
    8: "آبان",
    9: "آذر",
    10: "دی",
    11: "بهمن",
    12: "اسفند",
}


def as_tehran(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(TEHRAN_TZ)


def gregorian_to_jalali(year: int, month: int, day: int) -> tuple[int, int, int]:
    g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
    gy = year - 1600
    gm = month - 1
    gd = day - 1
    g_day_no = 365 * gy + (gy + 3) // 4 - (gy + 99) // 100 + (gy + 399) // 400
    g_day_no += sum(g_days_in_month[:gm])
    if gm > 1 and ((gy + 1600) % 4 == 0 and ((gy + 1600) % 100 != 0 or (gy + 1600) % 400 == 0)):
        g_day_no += 1
    g_day_no += gd

    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365
    jm = 0
    while jm < 11 and j_day_no >= j_days_in_month[jm]:
        j_day_no -= j_days_in_month[jm]
        jm += 1
    return jy, jm + 1, j_day_no + 1


def format_tehran_datetime(value: datetime | None, *, include_time: bool = True) -> str:
    local_value = as_tehran(value)
    if local_value is None:
        return "-"
    jy, jm, jd = gregorian_to_jalali(local_value.year, local_value.month, local_value.day)
    jalali_text = f"{jd} {JALALI_MONTHS[jm]} {jy}"
    gregorian_text = f"{LTR_MARK}{local_value.day} {GREGORIAN_MONTHS[local_value.month]} {local_value.year}{LTR_MARK}"
    date_text = f"شمسی: {jalali_text} | میلادی: {gregorian_text}"
    if not include_time:
        return date_text
    return f"{date_text} | ساعت: {local_value:%H:%M}"


def format_tehran_timestamp(timestamp: int | None, *, include_time: bool = True) -> str:
    if not timestamp:
        return "نامحدود"
    return format_tehran_datetime(datetime.fromtimestamp(timestamp, timezone.utc), include_time=include_time)
