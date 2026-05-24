from telegram import KeyboardButton, ReplyKeyboardMarkup


BUY_SUBSCRIPTION = "🛒 خرید سرویس"
WALLET = "💰 کیف پول"
PURCHASE_HISTORY = "📜 خریدهای من"
SUPPORT = "💬 پشتیبانی"
HELP = "ℹ️ راهنما"
REFERRALS = "👥 دعوت دوستان"
APPLY_COUPON = "🎁 کد تخفیف"
BACK_TO_MAIN = "⬅️ بازگشت به منوی اصلی"

ADMIN_INVENTORY = "📦 مدیریت موجودی"
ADMIN_PRICES = "💳 مدیریت قیمت‌ها"
ADMIN_USERS = "👤 مدیریت کاربران"
ADMIN_REPORTS = "📊 گزارش فروش"
ADMIN_COUPONS = "🎟 مدیریت تخفیف‌ها"
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
ADMIN_REFERRAL_REPORT = "👥 گزارش دعوت‌ها"
ADMIN_CREATE_COUPON = "➕ ساخت کد تخفیف"
ADMIN_REFRESH_ADMINS = "🔄 بروزرسانی لیست ادمین‌ها"

COUPON_PERCENT = "درصدی"
COUPON_FIXED = "مبلغ ثابت"
COUPON_ALL_USERS = "همه کاربران"
COUPON_SELECTED_USERS = "کاربران مشخص"

REPORT_TODAY = "امروز"
REPORT_WEEK = "هفته جاری"
REPORT_MONTH = "ماه جاری"

DONE_ADDING_CONFIGS = "✅ ثبت لینک‌ها"
CANCEL = "❌ لغو"

VOLUMES = (1, 2, 3, 5, 10, 20)


def _button(text: str) -> KeyboardButton:
    return KeyboardButton(text=text)


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
            [_button(BUY_SUBSCRIPTION)],
            [_button(WALLET), _button(PURCHASE_HISTORY)],
            [_button(SUPPORT), _button(HELP)],
        ]
    )


def buy_volume_keyboard(prices: dict | None = None) -> ReplyKeyboardMarkup:
    if not prices:
        prices = {1: 15000, 2: 28000, 3: 40000, 5: 65000, 10: 120000, 20: 220000}

    buttons = []
    for volume, value in prices.items():
        if isinstance(value, tuple):
            final_price, discount = value
            label = f"📦 {volume} گیگ | {final_price:,} تومان"
            if discount:
                label += f" | تخفیف {discount:,}"
        else:
            label = f"📦 {volume} گیگ | {value:,} تومان"
        buttons.append(_button(label))

    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    rows.append([_button(BACK_TO_MAIN)])
    return _keyboard(rows)


def wallet_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(APPLY_COUPON), _button(REFERRALS)],
            [_button(SUPPORT)],
            [_button(BACK_TO_MAIN)],
        ]
    )


def coupon_target_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(COUPON_ALL_USERS), _button(COUPON_SELECTED_USERS)],
            [_button(CANCEL), _button(ADMIN_BACK)],
        ],
        one_time_keyboard=True,
    )


def coupon_type_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(COUPON_PERCENT), _button(COUPON_FIXED)],
            [_button(CANCEL), _button(ADMIN_BACK)],
        ],
        one_time_keyboard=True,
    )


def back_to_main() -> ReplyKeyboardMarkup:
    return _keyboard([[_button(BACK_TO_MAIN)]])


def admin_main_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_INVENTORY), _button(ADMIN_PRICES)],
            [_button(ADMIN_USERS), _button(ADMIN_REPORTS)],
            [_button(ADMIN_COUPONS), _button(ADMIN_ADMINS)],
            [_button(ADMIN_LOGOUT)],
        ]
    )


def admin_inventory_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_ADD_CONFIG), _button(ADMIN_STOCK_STATUS)],
            [_button(ADMIN_BACK)],
        ]
    )


def volume_selection_keyboard(action: str = "add") -> ReplyKeyboardMarkup:
    if action == "edit_price":
        buttons = [_button(f"✏️ قیمت {volume} گیگ") for volume in VOLUMES]
    else:
        buttons = [_button(f"📦 {volume} گیگ") for volume in VOLUMES]

    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    rows.append([_button(CANCEL), _button(ADMIN_BACK)])
    return _keyboard(rows, one_time_keyboard=True)


def add_links_collecting_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(DONE_ADDING_CONFIGS)],
            [_button(CANCEL), _button(ADMIN_BACK)],
        ]
    )


def admin_prices_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_VIEW_PRICES), _button(ADMIN_EDIT_PRICE)],
            [_button(ADMIN_BACK)],
        ]
    )


def admin_users_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_SEARCH_USER), _button(ADMIN_CHARGE_WALLET)],
            [_button(ADMIN_USER_STATS), _button(ADMIN_REFERRAL_REPORT)],
            [_button(ADMIN_BACK)],
        ]
    )


def admin_reports_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(REPORT_TODAY), _button(REPORT_WEEK), _button(REPORT_MONTH)],
            [_button(ADMIN_BACK)],
        ]
    )


def admin_coupons_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_CREATE_COUPON)],
            [_button(ADMIN_BACK)],
        ]
    )


def admin_management_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_REFRESH_ADMINS)],
            [_button(ADMIN_BACK)],
        ]
    )
