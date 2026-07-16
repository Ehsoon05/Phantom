from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import html
import re

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from ..models import BotSetting, Config, Price, ReferralRewardRule, ShopButton, ShopMessage, ShopMessageButton, ShopPlan, ShopPlanCategory
from ..utils import messages as default_messages
from ..utils.keyboards import (
    ACCOUNT_INFO,
    APPLY_COUPON,
    BACK_TO_MAIN,
    BUY_SUBSCRIPTION,
    CHARGE_HOOSHPAY,
    CHARGE_RIAL,
    CHARGE_CRYPTO,
    HELP,
    PURCHASE_HISTORY,
    REFERRALS,
    SUPPORT,
    WALLET,
    STYLE_DANGER,
    STYLE_PRIMARY,
    STYLE_SUCCESS,
    SHOP_BUTTON_CUSTOM_EMOJI_ID,
)


PARSE_MODE_MARKDOWN = "Markdown"
TARIFFS_MESSAGE_KEY = "custom_message:shop_main:tariffs"
LEGACY_TARIFFS_MESSAGE_KEY = "custom_message:shop_main:1780731124"


class RenderedMessage(str):
    parse_mode: str
    photo_file_id: str | None

    def __new__(cls, value: str, parse_mode: str = PARSE_MODE_MARKDOWN, photo_file_id: str | None = None):
        instance = super().__new__(cls, value)
        instance.parse_mode = parse_mode
        instance.photo_file_id = photo_file_id
        return instance

    def __add__(self, other):
        other_mode = getattr(other, "parse_mode", PARSE_MODE_MARKDOWN)
        if self.parse_mode == "HTML" or other_mode == "HTML":
            left = str(self) if self.parse_mode == "HTML" else _markdown_to_telegram_html(str(self))
            right = str(other) if other_mode == "HTML" else _markdown_to_telegram_html(str(other))
            return RenderedMessage(left + right, "HTML", self.photo_file_id)
        return RenderedMessage(super().__add__(str(other)), self.parse_mode, self.photo_file_id)

    def __radd__(self, other):
        other_mode = getattr(other, "parse_mode", PARSE_MODE_MARKDOWN)
        if self.parse_mode == "HTML" or other_mode == "HTML":
            left = str(other) if other_mode == "HTML" else _markdown_to_telegram_html(str(other))
            right = str(self) if self.parse_mode == "HTML" else _markdown_to_telegram_html(str(self))
            return RenderedMessage(left + right, "HTML", self.photo_file_id)
        return RenderedMessage(str(other) + str(self), self.parse_mode, self.photo_file_id)


def _markdown_to_telegram_html(value: str) -> str:
    escaped = html.escape(value, quote=False)
    escaped = re.sub(r"```(?:[A-Za-z0-9_-]+)?\n?(.*?)```", r"<pre>\1</pre>", escaped, flags=re.DOTALL)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped, flags=re.DOTALL)
    escaped = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^)\s]+|tg://[^)\s]+)\)",
        r'<a href="\2">\1</a>',
        escaped,
    )
    return escaped


@dataclass(frozen=True)
class ButtonDefinition:
    action: str
    menu: str
    text: str
    emoji: str | None
    style: str | None
    row: int
    col: int
    premium_emoji_id: str | None = None
    emoji_position: str = "left"


@dataclass(frozen=True)
class PlanDefinition:
    volume_gb: int
    title: str
    emoji: str | None
    style: str | None
    display_order: int
    premium_emoji_id: str | None = None
    category_key: str = "default"
    emoji_position: str = "left"
    price: int | None = None


@dataclass(frozen=True)
class CategoryDefinition:
    key: str
    title: str
    emoji: str | None
    style: str | None
    display_order: int
    premium_emoji_id: str | None = None
    emoji_position: str = "left"


def _split_label(label: str) -> tuple[str | None, str]:
    parts = label.split(" ", 1)
    if len(parts) == 2 and len(parts[0]) <= 4:
        return parts[0], parts[1]
    return None, label


def clean_custom_variable_name(value: str) -> str:
    key = re.sub(r"[^A-Za-z0-9_:-]+", "_", (value or "").strip().lower()).strip("_:-")
    return key[:64]


def custom_message_action(menu: str, variable_name: str) -> str:
    return f"custom_message:{menu}:{clean_custom_variable_name(variable_name)}"


def _button_default(action: str, menu: str, label: str, style: str, row: int, col: int) -> ButtonDefinition:
    emoji, text = _split_label(label)
    return ButtonDefinition(
        action=action,
        menu=menu,
        text=text,
        emoji=emoji,
        style=style,
        row=row,
        col=col,
        premium_emoji_id=SHOP_BUTTON_CUSTOM_EMOJI_ID if menu.startswith("shop") else None,
    )


DEFAULT_BUTTONS: tuple[ButtonDefinition, ...] = (
    ButtonDefinition(TARIFFS_MESSAGE_KEY, "shop_main", "تعرفه ها", None, None, 0, 0, "5884491244360438851"),
    ButtonDefinition("buy_subscription", "shop_main", "خرید سرویس", None, STYLE_PRIMARY, 0, 1, "5922272602784534896"),
    ButtonDefinition("trial_config", "shop_main", "دریافت کانفیگ تست", "🧪", STYLE_SUCCESS, 1, 0, "5373141891321699086"),
    ButtonDefinition("wallet", "shop_main", "کیف پول", None, None, 2, 0, "5769126056262898415"),
    ButtonDefinition("purchase_history", "shop_main", "سرویس های من", None, None, 2, 1, "5805550320985578625"),
    ButtonDefinition("referrals", "shop_main", "دعوت دوستان", None, None, 3, 0, "6033125983572201397"),
    ButtonDefinition("account_info", "shop_main", "اطلاعات حساب", None, None, 3, 1, "5904630315946611415"),
    ButtonDefinition("support", "shop_main", "پشتیبانی", None, None, 4, 0, "6037421444789440735"),
    ButtonDefinition("help", "shop_main", "آموزش اتصال", None, None, 4, 1, "5776233299424843260"),
    _button_default("charge_rial", "shop_wallet", CHARGE_RIAL, STYLE_SUCCESS, 0, 0),
    _button_default("charge_crypto", "shop_wallet", CHARGE_CRYPTO, STYLE_SUCCESS, 1, 0),
    _button_default("charge_hooshpay", "shop_wallet", CHARGE_HOOSHPAY, STYLE_PRIMARY, 2, 0),
    _button_default("apply_coupon", "shop_wallet", APPLY_COUPON, STYLE_SUCCESS, 3, 0),
    _button_default("referrals", "shop_wallet", REFERRALS, STYLE_PRIMARY, 3, 1),
    _button_default("support", "shop_wallet", SUPPORT, STYLE_SUCCESS, 4, 0),
    _button_default("back_to_main", "shop_wallet", BACK_TO_MAIN, STYLE_DANGER, 5, 0),
    _button_default("back_to_main", "shop_back", BACK_TO_MAIN, STYLE_DANGER, 0, 0),
    ButtonDefinition("back_to_main", "shop_buy", "بازگشت به منوی اصلی", None, None, 99, 0, "6039539366177541657"),
)


DEFAULT_MESSAGES: dict[str, str] = {
    "main_menu": default_messages.MAIN_MENU_TEXT,
    "trial_success": (
        "**کانفیگ تست شما آماده شد**\n\n"
        "حجم: **{volume_mb} مگابایت**\n"
        "مدت: **{duration_hours} ساعت از اولین اتصال**\n\n"
        "سرویس با نام **تست رایگان** در بخش «سرویس‌های من» ثبت شد."
    ),
    "trial_already_claimed": (
        "**کانفیگ تست قبلاً دریافت شده است**\n\n"
        "برای هر حساب تلگرام فقط یک کانفیگ تست قابل دریافت است.\n"
        "سرویس خود را از بخش «سرویس‌های من» مشاهده کنید."
    ),
    "trial_unavailable": (
        "**ساخت کانفیگ تست انجام نشد**\n\n"
        "لطفاً کمی بعد دوباره تلاش کنید یا با پشتیبانی در ارتباط باشید."
    ),
    "trial_disabled": "**دریافت کانفیگ تست در حال حاضر غیرفعال است.**",
    "buy_menu": default_messages.BUY_MENU_TEXT,
    "rules_text": (
        "**قوانین استفاده از فانتوم**\n\n"
        "با استفاده از ربات، مسئولیت نگهداری لینک اشتراک و رعایت قوانین سرویس بر عهده شماست.\n"
        "لطفا لینک‌ها را عمومی منتشر نکنید و فقط برای استفاده شخصی نگه دارید.\n\n"
        "برای ادامه، قوانین را تایید کنید."
    ),
    "rules_accepted": "قوانین تایید شد. خوش آمدید.",
    "required_channel_join_prompt": (
        "برای استفاده از ربات، ابتدا در کانال‌های زیر عضو شوید و سپس دوباره /start را بزنید."
    ),
    "wallet": (
        "**کیف پول شما**\n\n"
        "موجودی فعلی: **{wallet_balance} تومان**\n\n"
        "برای شارژ کیف پول، به پشتیبانی پیام بدهید:\n"
        "{support_handle}"
    ),
    "wallet_charge_notification": (
        "✅ **کیف پول شما شارژ شد**\n\n"
        "مبلغ شارژ: **{amount} تومان**\n"
        "موجودی جدید: **{wallet_balance} تومان**\n\n"
        "اکنون می‌توانید سرویس موردنظرتان را تهیه کنید."
    ),
    "service_expiry_reminder": (
        "🔔 **یادآوری تمدید سرویس**\n\n"
        "سرویس: **{service_name}**\n"
        "{reason_lines}\n\n"
        "حجم کل: **{total_volume}**\n"
        "حجم باقی‌مانده: **{remaining_volume}**\n"
        "درصد باقی‌مانده: **{remaining_percent}**\n"
        "تاریخ انقضا: **{expiry_text}**\n"
        "زمان باقی‌مانده: **{remaining_time}**\n\n"
        "مهلت حذف از پنل: **{deletion_due_at}**\n"
        "زمان باقی‌مانده تا حذف: **{deletion_remaining_time}**\n\n"
        "برای جلوگیری از قطع شدن سرویس، می‌توانید همین حالا تمدیدش کنید."
    ),
    "purchase_success": (
        "**خرید با موفقیت انجام شد**\n\n"
        "نام سرویس: **{service_name}**\n"
        "حجم سرویس: **{volume}**\n"
        "مبلغ پرداختی: **{price} تومان**\n\n"
        "لینک اشتراک شما:\n"
        "`{sub_link}`\n\n"
        "لطفا این لینک را فقط برای خودتان نگه دارید."
    ),
    "support": default_messages.SUPPORT_TEXT,
    "help": default_messages.HELP_TEXT,
    "no_purchase": default_messages.NO_PURCHASE,
    "purchase_history_header": "**آخرین خریدهای شما**\n\n",
    "service_details": (
        "**{service_name}**\n\n"
        "نام اصلی اشتراک: **{original_title}**\n"
        "دسته‌بندی: **{category_key}**\n"
        "حجم کل: **{total_volume}**\n"
        "حجم مصرف‌شده: **{used_volume}**\n"
        "حجم باقی‌مانده: **{remaining_volume}**\n"
        "تاریخ انقضا: **{expiry_text}**\n"
        "زمان باقی‌مانده: **{remaining_time}**\n"
        "تعداد کانفیگ: **{config_count}**\n"
        "تاریخ خرید: **{purchased_at}**\n"
        "مبلغ پرداختی: **{price} تومان**"
    ),
    "rial_amount_prompt": (
        "**پرداخت ریالی (کارت‌به‌کارت)**\n\n"
        "مبلغی که می‌خواهید کیف پول شما شارژ شود را به تومان وارد کنید.\n"
        "حداقل پرداخت: **{minimum} تومان**"
    ),
    "rial_amount_invalid": "مبلغ معتبر نیست. حداقل مبلغ پرداخت ریالی **{minimum} تومان** است.",
    "rial_phone_prompt": (
        "**تایید شماره تماس**\n\n"
        "شماره اکانت تلگرام خودتان را با دکمه پایین به اشتراک بگذارید.\n"
        "فقط شماره ایران پذیرفته می‌شود."
    ),
    "rial_phone_invalid": (
        "شماره ارسال‌شده متعلق به اکانت شما نیست یا شماره ایران نیست.\n"
        "پرداخت ریالی برای این شماره قابل ادامه نیست؛ لطفا با {support_handle} تماس بگیرید."
    ),
    "rial_card_prompt": (
        "**شماره کارت مبدا**\n\n"
        "شماره کارت بانکی ۱۶ رقمی که واریز را از آن انجام می‌دهید وارد کنید."
    ),
    "rial_card_invalid": "شماره کارت معتبر نیست. شماره کارت مبدا را به‌صورت ۱۶ رقم وارد کنید.",
    "rial_payment_request": (
        "**درخواست ثبت پرداخت کارت‌به‌کارت**\n\n"
        "لطفاً متن زیر را به‌طور کامل کپی کرده و به آیدی زیر ارسال کنید:\n"
        "📩 {support_handle}\n\n"
        "```\n{copy_text}\n```\n"
        "📋 برای کپی، روی متن بالا یا دکمه کپی بزنید.\n\n"
        "🧾 کد پیگیری: `{tracking_code}`\n"
        "⚠️ لطفاً متن فوق را بدون هیچ تغییری به آیدی ذکرشده ارسال کنید.\n"
        "🚀 پس از تأیید پرداخت، کیف پول شما به‌صورت خودکار شارژ می‌شود."
    ),
    "rial_card_payment_instructions": (
        "**💳 کارت به کارت**\n\n"
        "شماره کارت:\n"
        "`{destination_card}`\n\n"
        "صاحب کارت: **{destination_holder}**\n\n"
        "مبلغ قابل پرداخت: **{amount} تومان**\n\n"
        "حتماً دقیقاً به همین مقدار واریز نمایید.\n"
        "در صورت واریز مبلغ غیر دقیق، مسئولیت تایید نشدن رسید بر عهده شما خواهد بود.\n\n"
        "پس از واریز، **پیام بعدی شما در همین چت به عنوان رسید پرداخت ثبت می‌شود.**\n"
        "لطفاً فقط تصویر رسید یا متن رسید را ارسال کنید.\n\n"
        "⏳ این پرداخت فقط تا **{valid_minutes} دقیقه** معتبر است.\n"
        "زمان پایان اعتبار: **{expires_at} به وقت تهران**"
    ),
    "rial_receipt_bot_start": (
        "**ارسال رسید پرداخت**\n\n"
        "درخواست شما آماده دریافت رسید است.\n"
        "مبلغ: **{amount} تومان**\n"
        "کد پیگیری: `{tracking_code}`\n\n"
        "لطفاً تصویر رسید یا متن رسید را همینجا ارسال کنید."
    ),
    "rial_receipt_received": (
        "✅ رسید شما دریافت شد و برای بررسی به ادمین ارسال شد.\n\n"
        "کد پیگیری: `{tracking_code}`\n"
        "پس از تایید، کیف پول شما به‌صورت خودکار شارژ می‌شود."
    ),
    "rial_receipt_approved": (
        "✅ رسید پرداخت شما تایید شد.\n\n"
        "مبلغ شارژ: **{amount} تومان**\n"
        "موجودی جدید: **{wallet_balance} تومان**"
    ),
    "rial_receipt_rejected": (
        "❌ رسید پرداخت شما رد شد.\n\n"
        "مبلغ درخواست: **{amount} تومان**\n"
        "کد پیگیری: `{tracking_code}`\n"
        "{reason_text}"
    ),
    "rial_receipt_expired": (
        "⏳ مهلت ارسال رسید این درخواست تمام شده است.\n\n"
        "لطفاً از کیف پول، درخواست پرداخت جدید ثبت کنید."
    ),
    "rial_receipt_admin_request": (
        "**درخواست واریز کارت‌به‌کارت**\n\n"
        "کاربر: **{user_name}**\n"
        "یوزرنیم: {username}\n"
        "آیدی عددی: `{telegram_id}`\n"
        "شماره موبایل: `{phone_number}`\n\n"
        "مبلغ: **{amount} تومان**\n"
        "شماره کارت مبدا: `{source_card}`\n"
        "کد پیگیری: `{tracking_code}`\n"
        "زمان ثبت: **{created_at}**\n\n"
        "رسید کاربر در پیام بعدی ارسال شده است."
    ),
    "hooshpay_amount_prompt": (
        "**درگاه هوش‌پی**\n\n"
        "مبلغی که می‌خواهید کیف پول شما شارژ شود را به تومان وارد کنید.\n"
        "این پرداخت آنی، بدون احراز و همراه با کارمزد درگاه است.\n\n"
        "حداقل پرداخت: **{minimum} تومان**"
    ),
    "hooshpay_amount_invalid": "مبلغ معتبر نیست. حداقل مبلغ پرداخت با هوش‌پی **{minimum} تومان** است.",
    "hooshpay_unavailable": (
        "درگاه هوش‌پی در حال حاضر قابل استفاده نیست.\n\n"
        "جزئیات: `{error}`"
    ),
    "hooshpay_invoice_created": (
        "**فاکتور هوش‌پی ساخته شد**\n\n"
        "مبلغ شارژ کیف پول: **{amount} تومان**\n"
        "مبلغ قابل پرداخت: **{payable_amount} تومان**\n"
        "کد پیگیری: `{tracking_code}`\n\n"
        "⏳ مهلت پرداخت تا ساعت **{expires_at} تهران** است.\n"
        "⚠️ حتماً مبلغ قابل پرداخت را دقیق واریز کنید؛ مسئولیت واریز مبلغ اشتباه یا کارت اشتباه با شماست.\n\n"
        "برای پرداخت، روی دکمه زیر بزنید. پس از تأیید پرداخت، کیف پول شما به‌صورت خودکار شارژ می‌شود."
    ),
    TARIFFS_MESSAGE_KEY: (
        '<tg-emoji emoji-id="4990387969408893849">⚡️</tg-emoji> <b>Phantom Express - فانتوم اکسپرس</b>\n'
        'لوکیشن آلمان <tg-emoji emoji-id="5420468891870571663">🇩🇪</tg-emoji>\n'
        'بدون محدودیت کاربر <tg-emoji emoji-id="5379694495291940508">✨</tg-emoji>\n'
        'یک‌ماهه\n\n'
        '<tg-emoji emoji-id="4999127510596715733">🟦</tg-emoji> 10 گیگ -&gt; 89 تومان\n'
        '<tg-emoji emoji-id="4999127510596715733">🟦</tg-emoji> 20 گیگ -&gt; 148 تومان\n'
        '<tg-emoji emoji-id="4999127510596715733">🟦</tg-emoji> 30 گیگ -&gt; 198 تومان\n'
        '<tg-emoji emoji-id="4999127510596715733">🟦</tg-emoji> 50 گیگ -&gt; 298 تومان\n'
        '<tg-emoji emoji-id="4999127510596715733">🟦</tg-emoji> 100 گیگ -&gt; 398 تومان\n\n'
        '<tg-emoji emoji-id="5780517739756000213">♾</tg-emoji> <b>Phantom Unlimited - فانتوم آنلیمیتد</b>\n'
        'لوکیشن آلمان <tg-emoji emoji-id="5420468891870571663">🇩🇪</tg-emoji>\n'
        'حجم نامحدود <tg-emoji emoji-id="5379694495291940508">✨</tg-emoji>\n'
        'یک‌ماهه\n\n'
        '<tg-emoji emoji-id="4999127510596715733">🟦</tg-emoji> 1 کاربره -&gt; 448 تومان\n'
        '<tg-emoji emoji-id="4999127510596715733">🟦</tg-emoji> 2 کاربره -&gt; 528 تومان\n'
        '<tg-emoji emoji-id="4999127510596715733">🟦</tg-emoji> 3 کاربره -&gt; 598 تومان\n\n'
        '<tg-emoji emoji-id="6030811868078018748">💎</tg-emoji> <b>Phantom No Limits - فانتوم نو لیمیت</b>\n'
        'مولتی لوکیشن\n'
        'بدون محدودیت تعداد کاربر <tg-emoji emoji-id="5379694495291940508">✨</tg-emoji>\n'
        'مدت زمان نامحدود <tg-emoji emoji-id="5379694495291940508">✨</tg-emoji>\n\n'
        '<tg-emoji emoji-id="4999127510596715733">🟦</tg-emoji> 10 گیگ -&gt; 160 تومان\n'
        '<tg-emoji emoji-id="4999127510596715733">🟦</tg-emoji> 20 گیگ -&gt; 300 تومان\n'
        '<tg-emoji emoji-id="4999127510596715733">🟦</tg-emoji> 30 گیگ -&gt; 400 تومان\n'
        '<tg-emoji emoji-id="4999127510596715733">🟦</tg-emoji> 50 گیگ -&gt; 500 تومان'
    ),
    "invalid_plan": "پلن انتخاب‌شده معتبر نیست. لطفا دوباره از منوی خرید انتخاب کنید.",
    "service_name_prompt": (
        "**نام دلخواه سرویس را وارد کنید**\n\n"
        "یک اسم کوتاه مثل علی، مهدی، احسان یا هر نامی که بعدا راحت پیدایش کنید بفرستید."
    ),
    "service_name_invalid": "نام سرویس باید بین ۱ تا ۶۰ کاراکتر باشد. لطفا یک نام کوتاه‌تر ارسال کنید.",
    "blocked_user": "حساب شما مسدود شده است.",
    "inactive_plan": "این پلن در حال حاضر فعال نیست.",
    "insufficient_balance": (
        "موجودی کیف پول کافی نیست.\n"
        "موجودی فعلی کیف پول: {wallet_balance} تومان\n"
        "مبلغ موردنیاز: {required_price} تومان"
    ),
    "plan_unavailable": "پلن {volume} گیگ فعلا ناموجود است.",
    "plan_sold_out": "پلن {volume} گیگ همین الان ناموجود شد. لطفا دوباره تلاش کنید.",
    "coupon_prompt": "کد تخفیف را ارسال کنید.",
    "coupon_invalid": "این کد تخفیف معتبر نیست یا برای حساب شما فعال نشده است.",
    "coupon_applied": (
        "کد تخفیف **{code}** با مقدار **{discount_text}** فعال شد.\n"
        "قیمت‌ها در منوی خرید با تخفیف نمایش داده می‌شوند."
    ),
    "coupon_cancelled": "عملیات لغو شد.",
    "referral_followup": "از منوی پایین می‌توانید به بخش‌های دیگر بروید.",
    "referral_share_text": (
        "سلام، من از فانتوم VPN استفاده می‌کنم.\n"
        "از لینک دعوت من وارد شو و سرویس‌هایت را راحت‌تر تهیه کن."
    ),
    "referral_commission_text": (
        "از هر خرید دوستانتان، **{commission_percent} درصد پورسانت** "
        "مستقیم به کیف پول شما اضافه می‌شود."
    ),
    "referral_user_identity": (
        "نام: {name}\n"
        "یوزرنیم: {username}\n"
        "آیدی عددی: {telegram_id}"
    ),
    "referral_join_notification": (
        "👥 یک کاربر جدید با لینک دعوت شما به جمع کاربران فانتوم هابز پیوست.\n\n"
        "{referred_identity}"
    ),
    "referral_commission_notification": (
        "🎁 پورسانت دعوت دوستان به کیف پول شما اضافه شد.\n\n"
        "نوع فعالیت زیرمجموعه: {source_label}\n"
        "مبلغ فعالیت: {base_amount} تومان\n"
        "پورسانت {percent}٪: {commission} تومان\n"
        "موجودی جدید شما: {wallet_balance} تومان\n\n"
        "مشخصات زیرمجموعه:\n"
        "{referred_identity}"
    ),
    "referral": (
        "**دعوت دوستان**\n\n"
        "لینک اختصاصی شما آماده است. هر کسی با این لینک وارد ربات شود به عنوان دعوت‌شده شما ثبت می‌شود.\n\n"
        "{commission_text}\n\n"
        "لینک قابل کلیک:\n[دعوت به فانتوم VPN]({link})\n\n"
        "لینک مستقیم:\n`{link}`\n\n"
        "تعداد ثبت‌نام با لینک شما: **{count} نفر**"
    ),
    "account_info": (
        "**اطلاعات حساب**\n\n"
        "آیدی عددی: `{telegram_id}`\n"
        "نام: {first_name}\n"
        "یوزرنیم: {username}\n"
        "موجودی کیف پول: **{wallet_balance} تومان**\n\n"
        "تعداد خریدها: **{total_count}**\n"
        "حجم خریداری‌شده: **{total_gb} گیگ**\n"
        "مبلغ کل خریدها: **{total_spent} تومان**\n"
        "ثبت‌نام با لینک دعوت شما: **{referral_count} نفر**"
    ),
    "purchase_history_item": (
        "نام سرویس: **{service_name}**\n"
        "حجم: {volume} گیگ | مبلغ: {price} تومان{discount}{coupon}\n"
        "زمان: {purchased_at}\n"
        "`{sub_link}`\n\n"
    ),
}


DEFAULT_MESSAGE_BUTTONS: tuple[dict, ...] = (
    {
        "message_key": "referral",
        "button_type": "inline_url",
        "text": "👥 دعوت دوستان",
        "payload": "{share_url}",
        "row": 0,
        "col": 0,
    },
    {
        "message_key": "referral",
        "button_type": "inline_copy",
        "text": "📋 کپی لینک دعوت",
        "payload": "{link}",
        "row": 1,
        "col": 0,
    },
    {
        "message_key": "rial_card_payment_instructions",
        "button_type": "inline_copy",
        "text": "📋 کپی شماره کارت",
        "payload": "{destination_card}",
        "row": 0,
        "col": 0,
    },
    {
        "message_key": "rial_card_payment_instructions",
        "button_type": "inline_copy",
        "text": "📋 کپی مبلغ تومان",
        "payload": "{amount_toman}",
        "row": 1,
        "col": 0,
    },
    {
        "message_key": "rial_card_payment_instructions",
        "button_type": "inline_copy",
        "text": "📋 کپی مبلغ ریال",
        "payload": "{amount_rial}",
        "row": 2,
        "col": 0,
    },
)

DEFAULT_MESSAGE_PARSE_MODES = {
    TARIFFS_MESSAGE_KEY: "HTML",
}


DEFAULT_CATEGORIES: tuple[CategoryDefinition, ...] = (
    CategoryDefinition("default", "سرویس‌های VPN", "🛡", STYLE_PRIMARY, 0, SHOP_BUTTON_CUSTOM_EMOJI_ID),
    CategoryDefinition(
        "unlimited",
        "Phantom Unlimited- فانتوم آنلیمیتد",
        None,
        STYLE_PRIMARY,
        2,
        "5780517739756000213",
    ),
)


DEFAULT_PLANS: tuple[PlanDefinition, ...] = (
    PlanDefinition(1, "1 گیگ", "📦", STYLE_SUCCESS, 0, SHOP_BUTTON_CUSTOM_EMOJI_ID, price=18818),
    PlanDefinition(2, "2 گیگ", "📦", STYLE_SUCCESS, 1, SHOP_BUTTON_CUSTOM_EMOJI_ID, price=420000),
    PlanDefinition(3, "3 گیگ", "📦", STYLE_SUCCESS, 2, SHOP_BUTTON_CUSTOM_EMOJI_ID, price=600000),
    PlanDefinition(5, "5 گیگ", "📦", STYLE_SUCCESS, 3, SHOP_BUTTON_CUSTOM_EMOJI_ID, price=950000),
    PlanDefinition(10, "10 گیگ", "📦", STYLE_SUCCESS, 4, SHOP_BUTTON_CUSTOM_EMOJI_ID, price=1800000),
    PlanDefinition(20, "20 گیگ", "📦", STYLE_SUCCESS, 5, SHOP_BUTTON_CUSTOM_EMOJI_ID, price=3200000),
)

OBSOLETE_CATEGORY_KEYS = {
    "___phantom_express_-_فانتوم_اکسپرس",
}


class ShopCustomizationService:
    @staticmethod
    def _deleted_button_key(menu: str, action: str) -> str:
        return f"deleted_shop_button:{menu}:{action}"

    @staticmethod
    def _message_button_marker_key(message_key: str, button_type: str, text: str) -> str:
        safe_key = re.sub(r"[^A-Za-z0-9_:-]+", "_", message_key).strip("_")[:120]
        safe_type = re.sub(r"[^A-Za-z0-9_:-]+", "_", button_type).strip("_")[:40]
        safe_text = re.sub(r"[^A-Za-z0-9_:-]+", "_", text).strip("_")[:120]
        return f"deleted_shop_message_button:{safe_key}:{safe_type}:{safe_text}"

    @staticmethod
    async def _migrate_legacy_tariffs_key(session: AsyncSession) -> None:
        legacy_message = (
            await session.execute(select(ShopMessage).where(ShopMessage.key == LEGACY_TARIFFS_MESSAGE_KEY))
        ).scalar_one_or_none()
        tariffs_message = (
            await session.execute(select(ShopMessage).where(ShopMessage.key == TARIFFS_MESSAGE_KEY))
        ).scalar_one_or_none()
        if legacy_message and not tariffs_message:
            legacy_message.key = TARIFFS_MESSAGE_KEY
        elif legacy_message and tariffs_message:
            await session.delete(legacy_message)

        legacy_buttons = (
            await session.execute(select(ShopButton).where(ShopButton.action == LEGACY_TARIFFS_MESSAGE_KEY))
        ).scalars().all()
        for button in legacy_buttons:
            button.action = TARIFFS_MESSAGE_KEY

        linked_messages = (
            await session.execute(
                select(ShopMessage).where(ShopMessage.response_button_url == LEGACY_TARIFFS_MESSAGE_KEY)
            )
        ).scalars().all()
        for message in linked_messages:
            message.response_button_url = TARIFFS_MESSAGE_KEY

    @staticmethod
    async def _remove_obsolete_defaults(session: AsyncSession) -> None:
        for category_key in OBSOLETE_CATEGORY_KEYS:
            plans = await session.execute(select(ShopPlan).where(ShopPlan.category_key == category_key))
            for plan in plans.scalars().all():
                await session.delete(plan)
            category = (
                await session.execute(select(ShopPlanCategory).where(ShopPlanCategory.key == category_key))
            ).scalar_one_or_none()
            if category:
                await session.delete(category)

    @staticmethod
    def _deleted_plan_key(volume_gb: int, category_key: str) -> str:
        return f"deleted_shop_plan:{_clean_key(category_key)}:{int(volume_gb)}"

    @staticmethod
    async def init_defaults(session: AsyncSession) -> None:
        await ShopCustomizationService._migrate_legacy_tariffs_key(session)
        await ShopCustomizationService._remove_obsolete_defaults(session)

        for key, text in DEFAULT_MESSAGES.items():
            result = await session.execute(select(ShopMessage).where(ShopMessage.key == key))
            message = result.scalar_one_or_none()
            if message is None:
                session.add(
                    ShopMessage(
                        key=key,
                        text=text,
                        parse_mode=DEFAULT_MESSAGE_PARSE_MODES.get(key, PARSE_MODE_MARKDOWN),
                    )
                )
                continue
            if key == "purchase_success":
                if "{service_name}" not in message.text:
                    message.text = _insert_after_heading(message.text, "نام سرویس: **{service_name}**\n")
                message.text = message.text.replace("{volume} گیگ", "{volume}")
            elif key == "purchase_history_item" and "{service_name}" not in message.text:
                message.text = "نام سرویس: **{service_name}**\n" + message.text
            elif key == "referral":
                old_commission_line = (
                    "از هر خرید دوستانتان، **۱۵ درصد پورسانت** مستقیم به کیف پول شما اضافه می‌شود."
                )
                if old_commission_line in message.text:
                    message.text = message.text.replace(old_commission_line, "{commission_text}")
                elif "{commission_text}" not in message.text:
                    message.text = message.text.replace("لینک قابل کلیک:", "{commission_text}\n\nلینک قابل کلیک:")
            elif key == "insufficient_balance" and "{wallet_balance}" not in message.text:
                message.text = message.text.replace(
                    "مبلغ موردنیاز:",
                    "موجودی فعلی کیف پول: {wallet_balance} تومان\n"
                    "مبلغ موردنیاز:",
                )
            elif key == "hooshpay_invoice_created":
                message.text = re.sub(r"^.*کارمزد.*\n?", "", message.text, flags=re.MULTILINE)
                if "{expires_at}" not in message.text:
                    message.text = message.text.replace(
                        "برای پرداخت، روی دکمه زیر بزنید.",
                        "⏳ مهلت پرداخت تا ساعت **{expires_at} تهران** است.\n"
                        "⚠️ حتماً مبلغ قابل پرداخت را دقیق واریز کنید؛ مسئولیت واریز مبلغ اشتباه یا کارت اشتباه با شماست.\n\n"
                        "برای پرداخت، روی دکمه زیر بزنید.",
                    )

        message_button_counts: dict[str, int] = {
            key: count
            for key, count in (
                await session.execute(
                    select(ShopMessageButton.message_key, func.count(ShopMessageButton.id))
                    .group_by(ShopMessageButton.message_key)
                )
            ).all()
        }
        for definition in DEFAULT_MESSAGE_BUTTONS:
            if message_button_counts.get(definition["message_key"], 0) > 0:
                continue
            marker_key = ShopCustomizationService._message_button_marker_key(
                definition["message_key"],
                definition["button_type"],
                definition["text"],
            )
            deleted_marker = (
                await session.execute(select(BotSetting).where(BotSetting.key == marker_key))
            ).scalar_one_or_none()
            if deleted_marker is not None:
                continue
            existing = (
                await session.execute(
                    select(ShopMessageButton).where(
                        ShopMessageButton.message_key == definition["message_key"],
                        ShopMessageButton.text == definition["text"],
                        ShopMessageButton.button_type == definition["button_type"],
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(ShopMessageButton(**definition))

        existing_button_count = (
            await session.execute(select(func.count(ShopButton.id)))
        ).scalar_one()
        deleted_button_count = (
            await session.execute(
                select(func.count(BotSetting.id)).where(BotSetting.key.like("deleted_shop_button:%"))
            )
        ).scalar_one()
        if existing_button_count == 0 and deleted_button_count == 0:
            for definition in DEFAULT_BUTTONS:
                session.add(
                    ShopButton(
                        action=definition.action,
                        menu=definition.menu,
                        text=definition.text,
                        emoji=definition.emoji,
                        premium_emoji_id=definition.premium_emoji_id,
                        premium_emoji_position=definition.emoji_position,
                        emoji_position=definition.emoji_position,
                        style=definition.style,
                        row=definition.row,
                        col=definition.col,
                    )
                )

        wallet_layout_key = "shop_wallet_layout:hooshpay_single_rows:v1"
        wallet_layout_migrated = (
            await session.execute(
                select(BotSetting).where(BotSetting.key == wallet_layout_key)
            )
        ).scalar_one_or_none()
        if wallet_layout_migrated is None and existing_button_count == 0:
            wallet_positions = {
                "charge_rial": (0, 0),
                "charge_crypto": (1, 0),
                "charge_hooshpay": (2, 0),
                "apply_coupon": (3, 0),
                "referrals": (3, 1),
                "support": (4, 0),
                "back_to_main": (5, 0),
            }
            result = await session.execute(select(ShopButton).where(ShopButton.menu == "shop_wallet"))
            for button in result.scalars().all():
                position = wallet_positions.get(button.action)
                if position:
                    button.row, button.col = position
            session.add(BotSetting(key=wallet_layout_key, value="true"))

        layout_migration_key = "shop_main_layout:restore_original:v2"
        layout_migrated = (
            await session.execute(
                select(BotSetting).where(BotSetting.key == layout_migration_key)
            )
        ).scalar_one_or_none()
        if layout_migrated is None and existing_button_count == 0:
            main_positions = {
                TARIFFS_MESSAGE_KEY: (0, 0),
                "buy_subscription": (0, 1),
                "trial_config": (1, 0),
                "wallet": (2, 0),
                "purchase_history": (2, 1),
                "referrals": (3, 0),
                "account_info": (3, 1),
                "support": (4, 0),
                "help": (4, 1),
            }
            result = await session.execute(
                select(ShopButton).where(ShopButton.menu == "shop_main")
            )
            for button in result.scalars().all():
                position = main_positions.get(button.action)
                if position:
                    button.row, button.col = position
            session.add(BotSetting(key=layout_migration_key, value="true"))

        for definition in DEFAULT_CATEGORIES:
            result = await session.execute(select(ShopPlanCategory).where(ShopPlanCategory.key == definition.key))
            if result.scalar_one_or_none() is None:
                session.add(
                    ShopPlanCategory(
                        key=definition.key,
                        title=definition.title,
                        emoji=definition.emoji,
                        premium_emoji_id=definition.premium_emoji_id,
                        emoji_position=definition.emoji_position,
                        style=definition.style,
                        display_order=definition.display_order,
                    )
                )

        for definition in DEFAULT_PLANS:
            deleted_marker = await session.execute(
                select(BotSetting.id).where(
                    BotSetting.key
                    == ShopCustomizationService._deleted_plan_key(
                        definition.volume_gb,
                        definition.category_key,
                    )
                )
            )
            if deleted_marker.scalar_one_or_none() is not None:
                continue
            result = await session.execute(
                select(ShopPlan).where(
                    ShopPlan.volume_gb == definition.volume_gb,
                    ShopPlan.category_key == definition.category_key,
                )
            )
            plan = result.scalar_one_or_none()
            price_result = await session.execute(select(Price).where(Price.volume_gb == definition.volume_gb))
            price_row = price_result.scalar_one_or_none()
            if plan is None:
                session.add(
                    ShopPlan(
                        volume_gb=definition.volume_gb,
                        title=definition.title,
                        price=definition.price if definition.price is not None else (price_row.price if price_row else None),
                        emoji=definition.emoji,
                        premium_emoji_id=definition.premium_emoji_id,
                        category_key=definition.category_key,
                        emoji_position=definition.emoji_position,
                        style=definition.style,
                        display_order=definition.display_order,
                    )
                )
            elif plan.price is None:
                plan.price = definition.price if definition.price is not None else (price_row.price if price_row else None)

        existing_plans = await session.execute(select(ShopPlan))
        for plan in existing_plans.scalars().all():
            if plan.price is None:
                price_result = await session.execute(select(Price).where(Price.volume_gb == plan.volume_gb))
                price_row = price_result.scalar_one_or_none()
                if price_row:
                    plan.price = price_row.price
        await session.commit()

    @staticmethod
    async def reset_defaults(session: AsyncSession) -> None:
        messages = await session.execute(select(ShopMessage))
        for message in messages.scalars().all():
            await session.delete(message)

        message_buttons = await session.execute(select(ShopMessageButton))
        for button in message_buttons.scalars().all():
            await session.delete(button)

        buttons = await session.execute(select(ShopButton))
        for button in buttons.scalars().all():
            await session.delete(button)

        plans = await session.execute(select(ShopPlan))
        for plan in plans.scalars().all():
            await session.delete(plan)

        categories = await session.execute(select(ShopPlanCategory))
        for category in categories.scalars().all():
            await session.delete(category)

        deleted_markers = await session.execute(
            select(BotSetting).where(
                or_(
                    BotSetting.key.like("deleted_shop_plan:%"),
                    BotSetting.key.like("deleted_shop_button:%"),
                    BotSetting.key.like("deleted_shop_message_button:%"),
                    BotSetting.key.like("shop_%_layout:%"),
                )
            )
        )
        for marker in deleted_markers.scalars().all():
            await session.delete(marker)

        await session.flush()
        await ShopCustomizationService.init_defaults(session)

    @staticmethod
    async def list_messages(session: AsyncSession) -> list[ShopMessage]:
        result = await session.execute(select(ShopMessage).order_by(ShopMessage.id))
        return list(result.scalars().all())

    @staticmethod
    async def list_message_buttons(session: AsyncSession, message_key: str | None = None) -> list[ShopMessageButton]:
        stmt = select(ShopMessageButton)
        if message_key:
            stmt = stmt.where(ShopMessageButton.message_key == message_key)
        result = await session.execute(
            stmt.order_by(ShopMessageButton.message_key, ShopMessageButton.row, ShopMessageButton.col, ShopMessageButton.id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create_message_button(
        session: AsyncSession,
        *,
        message_key: str,
        button_type: str,
        text: str,
        payload: str | None = None,
        style: str | None = None,
        premium_emoji_id: str | None = None,
        source_button_id: int | None = None,
        row: int = 0,
        col: int = 0,
    ) -> ShopMessageButton | None:
        if not await ShopCustomizationService.get_message_row(session, message_key):
            return None
        button = ShopMessageButton(
            message_key=message_key,
            button_type=button_type,
            text=text,
            payload=payload,
            style=style,
            premium_emoji_id=premium_emoji_id,
            source_button_id=source_button_id,
            row=max(0, int(row)),
            col=max(0, int(col)),
        )
        session.add(button)
        await session.commit()
        return button

    @staticmethod
    async def delete_message_button(session: AsyncSession, button_id: int) -> bool:
        button = await session.get(ShopMessageButton, button_id)
        if button is None:
            return False
        marker_key = ShopCustomizationService._message_button_marker_key(
            button.message_key,
            button.button_type,
            button.text,
        )
        marker = (
            await session.execute(select(BotSetting).where(BotSetting.key == marker_key))
        ).scalar_one_or_none()
        if marker is None:
            session.add(BotSetting(key=marker_key, value="1"))
        else:
            marker.value = "1"
            marker.updated_at = datetime.now(timezone.utc)
        await session.delete(button)
        await session.commit()
        return True

    @staticmethod
    async def update_message_button(session: AsyncSession, button_id: int, **values) -> ShopMessageButton | None:
        button = await session.get(ShopMessageButton, button_id)
        if button is None:
            return None
        allowed = {
            "button_type",
            "text",
            "payload",
            "style",
            "premium_emoji_id",
            "source_button_id",
            "row",
            "col",
            "is_enabled",
        }
        for field, value in values.items():
            if field not in allowed:
                continue
            if field in {"row", "col"} and value is not None:
                value = max(0, int(value))
            setattr(button, field, value)
        button.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return button

    @staticmethod
    async def get_message_button(session: AsyncSession, button_id: int) -> ShopMessageButton | None:
        return await session.get(ShopMessageButton, button_id)

    @staticmethod
    async def get_message_row(session: AsyncSession, key: str) -> ShopMessage | None:
        result = await session.execute(select(ShopMessage).where(ShopMessage.key == key))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_message_by_id(session: AsyncSession, message_id: int) -> ShopMessage | None:
        result = await session.execute(select(ShopMessage).where(ShopMessage.id == message_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_message(
        session: AsyncSession,
        key: str,
        text: str,
        parse_mode: str = PARSE_MODE_MARKDOWN,
        photo_file_id: str | None = None,
    ) -> ShopMessage | None:
        message = await ShopCustomizationService.get_message_row(session, key)
        if not message:
            return None
        message.text = text
        message.parse_mode = parse_mode
        message.photo_file_id = photo_file_id
        message.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return message

    @staticmethod
    async def update_message_settings(session: AsyncSession, key: str, **values) -> ShopMessage | None:
        message = await ShopCustomizationService.get_message_row(session, key)
        if not message:
            return None
        allowed = {
            "premium_emoji_id",
            "premium_emoji_position",
            "photo_file_id",
            "response_button_type",
            "response_button_text",
            "response_button_url",
            "response_button_style",
            "response_button_premium_emoji_id",
            "response_button_source_id",
        }
        for field, value in values.items():
            if field in allowed:
                setattr(message, field, value)
        message.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return message

    @staticmethod
    async def list_buttons(session: AsyncSession, menu: str | None = None) -> list[ShopButton]:
        stmt = select(ShopButton)
        if menu:
            stmt = stmt.where(ShopButton.menu == menu)
        result = await session.execute(stmt.order_by(ShopButton.menu, ShopButton.row, ShopButton.col, ShopButton.id))
        return list(result.scalars().all())

    @staticmethod
    async def get_button(session: AsyncSession, button_id: int) -> ShopButton | None:
        result = await session.execute(select(ShopButton).where(ShopButton.id == button_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_button(session: AsyncSession, button_id: int, **values) -> ShopButton | None:
        button = await ShopCustomizationService.get_button(session, button_id)
        if not button:
            return None

        allowed = {"text", "emoji", "premium_emoji_id", "premium_emoji_position", "emoji_position", "style", "row", "col", "is_enabled"}
        for key, value in values.items():
            if key in allowed:
                setattr(button, key, value)
        button.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return button

    @staticmethod
    async def delete_button(session: AsyncSession, button_id: int) -> bool:
        button = await ShopCustomizationService.get_button(session, button_id)
        if not button:
            return False
        deleted_key = ShopCustomizationService._deleted_button_key(button.menu, button.action)
        existing_marker = (
            await session.execute(select(BotSetting).where(BotSetting.key == deleted_key))
        ).scalar_one_or_none()
        if existing_marker is None:
            session.add(BotSetting(key=deleted_key, value="true"))
        if button.action.startswith("custom_message:"):
            message = await ShopCustomizationService.get_message_row(session, button.action)
            if message:
                await session.delete(message)
        await session.delete(button)
        await session.commit()
        return True

    @staticmethod
    async def create_custom_button(
        session: AsyncSession,
        menu: str,
        variable_name: str,
        text: str,
        message_text: str,
    ) -> ShopButton:
        variable_name = clean_custom_variable_name(variable_name)
        if not variable_name:
            raise ValueError("invalid_variable_name")
        buttons = await ShopCustomizationService.list_buttons(session, menu)
        row = max((button.row for button in buttons), default=-1) + 1
        action = custom_message_action(menu, variable_name)
        existing_message = await ShopCustomizationService.get_message_row(session, action)
        existing_button = (
            await session.execute(select(ShopButton.id).where(ShopButton.action == action, ShopButton.menu == menu))
        ).scalar_one_or_none()
        if existing_message or existing_button:
            raise ValueError("duplicate_variable_name")
        message = ShopMessage(key=action, text=message_text, parse_mode=PARSE_MODE_MARKDOWN)
        button = ShopButton(
            action=action,
            menu=menu,
            text=text,
            emoji="✨",
            premium_emoji_id=SHOP_BUTTON_CUSTOM_EMOJI_ID,
            style=STYLE_PRIMARY,
            row=row,
            col=0,
            is_enabled=True,
        )
        session.add(message)
        session.add(button)
        await session.commit()
        return button

    @staticmethod
    async def list_plans(session: AsyncSession, active_only: bool = False) -> list[ShopPlan]:
        stmt = select(ShopPlan)
        if active_only:
            stmt = stmt.where(ShopPlan.is_active.is_(True))
        result = await session.execute(stmt.order_by(ShopPlan.category_key, ShopPlan.display_order, ShopPlan.volume_gb))
        return list(result.scalars().all())

    @staticmethod
    async def list_categories(session: AsyncSession, active_only: bool = False) -> list[ShopPlanCategory]:
        stmt = select(ShopPlanCategory)
        if active_only:
            stmt = stmt.where(ShopPlanCategory.is_active == True)
        result = await session.execute(stmt.order_by(ShopPlanCategory.display_order, ShopPlanCategory.key))
        return list(result.scalars().all())

    @staticmethod
    async def get_category(session: AsyncSession, key: str) -> ShopPlanCategory | None:
        result = await session.execute(select(ShopPlanCategory).where(ShopPlanCategory.key == key))
        return result.scalar_one_or_none()

    @staticmethod
    async def ensure_category(session: AsyncSession, key: str, title: str | None = None) -> ShopPlanCategory:
        key = _clean_key(key)
        category = await ShopCustomizationService.get_category(session, key)
        if category:
            return category
        current = await ShopCustomizationService.list_categories(session)
        category = ShopPlanCategory(
            key=key,
            title=title or key,
            emoji="🧩",
            premium_emoji_id=SHOP_BUTTON_CUSTOM_EMOJI_ID,
            style=STYLE_PRIMARY,
            display_order=len(current),
            is_active=True,
        )
        session.add(category)
        await session.flush()
        return category

    @staticmethod
    async def update_category(session: AsyncSession, key: str, **values) -> ShopPlanCategory | None:
        category = await ShopCustomizationService.get_category(session, key)
        if not category:
            return None
        allowed = {
            "title",
            "emoji",
            "premium_emoji_id",
            "emoji_position",
            "style",
            "provision_panel_key",
            "provision_enabled",
            "display_order",
            "is_active",
        }
        for field, value in values.items():
            if field in allowed:
                setattr(category, field, value)
        category.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return category

    @staticmethod
    async def category_usage(session: AsyncSession, key: str) -> tuple[int, int]:
        plans = await session.execute(select(ShopPlan).where(ShopPlan.category_key == key))
        configs = await session.execute(select(Config).where(Config.category_key == key))
        return len(plans.scalars().all()), len(configs.scalars().all())

    @staticmethod
    async def delete_category(session: AsyncSession, key: str) -> bool:
        if key == "default":
            return False
        category = await ShopCustomizationService.get_category(session, key)
        if not category:
            return False
        await session.delete(category)
        await session.commit()
        return True

    @staticmethod
    async def get_plan(session: AsyncSession, plan_id: int) -> ShopPlan | None:
        result = await session.execute(select(ShopPlan).where(ShopPlan.id == plan_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_plan_by_product(session: AsyncSession, volume_gb: int, category_key: str) -> ShopPlan | None:
        result = await session.execute(
            select(ShopPlan)
            .where(
                ShopPlan.volume_gb == volume_gb,
                ShopPlan.category_key == _clean_key(category_key),
            )
            .order_by(ShopPlan.id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert_plan(
        session: AsyncSession,
        *,
        volume_gb: int,
        title: str,
        price: int | None = None,
        category_key: str = "default",
        emoji: str | None = "📦",
        style: str | None = STYLE_SUCCESS,
    ) -> ShopPlan:
        category_key = _clean_key(category_key)
        deleted_marker = await session.execute(
            select(BotSetting).where(
                BotSetting.key
                == ShopCustomizationService._deleted_plan_key(volume_gb, category_key)
            )
        )
        marker = deleted_marker.scalar_one_or_none()
        if marker:
            await session.delete(marker)
        await ShopCustomizationService.ensure_category(session, category_key)
        plan = await ShopCustomizationService.get_plan_by_product(session, volume_gb, category_key)
        if not plan:
            current = await ShopCustomizationService.list_plans(session)
            plan = ShopPlan(
                volume_gb=volume_gb,
                title=title,
                price=price,
                emoji=emoji,
                premium_emoji_id=SHOP_BUTTON_CUSTOM_EMOJI_ID,
                category_key=category_key,
                style=style,
                display_order=len(current),
                is_active=True,
            )
            session.add(plan)
        else:
            plan.title = title
            if price is not None:
                plan.price = price
            plan.emoji = emoji
            plan.style = style
            plan.is_active = True
            plan.updated_at = datetime.now(timezone.utc)

        await session.commit()
        return plan

    @staticmethod
    async def create_plan(
        session: AsyncSession,
        *,
        volume_gb: int,
        title: str,
        price: int | None = None,
        category_key: str = "default",
        emoji: str | None = "📦",
        style: str | None = STYLE_SUCCESS,
    ) -> ShopPlan:
        category_key = _clean_key(category_key)
        await ShopCustomizationService.ensure_category(session, category_key)
        current = await ShopCustomizationService.list_plans(session)
        plan = ShopPlan(
            volume_gb=volume_gb,
            title=title,
            price=price,
            emoji=emoji,
            premium_emoji_id=SHOP_BUTTON_CUSTOM_EMOJI_ID,
            category_key=category_key,
            style=style,
            display_order=len(current),
            is_active=True,
        )
        session.add(plan)
        await session.commit()
        return plan

    @staticmethod
    async def update_plan(session: AsyncSession, plan_id: int, **values) -> ShopPlan | None:
        plan = await ShopCustomizationService.get_plan(session, plan_id)
        if not plan:
            return None

        allowed = {
            "title",
            "price",
            "emoji",
            "premium_emoji_id",
            "premium_emoji_position",
            "emoji_position",
            "category_key",
            "style",
            "display_order",
            "duration_days",
            "provision_volume_gb",
            "provision_duration_days",
            "provision_time_mode",
            "subscription_device_limit",
            "show_subscription_configs",
            "name_prefix",
            "provision_mode",
            "provision_panel_key",
            "provision_enabled",
            "renew_enabled",
            "is_active",
        }
        category_title = values.get("category_title")
        for key, value in values.items():
            if key == "category_title":
                continue
            if key in allowed:
                if key == "category_key":
                    value = _clean_key(value)
                    await ShopCustomizationService.ensure_category(session, value, category_title)
                setattr(plan, key, value)
        plan.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return plan

    @staticmethod
    async def delete_plan(session: AsyncSession, plan_id: int) -> dict | None:
        plan = await ShopCustomizationService.get_plan(session, plan_id)
        if not plan:
            return None

        inventory_result = await session.execute(
            select(Config).where(
                or_(
                    Config.shop_plan_id == plan.id,
                    and_(
                        Config.shop_plan_id.is_(None),
                        Config.volume_gb == plan.volume_gb,
                        Config.category_key == plan.category_key,
                    ),
                ),
                Config.is_sold.is_(False),
            )
        )
        unsold_configs = list(inventory_result.scalars().all())

        rules_result = await session.execute(
            select(ReferralRewardRule).where(
                ReferralRewardRule.shop_plan_id == plan.id,
            )
        )
        reward_rules = list(rules_result.scalars().all())
        for rule in reward_rules:
            rule.is_active = False
            rule.shop_plan_id = None
            rule.updated_at = datetime.now(timezone.utc)

        for config in unsold_configs:
            await session.delete(config)
        marker_key = ShopCustomizationService._deleted_plan_key(
            plan.volume_gb,
            plan.category_key,
        )
        marker_result = await session.execute(
            select(BotSetting).where(BotSetting.key == marker_key)
        )
        if marker_result.scalar_one_or_none() is None:
            session.add(BotSetting(key=marker_key, value="1"))
        await session.delete(plan)
        await session.commit()
        return {
            "title": plan.title,
            "removed_inventory": len(unsold_configs),
            "disabled_reward_rules": len(reward_rules),
        }

    @staticmethod
    async def get_message(
        session: AsyncSession,
        key: str,
        *,
        escape_markdown_values: bool = False,
        **values,
    ) -> RenderedMessage:
        result = await session.execute(
            select(ShopMessage).where(ShopMessage.key == key, ShopMessage.is_active == True)
        )
        message = result.scalar_one_or_none()
        template = message.text if message else DEFAULT_MESSAGES[key]
        parse_mode = message.parse_mode if message and message.parse_mode else PARSE_MODE_MARKDOWN
        if values:
            rendered, parse_mode = _render_template_with_values(
                template,
                parse_mode,
                values,
                escape_markdown_values=escape_markdown_values,
            )
        else:
            rendered = template
        premium_id = message.premium_emoji_id if message else None
        position = message.premium_emoji_position if message else "none"
        photo_file_id = message.photo_file_id if message else None
        if not _is_valid_custom_emoji_id(premium_id) or position == "none":
            return RenderedMessage(rendered, parse_mode, photo_file_id)

        custom_emoji = f'<tg-emoji emoji-id="{premium_id}">⭐</tg-emoji>'
        rendered_html = rendered if parse_mode == "HTML" else _markdown_to_telegram_html(rendered)
        if position == "right":
            rendered_html = f"{rendered_html} {custom_emoji}"
        else:
            rendered_html = f"{custom_emoji} {rendered_html}"
        return RenderedMessage(rendered_html, "HTML", photo_file_id)

    @staticmethod
    async def main_menu_keyboard(session: AsyncSession) -> ReplyKeyboardMarkup:
        return await ShopCustomizationService._menu_keyboard(session, "shop_main")

    @staticmethod
    async def wallet_keyboard(session: AsyncSession) -> ReplyKeyboardMarkup:
        return await ShopCustomizationService._menu_keyboard(session, "shop_wallet")

    @staticmethod
    async def back_keyboard(session: AsyncSession) -> ReplyKeyboardMarkup:
        return await ShopCustomizationService._menu_keyboard(session, "shop_back")

    @staticmethod
    async def buy_volume_keyboard(session: AsyncSession, prices: dict | None = None) -> ReplyKeyboardMarkup:
        categories = await ShopCustomizationService.active_categories_with_plans(session)
        if categories:
            rows: dict[int, list[KeyboardButton]] = {}
            for index, category in enumerate(categories):
                row = category.display_order if category.display_order is not None else index
                rows.setdefault(row, []).append(
                    ShopCustomizationService._keyboard_button(
                        ShopCustomizationService.category_label(category),
                        style=category.style,
                        premium_emoji_id=category.premium_emoji_id,
                    )
                )
            back_buttons = await ShopCustomizationService._buttons_for_menu(session, "shop_buy")
            if back_buttons:
                rows[max(rows.keys(), default=-1) + 1] = [ShopCustomizationService._button_from_model(button) for button in back_buttons]
            return _reply_keyboard([rows[key] for key in sorted(rows)])

        return await ShopCustomizationService.buy_category_keyboard(session, "default", prices)

    @staticmethod
    def duration_options_for_category(category_key: str) -> list[tuple[str, str]]:
        options = {
            "express": [("یک‌ماهه", "monthly")],
            "unlimited": [("یک‌ماهه", "monthly")],
            "nolimits": [("نامحدود", "unlimited")],
        }
        return options.get((category_key or "").strip().lower(), [])

    @staticmethod
    async def buy_duration_keyboard(session: AsyncSession, category_key: str) -> ReplyKeyboardMarkup:
        rows: list[list[KeyboardButton]] = []
        for label, _key in ShopCustomizationService.duration_options_for_category(category_key):
            rows.append([ShopCustomizationService._keyboard_button(label, style=STYLE_PRIMARY)])

        back_buttons = await ShopCustomizationService._buttons_for_menu(session, "shop_buy")
        if back_buttons:
            rows.append([ShopCustomizationService._button_from_model(button) for button in back_buttons])
        return _reply_keyboard(rows)

    @staticmethod
    def duration_key_for_text(category_key: str | None, text: str) -> str | None:
        if not category_key:
            return None
        for label, key in ShopCustomizationService.duration_options_for_category(category_key):
            if label == text:
                return key
        return None

    @staticmethod
    async def buy_category_keyboard(session: AsyncSession, category_key: str, prices: dict | None = None) -> ReplyKeyboardMarkup:
        if not prices:
            prices = {}

        plans = await ShopCustomizationService.get_active_plans(session, category_key)
        rows: dict[int, list[KeyboardButton]] = {}
        for index, plan in enumerate(plans):
            if plan.id not in prices:
                continue
            row = index
            rows.setdefault(row, []).append(ShopCustomizationService._keyboard_button(
                ShopCustomizationService.plan_label(plan, prices[plan.id]),
                style=plan.style,
                premium_emoji_id=plan.premium_emoji_id,
            ))

        back_buttons = await ShopCustomizationService._buttons_for_menu(session, "shop_buy")
        if back_buttons:
            rows[max(rows.keys(), default=-1) + 1] = [ShopCustomizationService._button_from_model(button) for button in back_buttons]

        return _reply_keyboard([rows[key] for key in sorted(rows)])

    @staticmethod
    async def active_categories_with_plans(session: AsyncSession) -> list[ShopPlanCategory]:
        categories = await ShopCustomizationService.list_categories(session, active_only=True)
        plans = await ShopCustomizationService.get_active_plans(session)
        plan_categories = {plan.category_key for plan in plans}
        filtered = [category for category in categories if category.key in plan_categories]
        if filtered:
            return filtered
        default = await ShopCustomizationService.ensure_category(session, "default", "سرویس‌های VPN")
        await session.commit()
        return [default]

    @staticmethod
    async def category_for_text(session: AsyncSession, text: str) -> str | None:
        for category in await ShopCustomizationService.active_categories_with_plans(session):
            if ShopCustomizationService.category_label(category) == text:
                return category.key
        return None

    @staticmethod
    async def action_for_text(session: AsyncSession, text: str) -> str | None:
        result = await session.execute(
            select(ShopButton).where(ShopButton.is_enabled == True)
        )
        for button in result.scalars().all():
            if ShopCustomizationService.button_label(button) == text:
                return button.action

        persisted_count = (
            await session.execute(select(func.count(ShopButton.id)))
        ).scalar_one()
        deleted_count = (
            await session.execute(
                select(func.count(BotSetting.id)).where(BotSetting.key.like("deleted_shop_button:%"))
            )
        ).scalar_one()
        if persisted_count == 0 and deleted_count == 0:
            for definition in DEFAULT_BUTTONS:
                label = ShopCustomizationService.definition_label(definition)
                if label == text:
                    return definition.action
        return None

    @staticmethod
    async def plan_for_text(session: AsyncSession, text: str, prices: dict, category_key: str | None = None) -> int | None:
        plans = await ShopCustomizationService.get_active_plans(session, category_key)
        for plan in plans:
            price = prices.get(plan.id)
            if price is None:
                continue
            if ShopCustomizationService.plan_label(plan, price) == text:
                return plan.id
        return None

    @staticmethod
    async def get_active_plans(session: AsyncSession, category_key: str | None = None) -> list[ShopPlan]:
        stmt = select(ShopPlan).where(ShopPlan.is_active == True)
        if category_key:
            stmt = stmt.where(ShopPlan.category_key == category_key)
        result = await session.execute(stmt.order_by(ShopPlan.display_order, ShopPlan.volume_gb))
        plans = list(result.scalars().all())
        if plans:
            return plans

        prices_result = await session.execute(select(Price).order_by(Price.volume_gb))
        volumes = [price.volume_gb for price in prices_result.scalars().all()]
        if not volumes:
            volumes = [definition.volume_gb for definition in DEFAULT_PLANS]

        defaults = {definition.volume_gb: definition for definition in DEFAULT_PLANS}
        return [
            ShopPlan(
                volume_gb=volume,
                title=defaults.get(volume, PlanDefinition(volume, f"{volume} گیگ", "📦", STYLE_SUCCESS, volume)).title,
                emoji=defaults.get(volume, PlanDefinition(volume, f"{volume} گیگ", "📦", STYLE_SUCCESS, volume)).emoji,
                premium_emoji_id=SHOP_BUTTON_CUSTOM_EMOJI_ID,
                style=STYLE_SUCCESS,
                display_order=index,
            )
            for index, volume in enumerate(volumes)
        ]

    @staticmethod
    async def _menu_keyboard(session: AsyncSession, menu: str) -> ReplyKeyboardMarkup:
        buttons = await ShopCustomizationService._buttons_for_menu(session, menu)
        if not buttons:
            persisted_count = (
                await session.execute(
                    select(func.count(ShopButton.id)).where(ShopButton.menu == menu)
                )
            ).scalar_one()
            deleted_count = (
                await session.execute(
                    select(func.count(BotSetting.id)).where(
                        BotSetting.key.like(f"deleted_shop_button:{menu}:%")
                    )
                )
            ).scalar_one()
            if persisted_count == 0 and deleted_count == 0:
                buttons = ShopCustomizationService._default_buttons_for_menu(menu)

        rows: dict[int, list[ShopButton | ButtonDefinition]] = {}
        for button in buttons:
            rows.setdefault(button.row, []).append(button)

        keyboard_rows = []
        for row_index in sorted(rows):
            keyboard_rows.append([
                ShopCustomizationService._button_from_any(button)
                for button in sorted(rows[row_index], key=lambda item: item.col)
            ])
        return _reply_keyboard(keyboard_rows)

    @staticmethod
    async def _buttons_for_menu(session: AsyncSession, menu: str) -> list[ShopButton]:
        result = await session.execute(
            select(ShopButton)
            .where(ShopButton.menu == menu, ShopButton.is_enabled == True)
            .order_by(ShopButton.row, ShopButton.col)
        )
        return list(result.scalars().all())

    @staticmethod
    def _default_buttons_for_menu(menu: str) -> list[ButtonDefinition]:
        return [definition for definition in DEFAULT_BUTTONS if definition.menu == menu]

    @staticmethod
    def _button_from_any(button: ShopButton | ButtonDefinition) -> KeyboardButton:
        if isinstance(button, ShopButton):
            return ShopCustomizationService._button_from_model(button)
        return ShopCustomizationService._keyboard_button(
            ShopCustomizationService.definition_label(button),
            style=button.style,
            premium_emoji_id=button.premium_emoji_id,
        )

    @staticmethod
    def _button_from_model(button: ShopButton) -> KeyboardButton:
        return ShopCustomizationService._keyboard_button(
            ShopCustomizationService.button_label(button),
            style=button.style,
            premium_emoji_id=button.premium_emoji_id,
        )

    @staticmethod
    def _keyboard_button(text: str, *, style: str | None = None, premium_emoji_id: str | None = None) -> KeyboardButton:
        api_kwargs = {}
        if style:
            api_kwargs["style"] = style
        if _is_valid_custom_emoji_id(premium_emoji_id):
            api_kwargs["icon_custom_emoji_id"] = str(premium_emoji_id).strip()
        try:
            return KeyboardButton(text=text, api_kwargs=api_kwargs or None)
        except TypeError:
            return KeyboardButton(text=text)

    @staticmethod
    def button_label(button: ShopButton) -> str:
        return _join_emoji(button.emoji, button.text, button.emoji_position)

    @staticmethod
    def definition_label(definition: ButtonDefinition) -> str:
        return _join_emoji(definition.emoji, definition.text, definition.emoji_position)

    @staticmethod
    def plan_label(plan: ShopPlan, price_value) -> str:
        if isinstance(price_value, tuple):
            final_price, discount = price_value
            label = f"{_join_emoji(plan.emoji, plan.title, plan.emoji_position)} | {final_price:,} تومان"
            if discount:
                label += f" | تخفیف {discount:,}"
            return label
        return f"{_join_emoji(plan.emoji, plan.title, plan.emoji_position)} | {price_value:,} تومان"

    @staticmethod
    def category_label(category: ShopPlanCategory) -> str:
        return _join_emoji(category.emoji, category.title, category.emoji_position)

    @staticmethod
    async def message_reply_markup(
        session: AsyncSession,
        key: str,
        *,
        fallback_markup=None,
        default_url: str | None = None,
        copy_text: str | None = None,
        context: dict[str, object] | None = None,
    ):
        context = context or {}
        custom_buttons = [
            button for button in await ShopCustomizationService.list_message_buttons(session, key)
            if button.is_enabled
        ]
        if custom_buttons:
            rows: dict[int, list[tuple[int, InlineKeyboardButton]]] = {}
            for button in custom_buttons:
                rendered = await ShopCustomizationService._render_message_button(
                    session,
                    button,
                    default_url=default_url,
                    copy_text=copy_text,
                    context=context,
                )
                if rendered is None:
                    continue
                rows.setdefault(button.row, []).append((button.col, rendered))
            keyboard_rows = [
                [item for _, item in sorted(items, key=lambda value: value[0])]
                for _, items in sorted(rows.items(), key=lambda value: value[0])
            ]
            if keyboard_rows:
                return InlineKeyboardMarkup(keyboard_rows)

        message = await ShopCustomizationService.get_message_row(session, key)
        button_type = (message.response_button_type if message else "text") or "text"
        source_button = None
        if message and message.response_button_source_id:
            source_button = await ShopCustomizationService.get_button(session, message.response_button_source_id)
        button_text = (
            (message.response_button_text if message else None)
            or (ShopCustomizationService.button_label(source_button) if source_button else None)
            or "ادامه"
        )
        payload = (message.response_button_url if message else None) or default_url
        style = (message.response_button_style if message else None) or (source_button.style if source_button else None)
        premium_emoji_id = (
            (message.response_button_premium_emoji_id if message else None)
            or (source_button.premium_emoji_id if source_button else None)
        )
        api_kwargs = {}
        if style:
            api_kwargs["style"] = style
        if _is_valid_custom_emoji_id(premium_emoji_id):
            api_kwargs["icon_custom_emoji_id"] = str(premium_emoji_id).strip()
        if button_type == "inline_copy":
            copy_payload = payload or copy_text
            if not copy_payload:
                return fallback_markup
            api_kwargs["copy_text"] = {"text": copy_payload}
            return InlineKeyboardMarkup(
                [[InlineKeyboardButton(button_text, api_kwargs=api_kwargs)]]
            )
        if button_type == "inline_url" and payload and payload.startswith(("http://", "https://", "tg://")):
            return InlineKeyboardMarkup([[InlineKeyboardButton(button_text, url=payload, api_kwargs=api_kwargs or None)]])
        if button_type == "inline_action" and source_button:
            return InlineKeyboardMarkup(
                [[InlineKeyboardButton(
                    button_text,
                    callback_data=f"shop_response:{message.id}",
                    api_kwargs=api_kwargs or None,
                )]]
            )
        if button_type == "reply_keyboard":
            if source_button:
                return _reply_keyboard([[ShopCustomizationService._button_from_model(source_button)]])
            return fallback_markup
        return fallback_markup

    @staticmethod
    def _render_template(value: str | None, context: dict[str, object]) -> str | None:
        if value is None:
            return None
        result = str(value)
        for key, replacement in context.items():
            result = result.replace("{" + key + "}", str(replacement))
        return result

    @staticmethod
    async def _render_message_button(
        session: AsyncSession,
        button: ShopMessageButton,
        *,
        default_url: str | None = None,
        copy_text: str | None = None,
        context: dict[str, object] | None = None,
    ) -> InlineKeyboardButton | None:
        context = context or {}
        source_button = None
        if button.source_button_id:
            source_button = await ShopCustomizationService.get_button(session, button.source_button_id)
        button_text = ShopCustomizationService._render_template(button.text, context) or "ادامه"
        payload = ShopCustomizationService._render_template(button.payload, context) or default_url
        style = button.style or (source_button.style if source_button else None)
        premium_emoji_id = button.premium_emoji_id or (source_button.premium_emoji_id if source_button else None)
        api_kwargs = {}
        if style:
            api_kwargs["style"] = style
        if _is_valid_custom_emoji_id(premium_emoji_id):
            api_kwargs["icon_custom_emoji_id"] = str(premium_emoji_id).strip()
        if button.button_type == "inline_copy":
            copy_payload = payload or copy_text
            if not copy_payload:
                return None
            api_kwargs["copy_text"] = {"text": copy_payload}
            return InlineKeyboardButton(button_text, api_kwargs=api_kwargs)
        if button.button_type == "inline_url":
            if payload and payload.startswith(("http://", "https://", "tg://")):
                return InlineKeyboardButton(button_text, url=payload, api_kwargs=api_kwargs or None)
            return None
        if button.button_type == "inline_action" and source_button:
            return InlineKeyboardButton(
                button_text,
                callback_data=f"shop_response_button:{button.id}",
                api_kwargs=api_kwargs or None,
            )
        return None

    @staticmethod
    async def response_button_action(session: AsyncSession, message_id: int) -> str | None:
        result = await session.execute(select(ShopMessage).where(ShopMessage.id == message_id))
        message = result.scalar_one_or_none()
        if not message or not message.response_button_source_id:
            return None
        button = await ShopCustomizationService.get_button(session, message.response_button_source_id)
        if not button or not button.is_enabled:
            return None
        return button.action

    @staticmethod
    async def message_button_action(session: AsyncSession, button_id: int) -> str | None:
        message_button = await ShopCustomizationService.get_message_button(session, button_id)
        if not message_button or not message_button.is_enabled or not message_button.source_button_id:
            return None
        button = await ShopCustomizationService.get_button(session, message_button.source_button_id)
        if not button or not button.is_enabled:
            return None
        return button.action

    @staticmethod
    async def purchase_success_reply_markup(session: AsyncSession, sub_link: str):
        return await ShopCustomizationService.message_reply_markup(
            session,
            "purchase_success",
            fallback_markup=await ShopCustomizationService.back_keyboard(session),
            default_url=sub_link,
            copy_text=sub_link,
        )


def _reply_keyboard(rows: list[list[KeyboardButton]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        input_field_placeholder="یکی از گزینه‌ها را انتخاب کنید",
    )


def _join_emoji(emoji: str | None, text: str, position: str = "left") -> str:
    if emoji:
        if position == "right":
            return f"{text} {emoji}"
        return f"{emoji} {text}"
    return text


def _clean_key(value: str | None) -> str:
    value = (value or "default").strip().lower()
    value = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value)
    return value or "default"


def _is_valid_custom_emoji_id(value: str | None) -> bool:
    if value is None:
        return False
    value = str(value).strip()
    return bool(value and value.isdigit())


def _insert_after_heading(text: str, line: str) -> str:
    parts = text.split("\n\n", 1)
    if len(parts) == 2 and parts[0].strip().startswith("**"):
        return f"{parts[0]}\n\n{line}{parts[1]}"
    return line + text


def _safe_format(template: str, values: dict, *, escape_values: bool = False) -> str:
    rendered = template
    for key, value in values.items():
        if escape_values:
            value = re.sub(r"([_*`\[])", r"\\\1", str(value))
        rendered = rendered.replace("{" + str(key) + "}", str(value))
    return rendered


def _safe_format_html(template: str, values: dict) -> str:
    rendered = template
    for key, value in values.items():
        replacement = str(value) if getattr(value, "parse_mode", None) == "HTML" else html.escape(str(value), quote=False)
        rendered = rendered.replace("{" + str(key) + "}", replacement)
    return rendered


def _render_template_with_values(
    template: str,
    parse_mode: str,
    values: dict,
    *,
    escape_markdown_values: bool = False,
) -> tuple[str, str]:
    has_html_value = any(getattr(value, "parse_mode", None) == "HTML" for value in values.values())
    if parse_mode == "HTML":
        return _safe_format_html(template, values), "HTML"
    if has_html_value:
        html_template = _markdown_to_telegram_html(template)
        return _safe_format_html(html_template, values), "HTML"
    return _safe_format(template, values, escape_values=escape_markdown_values), parse_mode
