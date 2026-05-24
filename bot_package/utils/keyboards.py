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

# Put your own Telegram premium/custom emoji ID here.
# This single icon is used only for the user-facing shop bot buttons.
SHOP_BUTTON_CUSTOM_EMOJI_ID = "5373141891321699086"


def _shop_button(text: str, *, style: str = STYLE_PRIMARY) -> KeyboardButton:
    return KeyboardButton(
        text=text,
        style=style,
        icon_custom_emoji_id=SHOP_BUTTON_CUSTOM_EMOJI_ID,
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
            [_shop_button(BUY_SUBSCRIPTION, style=STYLE_SUCCESS)],
            [_shop_button(WALLET), _shop_button(PURCHASE_HISTORY)],
            [_shop_button(SUPPORT), _shop_button(HELP)],
        ]
    )


def buy_volume_keyboard(prices: dict | None = None) -> ReplyKeyboardMarkup:
    if not prices:
        prices = {1: 15000, 2: 28000, 3: 40000, 5: 65000, 10: 120000, 20: 220000}

    buttons = [
        _shop_button(f"📦 {volume} گیگ | {price:,} تومان", style=STYLE_SUCCESS)
        for volume, price in prices.items()
    ]
    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    rows.append([_shop_button(BACK_TO_MAIN)])
    return _keyboard(rows)


def wallet_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard([[_shop_button(SUPPORT, style=STYLE_SUCCESS)], [_shop_button(BACK_TO_MAIN)]])


def back_to_main() -> ReplyKeyboardMarkup:
    return _keyboard([[_shop_button(BACK_TO_MAIN)]])


def admin_main_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [ADMIN_INVENTORY, ADMIN_PRICES],
            [ADMIN_USERS, ADMIN_REPORTS],
            [ADMIN_ADMINS],
            [ADMIN_LOGOUT],
        ]
    )


def admin_inventory_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [ADMIN_ADD_CONFIG, ADMIN_STOCK_STATUS],
            [ADMIN_BACK],
        ]
    )


def volume_selection_keyboard(action: str = "add") -> ReplyKeyboardMarkup:
    if action == "edit_price":
        buttons = [f"✏️ قیمت {volume} گیگ" for volume in VOLUMES]
    else:
        buttons = [f"📦 {volume} گیگ" for volume in VOLUMES]

    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    rows.append([CANCEL, ADMIN_BACK])
    return _keyboard(rows, one_time_keyboard=True)


def add_links_collecting_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [DONE_ADDING_CONFIGS],
            [CANCEL, ADMIN_BACK],
        ]
    )


def admin_prices_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [ADMIN_VIEW_PRICES, ADMIN_EDIT_PRICE],
            [ADMIN_BACK],
        ]
    )


def admin_users_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [ADMIN_SEARCH_USER, ADMIN_CHARGE_WALLET],
            [ADMIN_USER_STATS],
            [ADMIN_BACK],
        ]
    )


def admin_reports_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [REPORT_TODAY, REPORT_WEEK, REPORT_MONTH],
            [ADMIN_BACK],
        ]
    )


def admin_management_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [ADMIN_REFRESH_ADMINS],
            [ADMIN_BACK],
        ]
    )
