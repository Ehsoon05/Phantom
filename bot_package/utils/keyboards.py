from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


BUY_SUBSCRIPTION = "🛒 خرید سرویس"
WALLET = "💰 کیف پول"
PURCHASE_HISTORY = "📜 خریدهای من"
SUPPORT = "💬 پشتیبانی"
HELP = "ℹ️ راهنما"
REFERRALS = "👥 دعوت دوستان"
ACCOUNT_INFO = "👤 اطلاعات حساب"
APPLY_COUPON = "🎁 کد تخفیف"
CHARGE_CRYPTO = "💎 شارژ با کریپتو"
CHARGE_RIAL = "💳 پرداخت ریالی (کارت‌به‌کارت)"
BACK_TO_MAIN = "⬅️ بازگشت به منوی اصلی"

ADMIN_INVENTORY = "📦 مدیریت موجودی"
ADMIN_PRICES = "💳 مدیریت قیمت‌ها"
ADMIN_USERS = "👤 مدیریت کاربران"
ADMIN_REPORTS = "📊 گزارش فروش"
ADMIN_COUPONS = "🎟 مدیریت تخفیف‌ها"
ADMIN_CRYPTO = "💎 پرداخت کریپتو"
ADMIN_ADMINS = "🛡 مدیریت ادمین‌ها"
ADMIN_SHOP_SETTINGS = "⚙️ تنظیمات ربات فروش"
ADMIN_LOGOUT = "🚪 خروج"
ADMIN_BROADCAST = "📢 ارسال پیام همگانی"
ADMIN_BROADCAST_SEND = "✅ ارسال به همه کاربران"
ADMIN_BACK = "⬅️ بازگشت به پنل"

ADMIN_CRYPTO_HISTORY = "📜 تراکنش‌های کریپتو"
ADMIN_CRYPTO_SEARCH = "🔎 جستجوی تراکنش کاربر"
ADMIN_CRYPTO_RATES = "⚙️ تنظیمات نرخ ارز"
ADMIN_CRYPTO_TOGGLE_MODE = "🔁 تغییر حالت نرخ (آنلاین/دستی)"
ADMIN_CRYPTO_SET_MARGIN = "✏️ تنظیم کارمزد (٪)"
ADMIN_CRYPTO_SET_USDT = "✏️ نرخ دستی USDT"
ADMIN_CRYPTO_SET_TON = "✏️ نرخ دستی TON"
ADMIN_RIAL_HISTORY = "📋 درخواست‌های کارت‌به‌کارت"
ADMIN_RIAL_SETTINGS = "💳 تنظیمات کارت‌به‌کارت"
ADMIN_RIAL_SET_MIN = "✏️ حداقل پرداخت ریالی"
ADMIN_RIAL_TOGGLE_PHONE = "📱 دریافت شماره تماس"
ADMIN_RIAL_SET_SUPPORT = "👤 آیدی پشتیبانی ریالی"

ADMIN_ADD_CONFIG = "➕ افزودن کانفیگ"
ADMIN_STOCK_STATUS = "📋 وضعیت موجودی"
ADMIN_VIEW_PRICES = "👁 مشاهده قیمت‌ها"
ADMIN_EDIT_PRICE = "✏️ ویرایش قیمت"
ADMIN_SEARCH_USER = "🔎 جستجوی کاربر"
ADMIN_CHARGE_WALLET = "➕ شارژ کیف پول"
ADMIN_SET_WALLET = "✏️ تنظیم موجودی کیف پول"
ADMIN_USER_STATS = "📈 آمار کاربران"
ADMIN_REFERRAL_REPORT = "👥 گزارش دعوت‌ها"
ADMIN_REFERRAL_REWARDS = "🎁 پاداش‌های رفرال"
ADMIN_REFERRAL_ADD_RULE = "➕ قانون پاداش جدید"
ADMIN_REFERRAL_RECALCULATE = "🔄 محاسبه پاداش‌های قبلی"
ADMIN_REFERRAL_TOGGLE_RULE = "⏯ فعال/غیرفعال"
ADMIN_REFERRAL_DELETE_RULE = "🗑 حذف قانون"
ADMIN_CREATE_COUPON = "➕ ساخت کد تخفیف"
ADMIN_EDIT_COUPON = "✏️ ویرایش تخفیف"
ADMIN_VIEW_COUPONS = "📋 مشاهده تخفیف‌ها"
ADMIN_DEACTIVATE_COUPON = "⏸ غیرفعال‌سازی تخفیف"
ADMIN_DELETE_COUPON = "🗑 حذف تخفیف"
ADMIN_REFRESH_ADMINS = "🔄 بروزرسانی لیست ادمین‌ها"
ADMIN_ADD_ADMIN = "➕ افزودن ادمین"
ADMIN_REMOVE_ADMIN = "➖ حذف ادمین"
ADMIN_CHANGE_ADMIN_PERMS = "🔐 تغییر دسترسی ادمین"
ADMIN_SHOP_MESSAGES = "📝 مدیریت پیام‌ها"
ADMIN_SHOP_BUTTONS = "🔘 مدیریت دکمه‌ها"
ADMIN_SHOP_PLANS = "📦 مدیریت سرویس‌ها"
ADMIN_SHOP_CATEGORIES = "🗂 مدیریت دسته‌ها"
ADMIN_PROVISION_PANELS = "🧬 مدیریت پنل‌های ساخت"
ADMIN_REQUIRED_CHANNELS = "📣 عضویت اجباری"
ADMIN_TOGGLE_BRANDED_LINKS = "🔗 لینک اختصاصی ساب"
ADMIN_TRIAL_SETTINGS = "🧪 تنظیمات کانفیگ تست"
ADMIN_TRIAL_TOGGLE = "⏯ روشن/خاموش کردن تست"
ADMIN_TRIAL_SET_VOLUME = "📦 حجم تست (مگابایت)"
ADMIN_TRIAL_SET_DURATION = "⏱ مدت تست (ساعت)"
ADMIN_SERVICE_REMINDERS = "🔔 هشدار تمدید سرویس"
ADMIN_SERVICE_REMINDER_TOGGLE = "⏯ روشن/خاموش هشدارها"
ADMIN_SERVICE_REMINDER_SET_VOLUME = "📉 درصدهای هشدار حجم"
ADMIN_SERVICE_REMINDER_SET_DAYS = "⏳ روزهای هشدار زمان"
ADMIN_SERVICE_REMINDER_SET_HOURS = "⏱ ساعت‌های هشدار زمان"
ADMIN_SHOP_RESET_DEFAULTS = "↩️ بازگشت فروشگاه به پیش‌فرض"
ADMIN_SHOP_MENU_MAIN = "منوی اصلی فروش"
ADMIN_SHOP_MENU_WALLET = "منوی کیف پول"
ADMIN_SHOP_MENU_BUY = "منوی خرید"
ADMIN_SHOP_MENU_BACK = "دکمه بازگشت"
ADMIN_EDIT_TEXT = "✏️ تغییر متن"
ADMIN_EDIT_EMOJI = "😀 تغییر ایموجی"
ADMIN_EDIT_PREMIUM_EMOJI = "💎 تغییر ایموجی پریمیوم"
ADMIN_EDIT_PREMIUM_EMOJI_POSITION = "💎↔️ جای ایموجی پریمیوم"
ADMIN_EDIT_STYLE = "🎨 تغییر رنگ"
ADMIN_EDIT_POSITION = "↕️ تغییر چینش"
ADMIN_TOGGLE_ENABLED = "⏯ فعال/غیرفعال"
ADMIN_ADD_BUTTON = "➕ افزودن دکمه سفارشی"
ADMIN_DELETE_BUTTON = "🗑 حذف دکمه"
ADMIN_DELETE_PLAN = "🗑 حذف کامل سرویس"
ADMIN_DELETE_PLAN_CONFIRM = "⚠️ بله، سرویس کامل حذف شود"
ADMIN_PLAN_PROVISION_SETTINGS = "🧬 تنظیمات ساخت از پنل"
ADMIN_SET_PROVISION_MODE = "🔁 حالت تامین سرویس"
ADMIN_SET_PROVISION_PANEL = "🖥 انتخاب پنل ساخت"
ADMIN_TOGGLE_PROVISION = "⏯ ساخت خودکار"
ADMIN_TOGGLE_RENEW = "🔄 تمدید سرویس"
ADMIN_SET_NAME_PREFIX = "🏷 پیشوند نام ساب"
ADMIN_SET_PROVISION_VOLUME = "📦 حجم واقعی ساخت"
ADMIN_SET_PROVISION_DURATION = "⏱ مدت واقعی ساخت"
ADMIN_SET_PROVISION_TIME_MODE = "🕒 نوع زمان ساخت"
ADMIN_SET_SUBSCRIPTION_DEVICE_LIMIT = "👤 محدودیت کاربر ساب"
ADMIN_PLAN_BACK_TO_EDIT = "⬅️ بازگشت به ویرایش سرویس"
ADMIN_SET_PANEL_GROUPS = "👥 گروه‌های آسان پنل"
ADMIN_SET_PANEL_HWID = "🔐 محدودیت HWID"
ADMIN_SET_PANEL_INBOUNDS = "🔌 اینباندهای مرزبان"
ADMIN_SET_PANEL_PROTOCOLS = "🧩 پروتکل‌های پنل"
ADMIN_TOGGLE_PANEL_ENABLED = "⏯ فعال/غیرفعال پنل"
ADMIN_ADD_PLAN = "➕ افزودن سرویس"
ADMIN_ADD_CATEGORY = "➕ افزودن دسته"
ADMIN_DELETE_CATEGORY = "🗑 حذف دسته"
ADMIN_ADD_CHANNEL = "➕ افزودن کانال"
ADMIN_DELETE_CHANNEL = "🗑 حذف کانال"
ADMIN_EDIT_TITLE = "✏️ تغییر عنوان"
ADMIN_EDIT_ORDER = "↕️ تغییر ترتیب"
ADMIN_EDIT_EMOJI_POSITION = "↔️ جای ایموجی"
ADMIN_EDIT_CATEGORY = "🗂 دسته‌بندی سرویس"
ADMIN_EDIT_RESPONSE_BUTTON = "🔗 نوع دکمه جواب"
ADMIN_RESPONSE_TEXT = "متن عادی"
ADMIN_RESPONSE_INLINE_COPY = "دکمه شیشه‌ای کپی"
ADMIN_RESPONSE_INLINE_URL = "دکمه شیشه‌ای لینک"
ADMIN_RESPONSE_INLINE_ACTION = "دکمه شیشه‌ای اکشن"
ADMIN_RESPONSE_REPLY_KEYBOARD = "کیبورد معمولی"
ADMIN_RESPONSE_EDIT_STYLE = "🎨 رنگ دکمه جواب"
ADMIN_RESPONSE_EDIT_PREMIUM_EMOJI = "💎 ایموجی دکمه جواب"
ADMIN_RESPONSE_SELECT_EXISTING = "🔗 اتصال به دکمه موجود"
ADMIN_RESET_CONFIRM = "⚠️ بله، بازگردانی شود"
ADMIN_EMOJI_LEFT = "چپ"
ADMIN_EMOJI_RIGHT = "راست"

COUPON_PERCENT = "درصدی"
COUPON_FIXED = "مبلغ ثابت"
COUPON_ALL_USERS = "همه کاربران"
COUPON_SELECTED_USERS = "کاربران مشخص"

REPORT_TODAY = "امروز"
REPORT_WEEK = "هفته جاری"
REPORT_MONTH = "ماه جاری"
REPORT_45_DAYS = "۴۵ روز اخیر"
REPORT_90_DAYS = "۹۰ روز اخیر"

DONE_ADDING_CONFIGS = "✅ ثبت لینک‌ها"
CANCEL = "❌ لغو"
CONFIRM_USER = "✅ تایید کاربر"
CHANGE_USER = "🔄 تغییر کاربر"

VOLUMES = (1, 2, 3, 5, 10, 20)

STYLE_PRIMARY = "primary"
STYLE_SUCCESS = "success"
STYLE_DANGER = "danger"
STYLE_DEFAULT = "default"

# Replace this with your own Telegram custom/premium emoji ID.
# It is intentionally one fixed icon for every user-facing shop button.
SHOP_BUTTON_CUSTOM_EMOJI_ID = "5373141891321699086"


def _button(text: str, *, style: str | None = None) -> KeyboardButton:
    try:
        return KeyboardButton(text=text, api_kwargs={"style": style} if style else None)
    except TypeError:
        return KeyboardButton(text=text)


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
            [_shop_button(REFERRALS, style=STYLE_PRIMARY), _shop_button(ACCOUNT_INFO)],
            [_shop_button(SUPPORT), _shop_button(HELP)],
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
        buttons.append(_shop_button(label, style=STYLE_SUCCESS))

    rows = [[button] for button in buttons]
    rows.append([_shop_button(BACK_TO_MAIN, style=STYLE_DANGER)])
    return _keyboard(rows)


def wallet_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_shop_button(APPLY_COUPON, style=STYLE_SUCCESS), _shop_button(REFERRALS)],
            [_shop_button(SUPPORT, style=STYLE_SUCCESS)],
            [_shop_button(BACK_TO_MAIN, style=STYLE_DANGER)],
        ]
    )


def referral_share_keyboard(share_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("👥 دعوت دوستان", url=share_url)]]
    )


def admin_user_confirm_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(CONFIRM_USER), _button(CHANGE_USER)],
            [_button(CANCEL), _button(ADMIN_BACK)],
        ],
        one_time_keyboard=True,
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
    return _keyboard([[_shop_button(BACK_TO_MAIN, style=STYLE_DANGER)]])


def admin_main_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_INVENTORY), _button(ADMIN_PRICES)],
            [_button(ADMIN_USERS), _button(ADMIN_REPORTS)],
            [_button(ADMIN_COUPONS), _button(ADMIN_CRYPTO)],
            [_button(ADMIN_SHOP_SETTINGS), _button(ADMIN_ADMINS)],
            [_button(ADMIN_BROADCAST)],
            [_button(ADMIN_LOGOUT)],
        ]
    )


def admin_crypto_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_CRYPTO_HISTORY), _button(ADMIN_CRYPTO_SEARCH)],
            [_button(ADMIN_CRYPTO_RATES)],
            [_button(ADMIN_RIAL_HISTORY), _button(ADMIN_RIAL_SETTINGS)],
            [_button(ADMIN_BACK)],
        ]
    )


def admin_crypto_rates_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_CRYPTO_TOGGLE_MODE)],
            [_button(ADMIN_CRYPTO_SET_MARGIN)],
            [_button(ADMIN_CRYPTO_SET_USDT), _button(ADMIN_CRYPTO_SET_TON)],
            [_button(ADMIN_BACK)],
        ]
    )


def admin_rial_settings_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_RIAL_SET_MIN)],
            [_button(ADMIN_RIAL_TOGGLE_PHONE)],
            [_button(ADMIN_RIAL_SET_SUPPORT)],
            [_button(ADMIN_BACK)],
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
            [_button(ADMIN_SET_WALLET)],
            [_button(ADMIN_USER_STATS), _button(ADMIN_REFERRAL_REPORT)],
            [_button(ADMIN_REFERRAL_REWARDS)],
            [_button(ADMIN_BACK)],
        ]
    )


def admin_reports_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(REPORT_TODAY), _button(REPORT_WEEK), _button(REPORT_MONTH)],
            [_button(REPORT_45_DAYS), _button(REPORT_90_DAYS)],
            [_button(ADMIN_BACK)],
        ]
    )


def admin_coupons_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_CREATE_COUPON), _button(ADMIN_VIEW_COUPONS)],
            [_button(ADMIN_EDIT_COUPON)],
            [_button(ADMIN_DEACTIVATE_COUPON), _button(ADMIN_DELETE_COUPON)],
            [_button(ADMIN_BACK)],
        ]
    )


def admin_management_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_REFRESH_ADMINS)],
            [_button(ADMIN_ADD_ADMIN), _button(ADMIN_REMOVE_ADMIN)],
            [_button(ADMIN_CHANGE_ADMIN_PERMS)],
            [_button(ADMIN_BACK)],
        ]
    )


def admin_shop_settings_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_SHOP_MESSAGES), _button(ADMIN_SHOP_BUTTONS)],
            [_button(ADMIN_SHOP_PLANS), _button(ADMIN_SHOP_CATEGORIES)],
            [_button(ADMIN_PROVISION_PANELS)],
            [_button(ADMIN_REQUIRED_CHANNELS), _button(ADMIN_TOGGLE_BRANDED_LINKS)],
            [_button(ADMIN_TRIAL_SETTINGS)],
            [_button(ADMIN_SERVICE_REMINDERS)],
            [_button(ADMIN_SHOP_RESET_DEFAULTS, style=STYLE_DANGER)],
            [_button(ADMIN_BACK)],
        ]
    )


def admin_trial_settings_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_TRIAL_TOGGLE)],
            [_button(ADMIN_TRIAL_SET_VOLUME), _button(ADMIN_TRIAL_SET_DURATION)],
            [_button(ADMIN_BACK)],
        ]
    )


def admin_service_reminders_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_SERVICE_REMINDER_TOGGLE)],
            [_button(ADMIN_SERVICE_REMINDER_SET_VOLUME)],
            [_button(ADMIN_SERVICE_REMINDER_SET_DAYS), _button(ADMIN_SERVICE_REMINDER_SET_HOURS)],
            [_button(ADMIN_BACK)],
        ]
    )


def admin_shop_menus_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_SHOP_MENU_MAIN), _button(ADMIN_SHOP_MENU_WALLET)],
            [_button(ADMIN_SHOP_MENU_BUY), _button(ADMIN_SHOP_MENU_BACK)],
            [_button(CANCEL), _button(ADMIN_BACK)],
        ],
        one_time_keyboard=True,
    )


def admin_shop_button_edit_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_EDIT_TEXT), _button(ADMIN_EDIT_EMOJI)],
            [_button(ADMIN_EDIT_PREMIUM_EMOJI), _button(ADMIN_EDIT_STYLE)],
            [_button(ADMIN_EDIT_EMOJI_POSITION), _button(ADMIN_EDIT_PREMIUM_EMOJI_POSITION)],
            [_button(ADMIN_EDIT_POSITION), _button(ADMIN_TOGGLE_ENABLED)],
            [_button(ADMIN_DELETE_BUTTON)],
            [_button(CANCEL), _button(ADMIN_BACK)],
        ],
        one_time_keyboard=True,
    )


def admin_shop_plan_edit_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_EDIT_TITLE), _button(ADMIN_EDIT_PRICE)],
            [_button(ADMIN_EDIT_EMOJI), _button(ADMIN_EDIT_PREMIUM_EMOJI)],
            [_button(ADMIN_EDIT_EMOJI_POSITION), _button(ADMIN_EDIT_PREMIUM_EMOJI_POSITION)],
            [_button(ADMIN_EDIT_STYLE)],
            [_button(ADMIN_EDIT_CATEGORY), _button(ADMIN_EDIT_ORDER)],
            [_button(ADMIN_PLAN_PROVISION_SETTINGS)],
            [_button(ADMIN_TOGGLE_ENABLED)],
            [_button(ADMIN_DELETE_PLAN, style=STYLE_DANGER)],
            [_button(CANCEL), _button(ADMIN_BACK)],
        ],
        one_time_keyboard=True,
    )


def admin_shop_plan_provision_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_SET_PROVISION_MODE), _button(ADMIN_SET_PROVISION_PANEL)],
            [_button(ADMIN_TOGGLE_PROVISION), _button(ADMIN_TOGGLE_RENEW)],
            [_button(ADMIN_SET_NAME_PREFIX), _button(ADMIN_SET_PROVISION_VOLUME)],
            [_button(ADMIN_SET_PROVISION_TIME_MODE), _button(ADMIN_SET_PROVISION_DURATION)],
            [_button(ADMIN_SET_SUBSCRIPTION_DEVICE_LIMIT)],
            [_button(ADMIN_PLAN_BACK_TO_EDIT)],
            [_button(CANCEL), _button(ADMIN_BACK)],
        ],
        one_time_keyboard=True,
    )


def admin_provision_panel_keyboard(panel_type: str | None = None) -> ReplyKeyboardMarkup:
    if panel_type == "easy":
        rows = [
            [_button(ADMIN_SET_PANEL_GROUPS), _button(ADMIN_SET_PANEL_HWID)],
            [_button(ADMIN_TOGGLE_PANEL_ENABLED)],
            [_button(CANCEL), _button(ADMIN_BACK)],
        ]
    else:
        rows = [
            [_button(ADMIN_SET_PANEL_INBOUNDS), _button(ADMIN_SET_PANEL_PROTOCOLS)],
            [_button(ADMIN_TOGGLE_PANEL_ENABLED)],
            [_button(CANCEL), _button(ADMIN_BACK)],
        ]
    return _keyboard(rows, one_time_keyboard=True)


def admin_provision_mode_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button("انبار فقط")],
            [_button("اول انبار بعد پنل")],
            [_button("فقط پنل")],
            [_button(CANCEL), _button(ADMIN_BACK)],
        ],
        one_time_keyboard=True,
    )


def admin_provision_time_mode_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button("شروع از اولین اتصال")],
            [_button("تاریخ‌دار از زمان ساخت")],
            [_button("زمان نامحدود")],
            [_button(CANCEL), _button(ADMIN_BACK)],
        ],
        one_time_keyboard=True,
    )


def admin_shop_plan_delete_confirm_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_DELETE_PLAN_CONFIRM, style=STYLE_DANGER)],
            [_button(CANCEL), _button(ADMIN_BACK)],
        ],
        one_time_keyboard=True,
    )


def admin_shop_category_edit_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_EDIT_TITLE), _button(ADMIN_EDIT_EMOJI)],
            [_button(ADMIN_EDIT_PREMIUM_EMOJI), _button(ADMIN_EDIT_EMOJI_POSITION)],
            [_button(ADMIN_EDIT_STYLE), _button(ADMIN_EDIT_ORDER)],
            [_button(ADMIN_TOGGLE_ENABLED)],
            [_button(ADMIN_DELETE_CATEGORY)],
            [_button(CANCEL), _button(ADMIN_BACK)],
        ],
        one_time_keyboard=True,
    )


def admin_style_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(STYLE_PRIMARY), _button(STYLE_SUCCESS)],
            [_button(STYLE_DANGER), _button(STYLE_DEFAULT)],
            [_button(CANCEL), _button(ADMIN_BACK)],
        ],
        one_time_keyboard=True,
    )


def admin_emoji_position_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_EMOJI_LEFT), _button(ADMIN_EMOJI_RIGHT)],
            [_button(CANCEL), _button(ADMIN_BACK)],
        ],
        one_time_keyboard=True,
    )


def admin_response_button_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_RESPONSE_TEXT), _button(ADMIN_RESPONSE_INLINE_COPY)],
            [_button(ADMIN_RESPONSE_INLINE_URL), _button(ADMIN_RESPONSE_INLINE_ACTION)],
            [_button(ADMIN_RESPONSE_REPLY_KEYBOARD), _button(ADMIN_RESPONSE_SELECT_EXISTING)],
            [_button(ADMIN_RESPONSE_EDIT_STYLE), _button(ADMIN_RESPONSE_EDIT_PREMIUM_EMOJI)],
            [_button(ADMIN_EDIT_PREMIUM_EMOJI), _button(ADMIN_EDIT_PREMIUM_EMOJI_POSITION)],
            [_button(CANCEL), _button(ADMIN_BACK)],
        ],
        one_time_keyboard=True,
    )


def admin_reset_confirm_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_RESET_CONFIRM, style=STYLE_DANGER)],
            [_button(CANCEL), _button(ADMIN_BACK)],
        ],
        one_time_keyboard=True,
    )


def admin_required_channel_keyboard() -> ReplyKeyboardMarkup:
    return _keyboard(
        [
            [_button(ADMIN_ADD_CHANNEL), _button(ADMIN_DELETE_CHANNEL)],
            [_button(CANCEL), _button(ADMIN_BACK)],
        ],
        one_time_keyboard=True,
    )
