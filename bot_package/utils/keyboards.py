import os

from telegram import KeyboardButton, ReplyKeyboardMarkup


BUY_SUBSCRIPTION = "🛒 خرید سرویس"
WALLET = "💰 کیف پول"
PURCHASE_HISTORY = "📜 خریدهای من"
SUPPORT = "💬 پشتیبانی"
HELP = "ℹ️ راهنما"
BACK_TO_MAIN = "⬅️ بازگشت به منوی اصلی"

ADMIN_INVENTORY = "📦 مدیریت موجودی"
ADMIN_PRICES = "💳 مدیریت قیمت‌ها"
ADMIN_USERS = "👤 مدیریت کاربران"
ADMIN_REPORTS = "📊 گزارش فروش"
ADMIN_ADMINS = "🛡 مدیریت ادمین‌ها"
ADMIN_LOGOUT = "🚪 خروج"
ADMIN_BACK = "⬅️ بازگشت به پنل"

ADMIN_ADD_CONFIG = "➕ افزودن کانفیگ"
ADMIN_STOCK_STATUS = "📋 وضعیت موجودی"
ADMIN_VIEW_PRICES = "👁 مشاهده قیمت‌ها"
ADMIN_EDIT_PRICE = "✏️ ویرایش قیمت"
ADMIN_SEARCH_USER = "🔎 جستجوی کاربر"
ADMIN_CHARGE_WALLET = "➕ شارژ کیف پول"
ADMIN_USER_STATS = "📈 آمار کاربران"
ADMIN_REFRESH_ADMINS = "🔄 بروزرسانی لیست ادمین‌ها"

REPORT_TODAY = "امروز"
REPORT_WEEK = "هفته جاری"
REPORT_MONTH = "ماه جاری"

DONE_ADDING_CONFIGS = "✅ ثبت لینک‌ها"
CANCEL = "❌ لغو"

VOLUMES = (1, 2, 3, 5, 10, 20)

STYLE_PRIMARY = "primary"
STYLE_SUCCESS = "success"
STYLE_DANGER = "danger"

# These IDs are safe defaults for wiring Bot API 9.4 premium icons.
# Replace them with your own custom emoji IDs for exact brand styling.
DEFAULT_PREMIUM_EMOJI_ID = "5373141891321699086"

PREMIUM_EMOJI_IDS = {
    BUY_SUBSCRIPTION: os.getenv("EMOJI_BUY_SUBSCRIPTION", DEFAULT_PREMIUM_EMOJI_ID),
    WALLET: os.getenv("EMOJI_WALLET", DEFAULT_PREMIUM_EMOJI_ID),
    PURCHASE_HISTORY: os.getenv("EMOJI_PURCHASE_HISTORY", DEFAULT_PREMIUM_EMOJI_ID),
    SUPPORT: os.getenv("EMOJI_SUPPORT", DEFAULT_PREMIUM_EMOJI_ID),
    HELP: os.getenv("EMOJI_HELP", DEFAULT_PREMIUM_EMOJI_ID),
    BACK_TO_MAIN: os.getenv("EMOJI_BACK_TO_MAIN", DEFAULT_PREMIUM_EMOJI_ID),
    ADMIN_INVENTORY: os.getenv("EMOJI_ADMIN_INVENTORY", DEFAULT_PREMIUM_EMOJI_ID),
    ADMIN_PRICES: os.getenv("EMOJI_ADMIN_PRICES", DEFAULT_PREMIUM_EMOJI_ID),
    ADMIN_USERS: os.getenv("EMOJI_ADMIN_USERS", DEFAULT_PREMIUM_EMOJI_ID),
    ADMIN_REPORTS: os.getenv("EMOJI_ADMIN_REPORTS", DEFAULT_PREMIUM_EMOJI_ID),
    ADMIN_ADMINS: os.getenv("EMOJI_ADMIN_ADMINS", DEFAULT_PREMIUM_EMOJI_ID),
    ADMIN_LOGOUT: os.getenv("EMOJI_ADMIN_LOGOUT", DEFAULT_PREMIUM_EMOJI_ID),
    ADMIN_ADD_CONFIG: os.getenv("EMOJI_ADMIN_ADD_CONFIG", DEFAULT_PREMIUM_EMOJI_ID),
    ADMIN_STOCK_STATUS: os.getenv("EMOJI_ADMIN_STOCK_STATUS", DEFAULT_PREMIUM_EMOJI_ID),
    ADMIN_VIEW_PRICES: os.getenv("EMOJI_ADMIN_VIEW_PRICES", DEFAULT_PREMIUM_EMOJI_ID),
    ADMIN_EDIT_PRICE: os.getenv("EMOJI_ADMIN_EDIT_PRICE", DEFAULT_PREMIUM_EMOJI_ID),
    ADMIN_SEARCH_USER: os.getenv("EMOJI_ADMIN_SEARCH_USER", DEFAULT_PREMIUM_EMOJI_ID),
    ADMIN_CHARGE_WALLET: os.getenv("EMOJI_ADMIN_CHARGE_WALLET", DEFAULT_PREMIUM_EMOJI_ID),
    ADMIN_USER_STATS: os.getenv("EMOJI_ADMIN_USER_STATS", DEFAULT_PREMIUM_EMOJI_ID),
    ADMIN_REFRESH_ADMINS: os.getenv("EMOJI_ADMIN_REFRESH_ADMINS", DEFAULT_PREMIUM_EMOJI_ID),
    DONE_ADDING_CONFIGS: os.getenv("EMOJI_DONE_ADDING_CONFIGS", DEFAULT_PREMIUM_EMOJI_ID),
    CANCEL: os.getenv("EMOJI_CANCEL", DEFAULT_PREMIUM_EMOJI_ID),
}


def _button(text: str, *, style: str | None = None, emoji_id: str | None = None) -> KeyboardButton:
    return KeyboardButton(
        text=text,
        style=style,
        icon_custom_emoji_id=emoji_id or PREMIUM_EMOJI_IDS.get(text),
    )


def _volume_button(text: str, *, style: str = STYLE_PRIMARY) -> KeyboardButton:
    return KeyboardButton(
        text=text,
        style=style,
        icon_custom_emoji_id=os.getenv("EMOJI_VOLUME", DEFAULT_PREMIUM_EMOJI_ID),
    )


def _keyboard(rows: list[list[str | KeyboardButton]], *, one_time_keyboard: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        one_time_keyboard=one_time_keyboard,
        input_field_placeholder="یکی از گزینه‌ها را انتخاب کنید",
    )


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(BUY_SUBSCRIPTION, style=STYLE_SUCCESS)],
            [_button(WALLET, style=STYLE_PRIMARY), _button(PURCHASE_HISTORY, style=STYLE_PRIMARY)],
            [_button(SUPPORT, style=STYLE_PRIMARY), _button(HELP, style=STYLE_PRIMARY)],
        ]
    )


def buy_volume_keyboard(prices: dict | None = None) -> ReplyKeyboardMarkup:
    if not prices:
        prices = {1: 15000, 2: 28000, 3: 40000, 5: 65000, 10: 120000, 20: 220000}

    buttons = [
        _volume_button(f"📦 {volume} گیگ | {price:,} تومان", style=STYLE_SUCCESS)
        for volume, price in prices.items()
    ]
    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    rows.append([_button(BACK_TO_MAIN, style=STYLE_PRIMARY)])
    return _keyboard(rows)


def wallet_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard([[_button(SUPPORT, style=STYLE_SUCCESS)], [_button(BACK_TO_MAIN, style=STYLE_PRIMARY)]])


def back_to_main() -> ReplyKeyboardMarkup:
    return _keyboard([[_button(BACK_TO_MAIN, style=STYLE_PRIMARY)]])


def admin_main_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_INVENTORY, style=STYLE_SUCCESS), _button(ADMIN_PRICES, style=STYLE_PRIMARY)],
            [_button(ADMIN_USERS, style=STYLE_PRIMARY), _button(ADMIN_REPORTS, style=STYLE_PRIMARY)],
            [_button(ADMIN_ADMINS, style=STYLE_PRIMARY)],
            [_button(ADMIN_LOGOUT, style=STYLE_DANGER)],
        ]
    )


def admin_inventory_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_ADD_CONFIG, style=STYLE_SUCCESS), _button(ADMIN_STOCK_STATUS, style=STYLE_PRIMARY)],
            [_button(ADMIN_BACK, style=STYLE_PRIMARY)],
        ]
    )


def volume_selection_keyboard(action: str = "add") -> ReplyKeyboardMarkup:
    if action == "edit_price":
        buttons = [
            _volume_button(f"✏️ قیمت {volume} گیگ", style=STYLE_PRIMARY)
            for volume in VOLUMES
        ]
    else:
        buttons = [
            _volume_button(f"📦 {volume} گیگ", style=STYLE_SUCCESS)
            for volume in VOLUMES
        ]

    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    rows.append([_button(CANCEL, style=STYLE_DANGER), _button(ADMIN_BACK, style=STYLE_PRIMARY)])
    return _keyboard(rows, one_time_keyboard=True)


def add_links_collecting_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(DONE_ADDING_CONFIGS, style=STYLE_SUCCESS)],
            [_button(CANCEL, style=STYLE_DANGER), _button(ADMIN_BACK, style=STYLE_PRIMARY)],
        ]
    )


def admin_prices_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_VIEW_PRICES, style=STYLE_PRIMARY), _button(ADMIN_EDIT_PRICE, style=STYLE_SUCCESS)],
            [_button(ADMIN_BACK, style=STYLE_PRIMARY)],
        ]
    )


def admin_users_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_SEARCH_USER, style=STYLE_PRIMARY), _button(ADMIN_CHARGE_WALLET, style=STYLE_SUCCESS)],
            [_button(ADMIN_USER_STATS, style=STYLE_PRIMARY)],
            [_button(ADMIN_BACK, style=STYLE_PRIMARY)],
        ]
    )


def admin_reports_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [
                _button(REPORT_TODAY, style=STYLE_SUCCESS, emoji_id=os.getenv("EMOJI_REPORT_TODAY", DEFAULT_PREMIUM_EMOJI_ID)),
                _button(REPORT_WEEK, style=STYLE_PRIMARY, emoji_id=os.getenv("EMOJI_REPORT_WEEK", DEFAULT_PREMIUM_EMOJI_ID)),
                _button(REPORT_MONTH, style=STYLE_PRIMARY, emoji_id=os.getenv("EMOJI_REPORT_MONTH", DEFAULT_PREMIUM_EMOJI_ID)),
            ],
            [_button(ADMIN_BACK, style=STYLE_PRIMARY)],
        ]
    )


def admin_management_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_REFRESH_ADMINS, style=STYLE_PRIMARY)],
            [_button(ADMIN_BACK, style=STYLE_PRIMARY)],
        ]
    )
