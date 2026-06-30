import json
import logging
import re
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
    constants,
)
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.helpers import escape_markdown

from ..auth import AuthManager
from ..config_loader import BotConfig
from ..database import async_session
from ..models import Config, ProvisionPanel, Purchase, ReferralRewardRule, User
from ..services.admin_service import ALL_PERMISSIONS, AdminService, normalize_permissions
from ..services.broadcast_service import BroadcastService
from ..services.coupon_service import CouponError, CouponService
from ..services.crypto_payment_service import CryptoPaymentService, available_coins
from ..services.rate_service import RateService
from ..services.rial_payment_service import RialPaymentService
from ..services.settings_service import SettingsService
from ..services.wallet_notification_service import WalletNotificationService
from ..services.inventory_service import InventoryService
from ..services.price_service import PriceService
from ..services.provisioning_service import ProvisioningError, ProvisioningService
from ..services.referral_service import ReferralService
from ..services.required_channel_service import RequiredChannelService
from ..services.shop_customization_service import ShopCustomizationService
from ..services.subscription_link_service import SubscriptionLinkService
from ..services.user_service import UserService
from ..utils.keyboards import (
    ADMIN_ADMINS,
    ADMIN_ADD_ADMIN,
    ADMIN_ADD_BUTTON,
    ADMIN_ADD_CATEGORY,
    ADMIN_ADD_CHANNEL,
    ADMIN_ADD_PLAN,
    ADMIN_ADD_CONFIG,
    ADMIN_BACK,
    ADMIN_BROADCAST,
    ADMIN_BROADCAST_SEND,
    ADMIN_CHANGE_ADMIN_PERMS,
    ADMIN_CHARGE_WALLET,
    ADMIN_COUPONS,
    ADMIN_CRYPTO,
    ADMIN_CRYPTO_HISTORY,
    ADMIN_CRYPTO_RATES,
    ADMIN_CRYPTO_SEARCH,
    ADMIN_CRYPTO_SET_MARGIN,
    ADMIN_CRYPTO_SET_TON,
    ADMIN_CRYPTO_SET_USDT,
    ADMIN_CRYPTO_TOGGLE_MODE,
    ADMIN_RIAL_HISTORY,
    ADMIN_RIAL_SETTINGS,
    ADMIN_RIAL_SET_MIN,
    ADMIN_RIAL_SET_SUPPORT,
    ADMIN_RIAL_TOGGLE_PHONE,
    ADMIN_CREATE_COUPON,
    ADMIN_DEACTIVATE_COUPON,
    ADMIN_DELETE_BUTTON,
    ADMIN_DELETE_PLAN,
    ADMIN_DELETE_PLAN_CONFIRM,
    ADMIN_PLAN_PROVISION_SETTINGS,
    ADMIN_SET_PROVISION_MODE,
    ADMIN_SET_PROVISION_PANEL,
    ADMIN_TOGGLE_PROVISION,
    ADMIN_TOGGLE_RENEW,
    ADMIN_SET_NAME_PREFIX,
    ADMIN_SET_PROVISION_DURATION,
    ADMIN_SET_PROVISION_VOLUME,
    ADMIN_SET_PROVISION_TIME_MODE,
    ADMIN_SET_SUBSCRIPTION_DEVICE_LIMIT,
    ADMIN_PLAN_BACK_TO_EDIT,
    ADMIN_SET_PANEL_GROUPS,
    ADMIN_SET_PANEL_HWID,
    ADMIN_SET_PANEL_INBOUNDS,
    ADMIN_SET_PANEL_PROTOCOLS,
    ADMIN_TOGGLE_PANEL_ENABLED,
    ADMIN_DELETE_CATEGORY,
    ADMIN_DELETE_CHANNEL,
    ADMIN_DELETE_COUPON,
    ADMIN_EDIT_COUPON,
    ADMIN_EDIT_EMOJI,
    ADMIN_EDIT_EMOJI_POSITION,
    ADMIN_EDIT_CATEGORY,
    ADMIN_EDIT_ORDER,
    ADMIN_EDIT_POSITION,
    ADMIN_EDIT_PRICE,
    ADMIN_EDIT_PREMIUM_EMOJI,
    ADMIN_EDIT_PREMIUM_EMOJI_POSITION,
    ADMIN_EDIT_RESPONSE_BUTTON,
    ADMIN_EDIT_STYLE,
    ADMIN_EDIT_TEXT,
    ADMIN_EDIT_TITLE,
    ADMIN_INVENTORY,
    ADMIN_LOGOUT,
    ADMIN_PRICES,
    ADMIN_REFERRAL_REPORT,
    ADMIN_REFERRAL_REWARDS,
    ADMIN_REFERRAL_ADD_RULE,
    ADMIN_REFERRAL_RECALCULATE,
    ADMIN_REFERRAL_TOGGLE_RULE,
    ADMIN_REFERRAL_DELETE_RULE,
    ADMIN_REFRESH_ADMINS,
    ADMIN_REQUIRED_CHANNELS,
    ADMIN_REMOVE_ADMIN,
    ADMIN_REPORTS,
    ADMIN_RESPONSE_INLINE_COPY,
    ADMIN_RESPONSE_INLINE_ACTION,
    ADMIN_RESPONSE_INLINE_URL,
    ADMIN_RESPONSE_EDIT_PREMIUM_EMOJI,
    ADMIN_RESPONSE_EDIT_STYLE,
    ADMIN_RESPONSE_REPLY_KEYBOARD,
    ADMIN_RESPONSE_SELECT_EXISTING,
    ADMIN_RESPONSE_TEXT,
    ADMIN_RESET_CONFIRM,
    ADMIN_SEARCH_USER,
    ADMIN_SET_WALLET,
    ADMIN_SHOP_BUTTONS,
    ADMIN_SHOP_CATEGORIES,
    ADMIN_SHOP_MENU_BACK,
    ADMIN_SHOP_MENU_BUY,
    ADMIN_SHOP_MENU_MAIN,
    ADMIN_SHOP_MENU_WALLET,
    ADMIN_SHOP_MESSAGES,
    ADMIN_SHOP_PLANS,
    ADMIN_PROVISION_PANELS,
    ADMIN_SHOP_RESET_DEFAULTS,
    ADMIN_SHOP_SETTINGS,
    ADMIN_STOCK_STATUS,
    ADMIN_TOGGLE_ENABLED,
    ADMIN_TOGGLE_BRANDED_LINKS,
    ADMIN_TRIAL_SETTINGS,
    ADMIN_TRIAL_SET_DURATION,
    ADMIN_TRIAL_SET_VOLUME,
    ADMIN_TRIAL_TOGGLE,
    ADMIN_SERVICE_REMINDERS,
    ADMIN_SERVICE_REMINDER_TOGGLE,
    ADMIN_SERVICE_REMINDER_SET_VOLUME,
    ADMIN_SERVICE_REMINDER_SET_DAYS,
    ADMIN_SERVICE_REMINDER_SET_HOURS,
    ADMIN_USERS,
    ADMIN_USER_STATS,
    ADMIN_EMOJI_LEFT,
    ADMIN_EMOJI_RIGHT,
    ADMIN_VIEW_COUPONS,
    ADMIN_VIEW_PRICES,
    CANCEL,
    COUPON_ALL_USERS,
    COUPON_FIXED,
    COUPON_PERCENT,
    COUPON_SELECTED_USERS,
    DONE_ADDING_CONFIGS,
    CHANGE_USER,
    CONFIRM_USER,
    REPORT_45_DAYS,
    REPORT_MONTH,
    REPORT_90_DAYS,
    REPORT_TODAY,
    REPORT_WEEK,
    add_links_collecting_keyboard,
    admin_coupons_keyboard,
    admin_crypto_keyboard,
    admin_crypto_rates_keyboard,
    admin_rial_settings_keyboard,
    admin_inventory_keyboard,
    admin_main_keyboard,
    admin_management_keyboard,
    admin_prices_keyboard,
    admin_reports_keyboard,
    admin_shop_button_edit_keyboard,
    admin_shop_category_edit_keyboard,
    admin_shop_menus_keyboard,
    admin_shop_plan_edit_keyboard,
    admin_shop_plan_provision_keyboard,
    admin_shop_plan_delete_confirm_keyboard,
    admin_provision_mode_keyboard,
    admin_provision_panel_keyboard,
    admin_provision_time_mode_keyboard,
    admin_shop_settings_keyboard,
    admin_emoji_position_keyboard,
    admin_response_button_keyboard,
    admin_reset_confirm_keyboard,
    admin_required_channel_keyboard,
    admin_style_keyboard,
    admin_trial_settings_keyboard,
    admin_service_reminders_keyboard,
    admin_user_confirm_keyboard,
    admin_users_keyboard,
    coupon_target_keyboard,
    coupon_type_keyboard,
)
from ..utils.messages import (
    ADD_CONFIG_VOLUME,
    ADMIN_INVENTORY_MENU,
    ADMIN_MAIN_MENU,
    ADMIN_MANAGEMENT_MENU,
    ADMIN_PRICES_MENU,
    ADMIN_REPORTS_MENU,
    ADMIN_USERS_MENU,
    AUTH_ENTER_PASSWORD,
    AUTH_EXPIRED,
    AUTH_FAILED,
    AUTH_SUCCESS,
    CHARGE_AMOUNT_PROMPT,
    CHARGE_SUCCESS,
    CHARGE_WALLET_PROMPT,
    EDIT_PRICE_PROMPT,
    LINKS_DETECTED,
    NO_LINKS_FOUND,
    PRICE_LIST_HEADER,
    PRICE_UPDATED,
    SEARCH_USER_PROMPT,
    SEND_LINKS_PROMPT,
    STOCK_STATUS_HEADER,
)
from ..utils.validators import extract_links_from_text

logger = logging.getLogger(__name__)

ADD_CONFIG_PAGE_SIZE = 8
ADD_CONFIG_CALLBACK_PREFIX = "admin_addcfg"
SHOP_PLAN_CALLBACK_PREFIX = "admin_planmgr"
PROVISION_INBOUND_CALLBACK_PREFIX = "admin_inb"

(
    CHOOSE_VOLUME_ADD,
    COLLECT_LINKS,
    CHOOSE_VOLUME_PRICE,
    ENTER_NEW_PRICE,
    SEARCH_USER,
    CHARGE_USER_ID,
    CHARGE_CONFIRM_USER,
    CHARGE_AMOUNT,
    COUPON_CODE,
    COUPON_TYPE,
    COUPON_AMOUNT,
    COUPON_TARGET,
    COUPON_TARGET_USERS,
    COUPON_DEACTIVATE_CODE,
    COUPON_DELETE_CODE,
    SET_WALLET_USER_ID,
    SET_WALLET_CONFIRM_USER,
    SET_WALLET_AMOUNT,
    COUPON_EDIT_CODE,
    COUPON_EDIT_TYPE,
    COUPON_EDIT_AMOUNT,
    COUPON_EDIT_TARGET,
    COUPON_EDIT_TARGET_USERS,
    SHOP_MESSAGE_SELECT,
    SHOP_MESSAGE_TEXT,
    SHOP_BUTTON_MENU,
    SHOP_BUTTON_SELECT,
    SHOP_BUTTON_OPTION,
    SHOP_BUTTON_VALUE,
    SHOP_BUTTON_ADD_TEXT,
    SHOP_BUTTON_ADD_MESSAGE,
    SHOP_PLAN_SELECT,
    SHOP_PLAN_OPTION,
    SHOP_PLAN_VALUE,
    SHOP_PLAN_ADD_VOLUME,
    SHOP_PLAN_ADD_TITLE,
    SHOP_PLAN_ADD_CATEGORY,
    SHOP_PLAN_ADD_PRICE,
    SHOP_CATEGORY_SELECT,
    SHOP_CATEGORY_ADD,
    SHOP_CATEGORY_OPTION,
    SHOP_CATEGORY_VALUE,
    REQUIRED_CHANNEL_ACTION,
    REQUIRED_CHANNEL_ADD,
    REQUIRED_CHANNEL_DELETE,
    ADMIN_ADD_ID,
    ADMIN_ADD_PERMS,
    ADMIN_REMOVE_ID,
    ADMIN_PERMS_ID,
    ADMIN_PERMS_VALUE,
    CRYPTO_SEARCH_ID,
    CRYPTO_SET_MARGIN_VALUE,
    CRYPTO_SET_USDT_VALUE,
    CRYPTO_SET_TON_VALUE,
    RIAL_SET_MIN_VALUE,
    RIAL_SET_SUPPORT_VALUE,
    SHOP_RESET_CONFIRM,
    SHOP_RESET_PASSWORD,
    TRIAL_SET_VOLUME_VALUE,
    TRIAL_SET_DURATION_VALUE,
    REFERRAL_RULE_SELECT,
    REFERRAL_RULE_TITLE,
    REFERRAL_RULE_QUALIFICATION,
    REFERRAL_RULE_COUNT,
    REFERRAL_RULE_REPEAT,
    REFERRAL_RULE_REWARD_TYPE,
    REFERRAL_RULE_REWARD_VALUE,
    REFERRAL_RULE_OPTION,
    BROADCAST_MESSAGE,
    BROADCAST_CONFIRM,
    PROVISION_PANEL_SELECT,
    PROVISION_PANEL_OPTION,
    PROVISION_PANEL_VALUE,
    SERVICE_REMINDER_VOLUME_VALUE,
    SERVICE_REMINDER_DAYS_VALUE,
    SERVICE_REMINDER_HOURS_VALUE,
) = range(76)


SHOP_MENU_LABELS = {
    ADMIN_SHOP_MENU_MAIN: "shop_main",
    ADMIN_SHOP_MENU_WALLET: "shop_wallet",
    ADMIN_SHOP_MENU_BUY: "shop_buy",
    ADMIN_SHOP_MENU_BACK: "shop_back",
}

STYLE_VALUES = {"primary", "success", "danger", "default"}
EMOJI_POSITION_VALUES = {ADMIN_EMOJI_LEFT: "left", ADMIN_EMOJI_RIGHT: "right", "left": "left", "right": "right"}
RESPONSE_BUTTON_VALUES = {
    ADMIN_RESPONSE_TEXT: "text",
    ADMIN_RESPONSE_INLINE_COPY: "inline_copy",
    ADMIN_RESPONSE_INLINE_URL: "inline_url",
    ADMIN_RESPONSE_INLINE_ACTION: "inline_action",
    ADMIN_RESPONSE_REPLY_KEYBOARD: "reply_keyboard",
}

ADMIN_TOP_LEVEL_LABELS = {
    ADMIN_INVENTORY,
    ADMIN_PRICES,
    ADMIN_USERS,
    ADMIN_REPORTS,
    ADMIN_COUPONS,
    ADMIN_ADMINS,
    ADMIN_SHOP_SETTINGS,
    ADMIN_LOGOUT,
}

SHOP_SETTINGS_LABELS = {
    ADMIN_SHOP_MESSAGES,
    ADMIN_SHOP_BUTTONS,
    ADMIN_SHOP_CATEGORIES,
    ADMIN_SHOP_PLANS,
    ADMIN_PROVISION_PANELS,
    ADMIN_SHOP_RESET_DEFAULTS,
    ADMIN_REQUIRED_CHANNELS,
    ADMIN_TOGGLE_BRANDED_LINKS,
    ADMIN_TRIAL_SETTINGS,
    ADMIN_SERVICE_REMINDERS,
}


def _exact_filter(text: str):
    return filters.Regex(f"^{re.escape(text)}$")


def _extract_volume(text: str) -> int | None:
    match = re.search(r"(\d+)\s*گیگ", text)
    return int(match.group(1)) if match else None


def _rows(labels: list[str], *, width: int = 2) -> ReplyKeyboardMarkup:
    rows = [labels[index : index + width] for index in range(0, len(labels), width)]
    rows.append([CANCEL, ADMIN_BACK])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


def _cancel_back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[CANCEL, ADMIN_BACK]], resize_keyboard=True, one_time_keyboard=True)


def _message_label(key: str) -> str:
    return f"📝 {key}"


MESSAGE_PLACEHOLDER_HINTS = {
    "service_details": (
        "\n\nکلیدهای قابل استفاده:\n"
        "`{service_name}` `{original_title}` `{category_key}`\n"
        "`{total_volume}` `{used_volume}` `{remaining_volume}`\n"
        "`{expiry_text}` `{remaining_time}` `{config_count}`\n"
        "`{purchased_at}` `{price}`\n"
        "هر خطی را که نمی‌خواهید نمایش داده شود، از متن قالب حذف کنید."
    ),
    "rial_payment_request": (
        "\n\nکلیدهای قابل استفاده:\n"
        "`{support_handle}` `{amount}` `{source_card}`\n"
        "`{tracking_code}` `{phone_number}` `{copy_text}`\n"
        "نام کلیدها را تغییر ندهید؛ فقط متن و جای آن‌ها را عوض کنید."
    ),
}


def _button_label(button) -> str:
    status = "فعال" if button.is_enabled else "غیرفعال"
    emoji = f"{button.emoji} " if button.emoji else ""
    return f"#{button.id} {emoji}{button.text} ({status})"


def _volume_label(volume_gb: int) -> str:
    return "نامحدود" if volume_gb <= 0 else f"{volume_gb} گیگ"


def _plan_label(plan) -> str:
    status = "فعال" if plan.is_active else "غیرفعال"
    emoji = f"{plan.emoji} " if plan.emoji else ""
    return f"#{plan.id} [{plan.category_key}] {emoji}{plan.title} - {_volume_label(plan.volume_gb)} ({status})"


def _inline_plan_label(plan, *, include_status: bool = False) -> str:
    status = "✅ " if include_status and plan.is_active else "⏸ " if include_status else ""
    label = f"{status}📦 {plan.title} | {_volume_label(plan.volume_gb)} | {plan.category_key}"
    return label if len(label) <= 60 else f"{label[:57]}..."


def _category_label(category) -> str:
    status = "✅" if category.is_active else "⏸"
    emoji = f"{category.emoji} " if category.emoji else ""
    return f"#{category.id} {status} {emoji}{category.title}"


def _panel_label(panel: ProvisionPanel) -> str:
    status = "✅" if panel.is_enabled else "⏸"
    return f"#{panel.id} {status} {panel.title} ({panel.key})"


def _panel_type_label(panel_type: str | None) -> str:
    return {
        "easy": "Easy",
        "pasarguard": "Pasarguard",
        "marzban": "Marzban",
    }.get(panel_type or "", panel_type or "-")


def _normalize_button_text(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def _provision_mode_label(value: str | None) -> str:
    return {
        "inventory": "انبار فقط",
        "inventory_then_panel": "اول انبار بعد پنل",
        "panel_only": "فقط پنل",
    }.get(value or "inventory", value or "inventory")


PROVISION_MODE_VALUES = {
    "انبار فقط": "inventory",
    "اول انبار بعد پنل": "inventory_then_panel",
    "فقط پنل": "panel_only",
    "inventory": "inventory",
    "inventory_then_panel": "inventory_then_panel",
    "panel_only": "panel_only",
}

PROVISION_TIME_MODE_LABELS = {
    "on_hold": "شروع از اولین اتصال",
    "date": "تاریخ‌دار از زمان ساخت",
    "unlimited": "زمان نامحدود",
}

PROVISION_TIME_MODE_VALUES = {
    "شروع از اولین اتصال": "on_hold",
    "تاریخ‌دار از زمان ساخت": "date",
    "زمان نامحدود": "unlimited",
    "on_hold": "on_hold",
    "date": "date",
    "unlimited": "unlimited",
}


def _provision_time_mode_label(value: str | None) -> str:
    return PROVISION_TIME_MODE_LABELS.get(value or "on_hold", value or "on_hold")


def _subscription_device_limit_label(value: int | None) -> str:
    limit = int(value or 0)
    return "نامحدود / بدون شمارش" if limit <= 0 else f"{limit} کاربر/دستگاه"


async def _sync_plan_subscription_device_limit(plan_id: int, device_limit: int) -> int:
    async with async_session() as session:
        result = await session.execute(
            select(Config).where(
                Config.shop_plan_id == plan_id,
                Config.public_sub_token.is_not(None),
                Config.subscription_device_limit.is_(None),
            )
        )
        configs = result.scalars().all()
        synced_count = 0
        for config in configs:
            purchase = (
                await session.execute(
                    select(Purchase)
                    .where(Purchase.config_id == config.id)
                    .order_by(Purchase.purchased_at.desc(), Purchase.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if not purchase:
                continue
            await SubscriptionLinkService.sync_to_panel(
                config,
                purchase.service_name,
                device_limit=device_limit,
            )
            synced_count += 1
        return synced_count


def _parse_inbounds_text(raw_value: str) -> dict[str, list[str]] | None:
    value = raw_value.strip()
    if value in {"-", "خاموش", "همه", "auto", "AUTO"}:
        return {}
    try:
        payload = json.loads(value)
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        result = {}
        for protocol, tags in payload.items():
            if not isinstance(tags, list):
                return None
            clean_tags = [str(tag).strip() for tag in tags if str(tag).strip()]
            if clean_tags:
                result[str(protocol).strip()] = clean_tags
        return result

    result: dict[str, list[str]] = {}
    for chunk in value.split(";"):
        if not chunk.strip():
            continue
        if ":" not in chunk:
            return None
        protocol, tags_text = chunk.split(":", 1)
        protocol = protocol.strip()
        tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()]
        if not protocol or not tags:
            return None
        result[protocol] = tags
    return result


def _flatten_inbounds(inbounds: dict[str, list[str]]) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for protocol in sorted(inbounds):
        for tag in sorted(inbounds[protocol]):
            items.append((protocol, tag))
    return items


def _selected_inbounds_from_panel(panel: ProvisionPanel, available: dict[str, list[str]]) -> set[tuple[str, str]]:
    configured = json.loads(panel.inbounds_json or "{}")
    if not configured:
        return set(_flatten_inbounds(available))
    return {
        (str(protocol), str(tag))
        for protocol, tags in configured.items()
        if isinstance(tags, list)
        for tag in tags
    }


def _inbounds_keyboard(
    available: dict[str, list[str]],
    selected: set[tuple[str, str]],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, (protocol, tag) in enumerate(_flatten_inbounds(available)):
        mark = "✅" if (protocol, tag) in selected else "⬜️"
        label = f"{mark} {protocol} | {tag}"
        if len(label) > 62:
            label = f"{label[:59]}..."
        rows.append([
            InlineKeyboardButton(
                label,
                callback_data=f"{PROVISION_INBOUND_CALLBACK_PREFIX}:toggle:{index}",
            )
        ])
    rows.append([
        InlineKeyboardButton("✅ انتخاب همه", callback_data=f"{PROVISION_INBOUND_CALLBACK_PREFIX}:all"),
        InlineKeyboardButton("⬜️ حذف همه", callback_data=f"{PROVISION_INBOUND_CALLBACK_PREFIX}:none"),
    ])
    rows.append([
        InlineKeyboardButton("🔄 دریافت دوباره", callback_data=f"{PROVISION_INBOUND_CALLBACK_PREFIX}:refresh"),
        InlineKeyboardButton("💾 ذخیره", callback_data=f"{PROVISION_INBOUND_CALLBACK_PREFIX}:save"),
    ])
    rows.append([InlineKeyboardButton("⬅️ بازگشت", callback_data=f"{PROVISION_INBOUND_CALLBACK_PREFIX}:back")])
    return InlineKeyboardMarkup(rows)


def _parse_hash_id(text: str) -> int | None:
    match = re.match(r"#(\d+)\b", text.strip())
    return int(match.group(1)) if match else None


async def _leave_shop_flow_if_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    text = update.message.text
    if text == ADMIN_BACK:
        await admin_menu_navigation(update, context)
        return True
    if text in ADMIN_TOP_LEVEL_LABELS:
        if text == ADMIN_SHOP_SETTINGS:
            await shop_settings_menu(update, context)
        elif text == ADMIN_ADMINS:
            await admin_management_menu(update, context)
        elif text == ADMIN_LOGOUT:
            await admin_logout(update, context)
        else:
            await admin_menu_navigation(update, context)
        return True
    if text in SHOP_SETTINGS_LABELS:
        if text == ADMIN_SHOP_MESSAGES:
            await shop_messages_start(update, context)
        elif text == ADMIN_SHOP_BUTTONS:
            await shop_buttons_start(update, context)
        elif text == ADMIN_SHOP_CATEGORIES:
            await shop_categories_start(update, context)
        elif text == ADMIN_SHOP_PLANS:
            await shop_plans_start(update, context)
        elif text == ADMIN_PROVISION_PANELS:
            await provision_panels_start(update, context)
        elif text == ADMIN_REQUIRED_CHANNELS:
            await required_channels_start(update, context)
        elif text == ADMIN_TOGGLE_BRANDED_LINKS:
            await toggle_branded_subscription_links(update, context)
        elif text == ADMIN_TRIAL_SETTINGS:
            await trial_settings_menu(update, context)
        elif text == ADMIN_SERVICE_REMINDERS:
            await service_reminders_menu(update, context)
        elif text == ADMIN_SHOP_RESET_DEFAULTS:
            await update.message.reply_text(
                "از روند فعلی خارج شدید. برای بازگردانی، دکمه قرمز «بازگشت فروشگاه به پیش‌فرض» را دوباره بزنید.",
                reply_markup=admin_shop_settings_keyboard(),
            )
        return True
    return False


async def _admin_volume_keyboard(session, action: str) -> ReplyKeyboardMarkup:
    plans = await ShopCustomizationService.list_plans(session)
    active_plans = [plan for plan in plans if plan.is_active]
    if action == "edit_price":
        labels = [f"#{plan.id} ✏️ [{plan.category_key}] {plan.title} - {_volume_label(plan.volume_gb)}" for plan in active_plans]
    else:
        labels = [f"#{plan.id} 📦 [{plan.category_key}] {plan.title} - {_volume_label(plan.volume_gb)}" for plan in active_plans]
    if not labels:
        labels = [f"📦 {volume} گیگ" for volume in (1, 2, 3, 5, 10, 20)]
    return _rows(labels, width=2)


def _add_config_plan_keyboard(plans, page: int = 0) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(plans) + ADD_CONFIG_PAGE_SIZE - 1) // ADD_CONFIG_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * ADD_CONFIG_PAGE_SIZE
    page_plans = plans[start : start + ADD_CONFIG_PAGE_SIZE]

    rows = [
        [
            InlineKeyboardButton(
                _inline_plan_label(plan),
                callback_data=f"{ADD_CONFIG_CALLBACK_PREFIX}:select:{plan.id}",
            )
        ]
        for plan in page_plans
    ]
    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                "قبلی",
                callback_data=f"{ADD_CONFIG_CALLBACK_PREFIX}:page:{page - 1}",
            )
        )
    navigation.append(
        InlineKeyboardButton(
            f"{page + 1} / {total_pages}",
            callback_data=f"{ADD_CONFIG_CALLBACK_PREFIX}:noop",
        )
    )
    if page + 1 < total_pages:
        navigation.append(
            InlineKeyboardButton(
                "بعدی",
                callback_data=f"{ADD_CONFIG_CALLBACK_PREFIX}:page:{page + 1}",
            )
        )
    rows.append(navigation)
    rows.append(
        [
            InlineKeyboardButton(
                "لغو",
                callback_data=f"{ADD_CONFIG_CALLBACK_PREFIX}:cancel",
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def _shop_plan_management_keyboard(plans, page: int = 0) -> InlineKeyboardMarkup:
    total_pages = max(1, (len(plans) + ADD_CONFIG_PAGE_SIZE - 1) // ADD_CONFIG_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * ADD_CONFIG_PAGE_SIZE
    page_plans = plans[start : start + ADD_CONFIG_PAGE_SIZE]
    rows = [
        [
            InlineKeyboardButton(
                _inline_plan_label(plan, include_status=True),
                callback_data=f"{SHOP_PLAN_CALLBACK_PREFIX}:select:{plan.id}",
            )
        ]
        for plan in page_plans
    ]
    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                "قبلی",
                callback_data=f"{SHOP_PLAN_CALLBACK_PREFIX}:page:{page - 1}",
            )
        )
    navigation.append(
        InlineKeyboardButton(
            f"{page + 1} / {total_pages}",
            callback_data=f"{SHOP_PLAN_CALLBACK_PREFIX}:noop",
        )
    )
    if page + 1 < total_pages:
        navigation.append(
            InlineKeyboardButton(
                "بعدی",
                callback_data=f"{SHOP_PLAN_CALLBACK_PREFIX}:page:{page + 1}",
            )
        )
    rows.append(navigation)
    rows.append(
        [
            InlineKeyboardButton(
                ADMIN_ADD_PLAN,
                callback_data=f"{SHOP_PLAN_CALLBACK_PREFIX}:add",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                "بازگشت",
                callback_data=f"{SHOP_PLAN_CALLBACK_PREFIX}:back",
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


async def _active_plans_for_config(session):
    plans = await ShopCustomizationService.list_plans(session)
    return [plan for plan in plans if plan.is_active]


def _normalize_nullable(text: str) -> str | None:
    value = text.strip()
    if value in {"-", "none", "None", "حذف", "خالی"}:
        return None
    return value


def _normalize_custom_emoji_id(text: str) -> str | None:
    value = _normalize_nullable(text)
    if value is None:
        return None
    if not value.isdigit():
        return ""
    return value


def _extract_custom_emoji_id(message) -> str | None:
    sticker = getattr(message, "sticker", None)
    sticker_custom_emoji_id = getattr(sticker, "custom_emoji_id", None)
    if sticker_custom_emoji_id:
        return str(sticker_custom_emoji_id)
    custom_emoji_type = getattr(constants.MessageEntityType, "CUSTOM_EMOJI", "custom_emoji")
    entities = list(getattr(message, "entities", None) or [])
    entities += list(getattr(message, "caption_entities", None) or [])
    for entity in entities:
        entity_type = getattr(entity, "type", "")
        if entity_type == custom_emoji_type or str(entity_type) == "custom_emoji":
            custom_emoji_id = getattr(entity, "custom_emoji_id", None)
            if custom_emoji_id:
                return str(custom_emoji_id)
    return None


def _read_custom_emoji_id(message, raw_text: str) -> str | None:
    return _extract_custom_emoji_id(message) or _normalize_custom_emoji_id(raw_text)


def _message_text_for_storage(message) -> tuple[str, str, str | None]:
    photo_file_id = None
    if getattr(message, "photo", None):
        photo_file_id = message.photo[-1].file_id
        caption = message.caption or ""
        caption_html = getattr(message, "caption_html", None)
        if isinstance(caption_html, str) and caption_html:
            return caption_html, constants.ParseMode.HTML, photo_file_id
        return caption, constants.ParseMode.MARKDOWN, photo_file_id
    if _extract_custom_emoji_id(message):
        text_html = getattr(message, "text_html", None)
        if isinstance(text_html, str) and text_html:
            return text_html, constants.ParseMode.HTML, None
    return message.text or "", constants.ParseMode.MARKDOWN, None


def _broadcast_text(message) -> tuple[str, str | None]:
    if message.entities:
        text_html = getattr(message, "text_html", None)
        if isinstance(text_html, str) and text_html:
            return text_html, constants.ParseMode.HTML
    return message.text or "", None


def _admin_user_preview(user) -> str:
    first_name = escape_markdown(user.first_name or "بدون نام", version=1)
    username = f"@{escape_markdown(user.username, version=1)}" if user.username else "ندارد"
    status = "مسدود" if user.is_blocked else "فعال"
    return (
        "**تایید کاربر**\n\n"
        f"آیدی عددی: `{user.telegram_id}`\n"
        f"نام: {first_name}\n"
        f"یوزرنیم: {username}\n"
        f"موجودی کیف پول: **{user.wallet_balance:,} تومان**\n"
        f"وضعیت: {status}\n\n"
        "اگر کاربر درست است، دکمه تایید کاربر را بزنید."
    )


def require_auth(func=None, *, permission: str | None = None, owner_only: bool = False):
    def decorator(handler_func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            async with async_session() as session:
                if owner_only:
                    is_allowed = await AdminService.is_owner(session, update.effective_user.id)
                else:
                    is_allowed = await AdminService.can_access(session, update.effective_user.id, permission)

            if not is_allowed:
                await update.effective_message.reply_text("دسترسی شما به این بخش مجاز نیست.")
                return ConversationHandler.END

            if not AuthManager.is_authenticated(update.effective_user.id):
                context.user_data["awaiting_password"] = True
                await update.effective_message.reply_text(AUTH_EXPIRED, parse_mode=constants.ParseMode.MARKDOWN)
                return ConversationHandler.END

            AuthManager.refresh_session(update.effective_user.id)
            return await handler_func(update, context)

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


async def is_known_admin(user_id: int) -> bool:
    async with async_session() as session:
        return await AdminService.can_access(session, user_id)


async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_known_admin(update.effective_user.id):
        if not BotConfig.is_admin(update.effective_user.id):
            await update.effective_message.reply_text("دسترسی شما به پنل مدیریت مجاز نیست.")
            return
        async with async_session() as session:
            await AdminService.sync_configured_admins(session)

    if AuthManager.is_authenticated(update.effective_user.id):
        await update.message.reply_text(
            ADMIN_MAIN_MENU.format(update.effective_user.first_name),
            reply_markup=admin_main_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    context.user_data["awaiting_password"] = True
    await update.message.reply_text(AUTH_ENTER_PASSWORD, parse_mode=constants.ParseMode.MARKDOWN)


async def check_admin_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_known_admin(update.effective_user.id):
        return
    if not context.user_data.get("awaiting_password"):
        return

    password = update.message.text
    try:
        await update.message.delete()
    except Exception:
        pass

    if password == BotConfig.ADMIN_PASSWORD:
        AuthManager.authenticate(update.effective_user.id)
        context.user_data["awaiting_password"] = False
        success_msg = await update.message.reply_text(AUTH_SUCCESS, parse_mode=constants.ParseMode.MARKDOWN)
        context.job_queue.run_once(delete_later, 3, data=success_msg)
        await update.message.reply_text(
            ADMIN_MAIN_MENU.format(update.effective_user.first_name),
            reply_markup=admin_main_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    fail_msg = await update.message.reply_text(AUTH_FAILED, parse_mode=constants.ParseMode.MARKDOWN)
    context.job_queue.run_once(delete_later, 5, data=fail_msg)


async def delete_later(context: ContextTypes.DEFAULT_TYPE):
    message = context.job.data
    try:
        await message.delete()
    except Exception:
        pass


@require_auth
async def admin_menu_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nav_map = {
        ADMIN_BACK: (ADMIN_MAIN_MENU.format(update.effective_user.first_name), admin_main_keyboard()),
        ADMIN_INVENTORY: (ADMIN_INVENTORY_MENU, admin_inventory_keyboard()),
        ADMIN_PRICES: (ADMIN_PRICES_MENU, admin_prices_keyboard()),
        ADMIN_USERS: (ADMIN_USERS_MENU, admin_users_keyboard()),
        ADMIN_REPORTS: (ADMIN_REPORTS_MENU, admin_reports_keyboard()),
        ADMIN_COUPONS: (
            "**مدیریت تخفیف‌ها**\n\n"
            "از این بخش می‌توانید کد تخفیف بسازید، لیست تخفیف‌ها را ببینید، یا کدهای قبلی را غیرفعال و حذف کنید.",
            admin_coupons_keyboard(),
        ),
    }
    text, keyboard = nav_map[update.message.text]
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=constants.ParseMode.MARKDOWN)


@require_auth(owner_only=True)
async def admin_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        ADMIN_MANAGEMENT_MENU,
        reply_markup=admin_management_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


@require_auth
async def admin_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    AuthManager.logout(update.effective_user.id)
    await update.message.reply_text(
        "از پنل مدیریت خارج شدید. برای ورود دوباره /start را ارسال کنید.",
        reply_markup=ReplyKeyboardRemove(),
    )


@require_auth(permission="inventory")
async def add_config_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        plans = await _active_plans_for_config(session)
    if not plans:
        await update.message.reply_text(
            "هیچ سرویس فعالی برای افزودن کانفیگ وجود ندارد.",
            reply_markup=admin_inventory_keyboard(),
        )
        return ConversationHandler.END
    await update.message.reply_text(
        f"{ADD_CONFIG_VOLUME}\n\nتعداد سرویس‌های فعال: **{len(plans)}**",
        reply_markup=_add_config_plan_keyboard(plans),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return CHOOSE_VOLUME_ADD


@require_auth(permission="inventory")
async def add_config_plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = (query.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "noop":
        return CHOOSE_VOLUME_ADD
    if action == "cancel":
        await query.edit_message_text("افزودن کانفیگ لغو شد.")
        await query.message.reply_text(
            ADMIN_INVENTORY_MENU,
            reply_markup=admin_inventory_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return ConversationHandler.END

    async with async_session() as session:
        plans = await _active_plans_for_config(session)
        if action == "page":
            page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
            await query.edit_message_reply_markup(
                reply_markup=_add_config_plan_keyboard(plans, page)
            )
            return CHOOSE_VOLUME_ADD

        plan_id = int(parts[2]) if action == "select" and len(parts) > 2 and parts[2].isdigit() else None
        plan = await ShopCustomizationService.get_plan(session, plan_id) if plan_id else None

    if not plan or not plan.is_active:
        await query.message.reply_text("این سرویس دیگر فعال نیست؛ یک سرویس دیگر انتخاب کنید.")
        return CHOOSE_VOLUME_ADD

    context.user_data["adding_plan_id"] = plan.id
    context.user_data["adding_volume"] = plan.volume_gb
    context.user_data["adding_category_key"] = plan.category_key
    context.user_data["collected_links"] = []
    await query.edit_message_text(
        f"سرویس انتخاب شد:\n"
        f"**{escape_markdown(plan.title, version=1)}**\n"
        f"دسته: `{escape_markdown(plan.category_key, version=1)}`\n"
        f"حجم: **{_volume_label(plan.volume_gb)}**",
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    await query.message.reply_text(
        SEND_LINKS_PROMPT,
        reply_markup=add_links_collecting_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return COLLECT_LINKS


@require_auth(permission="inventory")
async def add_config_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_id = _parse_hash_id(update.message.text)
    if plan_id is None:
        await update.message.reply_text("سرویس انتخاب‌شده معتبر نیست.", reply_markup=admin_inventory_keyboard())
        return ConversationHandler.END

    async with async_session() as session:
        plan = await ShopCustomizationService.get_plan(session, plan_id)
    if not plan:
        await update.message.reply_text("سرویس پیدا نشد.", reply_markup=admin_inventory_keyboard())
        return ConversationHandler.END

    context.user_data["adding_plan_id"] = plan.id
    context.user_data["adding_volume"] = plan.volume_gb
    context.user_data["adding_category_key"] = plan.category_key
    context.user_data["collected_links"] = []
    await update.message.reply_text(
        SEND_LINKS_PROMPT,
        reply_markup=add_links_collecting_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return COLLECT_LINKS


@require_auth(permission="inventory")
async def collect_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_links = extract_links_from_text(update.message.text)
    if new_links:
        context.user_data.setdefault("collected_links", []).extend(new_links)
        await update.message.reply_text(
            LINKS_DETECTED.format(len(new_links), len(context.user_data["collected_links"])),
            reply_markup=add_links_collecting_keyboard(),
        )
    else:
        await update.message.reply_text(NO_LINKS_FOUND, reply_markup=add_links_collecting_keyboard())
    return COLLECT_LINKS


@require_auth(permission="inventory")
async def done_collecting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    volume = context.user_data.get("adding_volume")
    category_key = context.user_data.get("adding_category_key", "default")
    links = context.user_data.get("collected_links", [])
    if volume is None or not links:
        await update.message.reply_text("لینکی برای ثبت وجود ندارد.", reply_markup=admin_inventory_keyboard())
        return ConversationHandler.END

    async with async_session() as session:
        count = await InventoryService.add_configs(
            session,
            volume,
            links,
            category_key,
            context.user_data.get("adding_plan_id"),
        )

    await update.message.reply_text(
        f"{count} لینک برای پلن {_volume_label(volume)} در دسته `{category_key}` ثبت شد.",
        reply_markup=admin_inventory_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


@require_auth(permission="inventory")
async def stock_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        stock = await InventoryService.get_stock_status(session)

    message = STOCK_STATUS_HEADER
    for _plan_id, category_key, volume, title, count in stock:
        if count < 5:
            status = "بحرانی"
        elif count <= 10:
            status = "متوسط"
        else:
            status = "مناسب"
        message += f"[{category_key}] {title} - {_volume_label(volume)}: {count} عدد ({status})\n"

    await update.message.reply_text(
        message,
        reply_markup=admin_inventory_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


@require_auth(permission="prices")
async def view_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        plans = await ShopCustomizationService.list_plans(session)

    message = PRICE_LIST_HEADER.format(datetime.now().strftime("%Y-%m-%d %H:%M"))
    async with async_session() as session:
        for plan in plans:
            price = await PriceService.get_plan_price(session, plan)
            message += f"#{plan.id} [{plan.category_key}] {plan.title} - {_volume_label(plan.volume_gb)}: {(price or 0):,} تومان\n"

    await update.message.reply_text(
        message,
        reply_markup=admin_prices_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


@require_auth(permission="prices")
async def edit_price_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        keyboard = await _admin_volume_keyboard(session, "edit_price")
    await update.message.reply_text(
        "حجم پلنی که می‌خواهید قیمتش را تغییر دهید انتخاب کنید:",
        reply_markup=keyboard,
    )
    return CHOOSE_VOLUME_PRICE


@require_auth(permission="prices")
async def edit_price_enter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_id = _parse_hash_id(update.message.text)
    if plan_id is None:
        await update.message.reply_text("سرویس انتخاب‌شده معتبر نیست.", reply_markup=admin_prices_keyboard())
        return ConversationHandler.END

    async with async_session() as session:
        plan = await ShopCustomizationService.get_plan(session, plan_id)
        if not plan:
            await update.message.reply_text("سرویس پیدا نشد.", reply_markup=admin_prices_keyboard())
            return ConversationHandler.END
        current_price = await PriceService.get_plan_price(session, plan)

    context.user_data["editing_plan_id"] = plan.id
    context.user_data["editing_volume"] = plan.volume_gb
    context.user_data["editing_category_key"] = plan.category_key

    await update.message.reply_text(
        EDIT_PRICE_PROMPT.format(plan.volume_gb, f"{(current_price or 0):,}"),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ENTER_NEW_PRICE


@require_auth(permission="prices")
async def save_new_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_id = context.user_data.get("editing_plan_id")
    try:
        new_price = int(update.message.text.replace(",", "").strip())
    except ValueError:
        await update.message.reply_text("لطفا قیمت را فقط به صورت عددی ارسال کنید.")
        return ENTER_NEW_PRICE

    if new_price <= 0:
        await update.message.reply_text("قیمت باید بیشتر از صفر باشد.")
        return ENTER_NEW_PRICE

    async with async_session() as session:
        plan = await ShopCustomizationService.update_plan(session, plan_id, price=new_price)
        success = plan is not None

    if success:
        await update.message.reply_text(
            PRICE_UPDATED.format(context.user_data.get("editing_volume"), f"{new_price:,}", datetime.now().strftime("%H:%M:%S")),
            reply_markup=admin_prices_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text("قیمت بروزرسانی نشد.", reply_markup=admin_prices_keyboard())

    return ConversationHandler.END


@require_auth(permission="users")
async def search_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(SEARCH_USER_PROMPT, parse_mode=constants.ParseMode.MARKDOWN)
    return SEARCH_USER


@require_auth(permission="users")
async def search_user_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    async with async_session() as session:
        user = await UserService.search_user(session, query_text)
        purchase_summary = None
        if user:
            purchase_summary = await UserService.get_user_purchase_summary(session, user.telegram_id)

    if user:
        status = "مسدود" if user.is_blocked else "فعال"
        message = (
            "**اطلاعات کاربر**\n\n"
            f"آیدی عددی: `{user.telegram_id}`\n"
            f"نام: {user.first_name}\n"
            f"یوزرنیم: @{user.username or 'ندارد'}\n"
            f"موجودی کیف پول: **{user.wallet_balance:,} تومان**\n"
            f"تاریخ عضویت: {user.created_at.strftime('%Y-%m-%d')}\n"
            f"وضعیت: {status}\n\n"
            "**خلاصه خرید**\n"
            f"تعداد خرید: **{purchase_summary['total_count']}**\n"
            f"حجم خریداری‌شده: **{purchase_summary['total_gb']:,} گیگ**\n"
            f"مبلغ کل خریدها: **{purchase_summary['total_spent']:,} تومان**"
        )
        if purchase_summary["purchases"]:
            message += "\n\n**آخرین خریدها**\n"
            for purchase in purchase_summary["purchases"]:
                coupon_text = f" | کد تخفیف: {purchase.coupon_code}" if purchase.coupon_code else ""
                message += (
                    f"{purchase.purchased_at.strftime('%Y-%m-%d %H:%M')} | "
                    f"{purchase.volume_gb} گیگ | {purchase.price:,} تومان{coupon_text}\n"
                )
        else:
            message += "\n\nخریدی برای این کاربر ثبت نشده است."

        await update.message.reply_text(
            message,
            reply_markup=admin_users_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text("کاربر پیدا نشد.", reply_markup=admin_users_keyboard())

    return ConversationHandler.END


@require_auth(permission="users")
async def charge_wallet_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(CHARGE_WALLET_PROMPT, parse_mode=constants.ParseMode.MARKDOWN)
    return CHARGE_USER_ID


@require_auth(permission="users")
async def charge_wallet_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    if not query_text:
        await update.message.reply_text("آیدی عددی یا یوزرنیم کاربر را ارسال کنید.")
        return CHARGE_USER_ID

    async with async_session() as session:
        user = await UserService.search_user(session, query_text)

    if not user:
        await update.message.reply_text("کاربری با این آیدی یا یوزرنیم پیدا نشد. دوباره ارسال کنید.")
        return CHARGE_USER_ID

    context.user_data["charge_user_id"] = user.telegram_id
    await update.message.reply_text(
        _admin_user_preview(user),
        reply_markup=admin_user_confirm_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return CHARGE_CONFIRM_USER


@require_auth(permission="users")
async def charge_wallet_confirm_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == CHANGE_USER:
        context.user_data.pop("charge_user_id", None)
        await update.message.reply_text(CHARGE_WALLET_PROMPT, parse_mode=constants.ParseMode.MARKDOWN)
        return CHARGE_USER_ID

    if update.message.text != CONFIRM_USER:
        await update.message.reply_text("لطفا تایید کاربر یا تغییر کاربر را انتخاب کنید.", reply_markup=admin_user_confirm_keyboard())
        return CHARGE_CONFIRM_USER

    await update.message.reply_text(CHARGE_AMOUNT_PROMPT, parse_mode=constants.ParseMode.MARKDOWN)
    return CHARGE_AMOUNT


@require_auth(permission="users")
async def charge_wallet_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.user_data.get("charge_user_id")
    try:
        amount = int(update.message.text.replace(",", "").strip())
    except ValueError:
        await update.message.reply_text("مبلغ شارژ را فقط به صورت عددی ارسال کنید.")
        return CHARGE_AMOUNT

    if amount <= 0:
        await update.message.reply_text("مبلغ شارژ باید بیشتر از صفر باشد.")
        return CHARGE_AMOUNT

    async with async_session() as session:
        success = await UserService.charge_wallet(session, user_id, amount, update.effective_user.id)
        if success:
            user = (
                await session.execute(select(User).where(User.telegram_id == user_id))
            ).scalar_one()

    if success:
        async with async_session() as session:
            notified = await WalletNotificationService.send_charge_notification(
                session,
                telegram_id=user_id,
                amount=amount,
                wallet_balance=user.wallet_balance,
            )
        if notified:
            notification_status = "\nپیام شارژ نیز برای کاربر ارسال شد."
        else:
            notification_status = "\nشارژ ثبت شد، اما ارسال پیام به کاربر ممکن نبود."
        await update.message.reply_text(
            CHARGE_SUCCESS.format(user_id, f"{amount:,}", datetime.now().strftime("%H:%M:%S"))
            + notification_status,
            reply_markup=admin_users_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text("کاربر پیدا نشد.", reply_markup=admin_users_keyboard())


async def _execute_broadcast(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    admin_chat_id: int,
    text: str,
    parse_mode: str | None,
) -> None:
    try:
        async with async_session() as session:
            user_ids = await BroadcastService.recipient_ids(session)
        stats = await BroadcastService.send_text(user_ids, text=text, parse_mode=parse_mode)
        await context.bot.send_message(
            chat_id=admin_chat_id,
            text=(
                "✅ **ارسال همگانی تمام شد**\n\n"
                f"کل مخاطبان: **{stats['total']:,}**\n"
                f"ارسال موفق: **{stats['sent']:,}**\n"
                f"مسدود یا چت غیرفعال: **{stats['blocked']:,}**\n"
                f"خطاهای دیگر: **{stats['failed']:,}**"
            ),
            parse_mode=constants.ParseMode.MARKDOWN,
            reply_markup=admin_main_keyboard(),
        )
    except Exception:
        logger.exception("Broadcast failed")
        await context.bot.send_message(
            chat_id=admin_chat_id,
            text="ارسال همگانی به دلیل خطای داخلی متوقف شد. جزئیات در لاگ سرور ثبت شد.",
            reply_markup=admin_main_keyboard(),
        )


@require_auth(permission="users")
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("broadcast_text", None)
    context.user_data.pop("broadcast_parse_mode", None)
    await update.message.reply_text(
        "📢 **ارسال پیام همگانی**\n\n"
        "متن موردنظر را ارسال کنید. قالب‌بندی متن و ایموجی پریمیوم حفظ می‌شود.\n"
        "پس از آن پیش‌نمایش و تأیید نهایی نمایش داده می‌شود.",
        reply_markup=_cancel_back_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return BROADCAST_MESSAGE


@require_auth(permission="users")
async def broadcast_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, parse_mode = _broadcast_text(update.message)
    if not text.strip():
        await update.message.reply_text("متن پیام نمی‌تواند خالی باشد.")
        return BROADCAST_MESSAGE
    if len(text) > 4096:
        await update.message.reply_text("متن پیام بیشتر از محدودیت ۴۰۹۶ کاراکتری تلگرام است.")
        return BROADCAST_MESSAGE

    context.user_data["broadcast_text"] = text
    context.user_data["broadcast_parse_mode"] = parse_mode
    await update.message.reply_text("پیش‌نمایش پیام:")
    await update.message.reply_text(
        text,
        parse_mode=parse_mode,
        reply_markup=ReplyKeyboardMarkup(
            [[ADMIN_BROADCAST_SEND], [CANCEL, ADMIN_BACK]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )
    return BROADCAST_CONFIRM


@require_auth(permission="users")
async def broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != ADMIN_BROADCAST_SEND:
        await update.message.reply_text("برای ارسال، دکمه تأیید را انتخاب کنید.")
        return BROADCAST_CONFIRM

    text = context.user_data.pop("broadcast_text", None)
    parse_mode = context.user_data.pop("broadcast_parse_mode", None)
    if not text:
        return await broadcast_start(update, context)

    async with async_session() as session:
        recipient_count = len(await BroadcastService.recipient_ids(session))
    await update.message.reply_text(
        f"ارسال پیام به {recipient_count:,} کاربر در پس‌زمینه شروع شد. پس از پایان، گزارش ارسال می‌شود.",
        reply_markup=admin_main_keyboard(),
    )
    context.application.create_task(
        _execute_broadcast(
            context,
            admin_chat_id=update.effective_chat.id,
            text=text,
            parse_mode=parse_mode,
        ),
        update=update,
        name=f"broadcast-{update.effective_user.id}",
    )
    return ConversationHandler.END

    return ConversationHandler.END


@require_auth(permission="users")
async def set_wallet_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "**تنظیم موجودی کیف پول**\n\nآیدی عددی تلگرام کاربر را ارسال کنید.",
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SET_WALLET_USER_ID


@require_auth(permission="users")
async def set_wallet_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("آیدی عددی تلگرام باید فقط عدد باشد.")
        return SET_WALLET_USER_ID

    async with async_session() as session:
        user = await UserService.search_user(session, str(user_id))

    if not user:
        await update.message.reply_text("کاربری با این آیدی پیدا نشد. دوباره آیدی عددی را ارسال کنید.")
        return SET_WALLET_USER_ID

    context.user_data["set_wallet_user_id"] = user.telegram_id
    await update.message.reply_text(
        _admin_user_preview(user),
        reply_markup=admin_user_confirm_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SET_WALLET_CONFIRM_USER


@require_auth(permission="users")
async def set_wallet_confirm_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == CHANGE_USER:
        context.user_data.pop("set_wallet_user_id", None)
        await update.message.reply_text(
            "**تنظیم موجودی کیف پول**\n\nآیدی عددی تلگرام کاربر را ارسال کنید.",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return SET_WALLET_USER_ID

    if update.message.text != CONFIRM_USER:
        await update.message.reply_text("لطفا تایید کاربر یا تغییر کاربر را انتخاب کنید.", reply_markup=admin_user_confirm_keyboard())
        return SET_WALLET_CONFIRM_USER

    await update.message.reply_text(
        "موجودی جدید کیف پول را به تومان ارسال کنید. برای صفر کردن کیف پول عدد `0` را بفرستید.",
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SET_WALLET_AMOUNT


@require_auth(permission="users")
async def set_wallet_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.user_data.get("set_wallet_user_id")
    try:
        balance = int(update.message.text.replace(",", "").strip())
    except ValueError:
        await update.message.reply_text("موجودی جدید را فقط به صورت عددی ارسال کنید.")
        return SET_WALLET_AMOUNT

    if balance < 0:
        await update.message.reply_text("موجودی کیف پول نمی‌تواند منفی باشد.")
        return SET_WALLET_AMOUNT

    async with async_session() as session:
        success = await UserService.set_wallet_balance(session, user_id, balance, update.effective_user.id)

    if success:
        await update.message.reply_text(
            f"موجودی کیف پول کاربر `{user_id}` روی **{balance:,} تومان** تنظیم شد.",
            reply_markup=admin_users_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text("کاربر پیدا نشد.", reply_markup=admin_users_keyboard())

    return ConversationHandler.END


@require_auth(permission="reports")
async def sales_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    period_map = {
        REPORT_TODAY: (1, "امروز"),
        REPORT_WEEK: (7, "هفته جاری"),
        REPORT_MONTH: (30, "ماه جاری"),
        REPORT_45_DAYS: (45, "۴۵ روز اخیر"),
        REPORT_90_DAYS: (90, "۹۰ روز اخیر"),
    }
    days, period_name = period_map[update.message.text]
    tehran = ZoneInfo("Asia/Tehran")
    today = datetime.now(tehran).date()
    since = datetime.combine(today - timedelta(days=days - 1), time.min, tehran).astimezone(timezone.utc)
    until = datetime.combine(today + timedelta(days=1), time.min, tehran).astimezone(timezone.utc)

    async with async_session() as session:
        result = await session.execute(
            select(Purchase).where(Purchase.purchased_at >= since, Purchase.purchased_at < until)
        )
        purchases = result.scalars().all()

    purchases = sorted(purchases, key=lambda item: item.purchased_at, reverse=True)
    total_revenue = sum(purchase.price for purchase in purchases)
    sale_count = sum(1 for purchase in purchases if purchase.kind != "renewal")
    renewals = sum(1 for purchase in purchases if purchase.kind == "renewal")
    volume_stats = {}
    category_stats = {}
    plan_stats = {}
    source_stats = {"inventory": 0, "panel": 0}
    for purchase in purchases:
        volume_stats[purchase.volume_gb] = volume_stats.get(purchase.volume_gb, 0) + 1
        category = purchase.category_key or "default"
        category_bucket = category_stats.setdefault(category, {"count": 0, "revenue": 0})
        category_bucket["count"] += 1
        category_bucket["revenue"] += purchase.price
        plan_key = purchase.service_name or f"{_volume_label(purchase.volume_gb)} [{category}]"
        plan_bucket = plan_stats.setdefault(plan_key, {"count": 0, "revenue": 0})
        plan_bucket["count"] += 1
        plan_bucket["revenue"] += purchase.price
        if purchase.provision_source == "panel":
            source_stats["panel"] += 1
        else:
            source_stats["inventory"] += 1

    message = f"**گزارش فروش {period_name}**\n\n"
    message += f"کل تراکنش‌های فروش/تمدید: **{len(purchases)}**\n"
    message += f"خرید جدید: **{sale_count}**\n"
    message += f"تمدید: **{renewals}**\n"
    message += f"ارسال از انبار: **{source_stats['inventory']}**\n"
    message += f"ساخت مستقیم از پنل: **{source_stats['panel']}**\n"
    message += f"درآمد کل: **{total_revenue:,} تومان**\n\n"

    if category_stats:
        message += "**تفکیک دسته‌ها:**\n"
        for category, data in sorted(category_stats.items(), key=lambda item: item[1]["revenue"], reverse=True)[:10]:
            message += f"`{category}`: {data['count']} مورد | {data['revenue']:,} تومان\n"
        message += "\n"

    if plan_stats:
        message += "**پرفروش‌ترین سرویس‌ها:**\n"
        for title, data in sorted(plan_stats.items(), key=lambda item: item[1]["count"], reverse=True)[:10]:
            safe_title = escape_markdown(title, version=1)
            message += f"{safe_title}: {data['count']} مورد | {data['revenue']:,} تومان\n"
        message += "\n"

    if volume_stats:
        message += "**تفکیک حجم نمایشی:**\n"
        for volume, count in sorted(volume_stats.items()):
            message += f"{_volume_label(volume)}: {count} مورد\n"

    if purchases:
        message += "\n**آخرین فروش‌ها:**\n"
        for purchase in purchases[:12]:
            purchased_at = purchase.purchased_at
            if purchased_at.tzinfo is None:
                purchased_at = purchased_at.replace(tzinfo=timezone.utc)
            local_time = purchased_at.astimezone(tehran).strftime("%m-%d %H:%M")
            kind = "تمدید" if purchase.kind == "renewal" else "خرید"
            source = "پنل" if purchase.provision_source == "panel" else "انبار"
            title = escape_markdown(purchase.service_name or _volume_label(purchase.volume_gb), version=1)
            message += f"{local_time} | {kind} | {source} | {title} | {purchase.price:,} تومان\n"

    await update.message.reply_text(
        message[:3900],
        reply_markup=admin_reports_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


@require_auth(permission="users")
async def user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        stats = await UserService.get_user_stats(session)

    message = (
        "**آمار کاربران**\n\n"
        f"کل کاربران: {stats['total_users']}\n"
        f"کاربران جدید امروز: {stats['new_today']}\n"
        f"جمع موجودی کیف پول‌ها: **{stats['total_balance']:,} تومان**\n"
        f"حجم کل خریداری‌شده: **{stats['total_purchased_gb']:,} گیگ**\n"
        f"مبلغ کل خریدها: **{stats['total_spent']:,} تومان**\n"
    )

    await update.message.reply_text(
        message,
        reply_markup=admin_users_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


@require_auth(permission="users")
async def referral_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        rows = await ReferralService.referral_map(session)

    if not rows:
        await update.message.reply_text("هنوز هیچ دعوتی ثبت نشده است.", reply_markup=admin_users_keyboard())
        return

    lines = ["**گزارش دعوت‌ها**\n"]
    for referred_id, referrer_id, referred_at in rows[:50]:
        when = referred_at.strftime("%Y-%m-%d %H:%M") if referred_at else "-"
        lines.append(f"`{referred_id}` ← `{referrer_id}` | {when}")

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=admin_users_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


def _referral_rule_label(rule: ReferralRewardRule) -> str:
    status = "✅" if rule.is_active else "⏸"
    condition = ReferralService.QUALIFICATION_LABELS.get(rule.qualification_type, rule.qualification_type)
    reward = (
        f"{rule.wallet_amount or 0:,} تومان"
        if rule.reward_type == "wallet"
        else f"سرویس پلن #{rule.shop_plan_id}"
    )
    repeat = "هر بار" if rule.is_repeatable else "یک‌بار"
    return f"#{rule.id} {status} {rule.title} | {rule.required_count} نفر | {condition} | {reward} | {repeat}"


@require_auth(permission="users")
async def referral_rewards_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("referral_rule_draft", None)
    context.user_data.pop("referral_rule_id", None)
    async with async_session() as session:
        rules = await ReferralService.list_rules(session)
    labels = [
        ADMIN_REFERRAL_ADD_RULE,
        ADMIN_REFERRAL_RECALCULATE,
        *[_referral_rule_label(rule) for rule in rules],
    ]
    await update.message.reply_text(
        "🎁 **مدیریت پاداش‌های رفرال**\n\n"
        "می‌توانید چند قانون هم‌زمان بسازید. قانون تکرارشونده در هر مضرب تعداد تعیین‌شده جایزه می‌دهد.",
        reply_markup=_rows(labels, width=1),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return REFERRAL_RULE_SELECT


@require_auth(permission="users")
async def referral_rule_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == ADMIN_REFERRAL_ADD_RULE:
        context.user_data["referral_rule_draft"] = {}
        await update.message.reply_text("یک عنوان کوتاه برای قانون بفرستید.", reply_markup=_cancel_back_keyboard())
        return REFERRAL_RULE_TITLE
    if update.message.text == ADMIN_REFERRAL_RECALCULATE:
        async with async_session() as session:
            rewards = await ReferralService.evaluate_all_referrers(session)
            await session.commit()
        for reward in rewards:
            if reward["config"] is not None:
                await SubscriptionLinkService.sync_to_panel(reward["config"], reward["service_name"])
        await update.message.reply_text(f"✅ محاسبه انجام شد و {len(rewards)} جایزه جدید ثبت شد.")
        return await referral_rewards_start(update, context)

    rule_id = _parse_hash_id(update.message.text)
    if not rule_id:
        await update.message.reply_text("قانون معتبر نیست.")
        return REFERRAL_RULE_SELECT
    async with async_session() as session:
        rule = await session.get(ReferralRewardRule, rule_id)
    if not rule:
        await update.message.reply_text("این قانون پیدا نشد.")
        return await referral_rewards_start(update, context)
    context.user_data["referral_rule_id"] = rule_id
    await update.message.reply_text(
        _referral_rule_label(rule),
        reply_markup=_rows([ADMIN_REFERRAL_TOGGLE_RULE, ADMIN_REFERRAL_DELETE_RULE], width=1),
    )
    return REFERRAL_RULE_OPTION


@require_auth(permission="users")
async def referral_rule_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text("عنوان نمی‌تواند خالی باشد.")
        return REFERRAL_RULE_TITLE
    context.user_data["referral_rule_draft"]["title"] = title
    labels = list(ReferralService.QUALIFICATION_LABELS.values())
    await update.message.reply_text("چه زمانی یک زیرمجموعه معتبر حساب شود؟", reply_markup=_rows(labels, width=1))
    return REFERRAL_RULE_QUALIFICATION


@require_auth(permission="users")
async def referral_rule_qualification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reverse = {label: key for key, label in ReferralService.QUALIFICATION_LABELS.items()}
    qualification = reverse.get(update.message.text)
    if not qualification:
        await update.message.reply_text("شرط معتبر نیست.")
        return REFERRAL_RULE_QUALIFICATION
    context.user_data["referral_rule_draft"]["qualification_type"] = qualification
    await update.message.reply_text(
        "جایزه بعد از چند زیرمجموعه معتبر داده شود؟ فقط عدد بفرستید.",
        reply_markup=_cancel_back_keyboard(),
    )
    return REFERRAL_RULE_COUNT


@require_auth(permission="users")
async def referral_rule_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text.strip())
    except ValueError:
        count = 0
    if count <= 0:
        await update.message.reply_text("تعداد باید یک عدد بزرگ‌تر از صفر باشد.")
        return REFERRAL_RULE_COUNT
    context.user_data["referral_rule_draft"]["required_count"] = count
    await update.message.reply_text(
        "این جایزه فقط یک‌بار داده شود یا در هر بار رسیدن به این تعداد تکرار شود؟",
        reply_markup=_rows(["یک‌بار", "تکرارشونده"], width=2),
    )
    return REFERRAL_RULE_REPEAT


@require_auth(permission="users")
async def referral_rule_repeat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text not in {"یک‌بار", "تکرارشونده"}:
        await update.message.reply_text("یکی از گزینه‌ها را انتخاب کنید.")
        return REFERRAL_RULE_REPEAT
    context.user_data["referral_rule_draft"]["is_repeatable"] = update.message.text == "تکرارشونده"
    await update.message.reply_text(
        "نوع جایزه را انتخاب کنید.",
        reply_markup=_rows(list(ReferralService.REWARD_LABELS.values()), width=2),
    )
    return REFERRAL_RULE_REWARD_TYPE


@require_auth(permission="users")
async def referral_rule_reward_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reverse = {label: key for key, label in ReferralService.REWARD_LABELS.items()}
    reward_type = reverse.get(update.message.text)
    if not reward_type:
        await update.message.reply_text("نوع جایزه معتبر نیست.")
        return REFERRAL_RULE_REWARD_TYPE
    context.user_data["referral_rule_draft"]["reward_type"] = reward_type
    if reward_type == "wallet":
        await update.message.reply_text(
            "مبلغ جایزه را به تومان و فقط به‌صورت عدد ارسال کنید.",
            reply_markup=_cancel_back_keyboard(),
        )
    else:
        async with async_session() as session:
            plans = await ShopCustomizationService.list_plans(session, active_only=True)
        if not plans:
            await update.message.reply_text("هیچ سرویس فعالی برای جایزه وجود ندارد.")
            return await referral_rewards_start(update, context)
        await update.message.reply_text(
            "سرویس رایگان را انتخاب کنید. تحویل جایزه به موجودی همین سرویس وابسته است.",
            reply_markup=_rows([_plan_label(plan) for plan in plans], width=1),
        )
    return REFERRAL_RULE_REWARD_VALUE


@require_auth(permission="users")
async def referral_rule_reward_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get("referral_rule_draft", {})
    if draft.get("reward_type") == "wallet":
        try:
            amount = int(update.message.text.replace(",", "").strip())
        except ValueError:
            amount = 0
        if amount <= 0:
            await update.message.reply_text("مبلغ باید بزرگ‌تر از صفر باشد.")
            return REFERRAL_RULE_REWARD_VALUE
        draft["wallet_amount"] = amount
    else:
        plan_id = _parse_hash_id(update.message.text)
        if not plan_id:
            await update.message.reply_text("سرویس معتبر نیست.")
            return REFERRAL_RULE_REWARD_VALUE
        draft["shop_plan_id"] = plan_id

    try:
        async with async_session() as session:
            rule = await ReferralService.create_rule(
                session,
                created_by=update.effective_user.id,
                **draft,
            )
            await session.commit()
    except ValueError as exc:
        await update.message.reply_text(f"ساخت قانون انجام نشد: {exc}")
        return await referral_rewards_start(update, context)

    context.user_data.pop("referral_rule_draft", None)
    await update.message.reply_text(f"✅ قانون «{rule.title}» ساخته شد.")
    return await referral_rewards_start(update, context)


@require_auth(permission="users")
async def referral_rule_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rule_id = context.user_data.get("referral_rule_id")
    if not rule_id:
        return await referral_rewards_start(update, context)
    async with async_session() as session:
        if update.message.text == ADMIN_REFERRAL_TOGGLE_RULE:
            rule = await ReferralService.toggle_rule(session, rule_id)
            message = "وضعیت قانون تغییر کرد." if rule else "قانون پیدا نشد."
        elif update.message.text == ADMIN_REFERRAL_DELETE_RULE:
            deleted = await ReferralService.delete_rule(session, rule_id)
            message = "قانون حذف شد." if deleted else "قانون پیدا نشد."
        else:
            await update.message.reply_text("گزینه معتبر نیست.")
            return REFERRAL_RULE_OPTION
    await update.message.reply_text(message)
    return await referral_rewards_start(update, context)


@require_auth(permission="coupons")
async def list_coupons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        coupons = await CouponService.list_coupons(session)

    if not coupons:
        await update.message.reply_text("هنوز هیچ کد تخفیفی ساخته نشده است.", reply_markup=admin_coupons_keyboard())
        return

    lines = ["**کدهای تخفیف فعلی**\n"]
    for coupon in coupons[:50]:
        status = "فعال" if coupon.is_active else "غیرفعال"
        if coupon.discount_type == "percent":
            amount = f"{coupon.amount} درصد"
        else:
            amount = f"{coupon.amount:,} تومان"
        target = "همه کاربران" if coupon.applies_to_all else f"{len(coupon.targets)} کاربر"
        lines.append(f"`{coupon.code}` | {amount} | {target} | {status}")

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=admin_coupons_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


@require_auth(permission="coupons")
async def deactivate_coupon_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "کد تخفیفی را که می‌خواهید غیرفعال شود ارسال کنید.",
        reply_markup=admin_coupons_keyboard(),
    )
    return COUPON_DEACTIVATE_CODE


@require_auth(permission="coupons")
async def deactivate_coupon_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        coupon = await CouponService.deactivate_coupon(session, update.message.text)

    if not coupon:
        await update.message.reply_text("کد تخفیف پیدا نشد.", reply_markup=admin_coupons_keyboard())
        return ConversationHandler.END

    await update.message.reply_text(
        f"کد تخفیف **{coupon.code}** غیرفعال شد.",
        reply_markup=admin_coupons_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


@require_auth(permission="coupons")
async def delete_coupon_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "کد تخفیفی را که می‌خواهید حذف شود ارسال کنید.",
        reply_markup=admin_coupons_keyboard(),
    )
    return COUPON_DELETE_CODE


@require_auth(permission="coupons")
async def delete_coupon_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        coupon = await CouponService.delete_coupon(session, update.message.text)

    if not coupon:
        await update.message.reply_text("کد تخفیف پیدا نشد.", reply_markup=admin_coupons_keyboard())
        return ConversationHandler.END

    await update.message.reply_text(
        f"کد تخفیف **{coupon.code}** حذف شد.",
        reply_markup=admin_coupons_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


@require_auth(permission="coupons")
async def edit_coupon_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("coupon_edit_draft", None)
    await update.message.reply_text(
        "**ویرایش تخفیف**\n\nکد تخفیفی را که می‌خواهید ویرایش شود ارسال کنید.",
        reply_markup=admin_coupons_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return COUPON_EDIT_CODE


@require_auth(permission="coupons")
async def edit_coupon_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    async with async_session() as session:
        coupon = await CouponService.get_any_coupon_by_code(session, code)

    if not coupon:
        await update.message.reply_text("کد تخفیف پیدا نشد.", reply_markup=admin_coupons_keyboard())
        return ConversationHandler.END

    context.user_data["coupon_edit_draft"] = {"code": coupon.code}
    current_type = "درصدی" if coupon.discount_type == "percent" else "مبلغ ثابت"
    await update.message.reply_text(
        f"کد **{coupon.code}** پیدا شد.\nنوع فعلی: **{current_type}**\nمقدار فعلی: **{coupon.amount:,}**\n\nنوع جدید تخفیف را انتخاب کنید.",
        reply_markup=coupon_type_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return COUPON_EDIT_TYPE


@require_auth(permission="coupons")
async def edit_coupon_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == COUPON_PERCENT:
        discount_type = "percent"
        prompt = "درصد تخفیف جدید را به صورت عددی بین ۱ تا ۱۰۰ ارسال کنید. مثال: `25`"
    elif update.message.text == COUPON_FIXED:
        discount_type = "fixed"
        prompt = "مبلغ تخفیف جدید را به تومان ارسال کنید. مثال: `50000`"
    else:
        await update.message.reply_text("نوع تخفیف معتبر نیست.", reply_markup=coupon_type_keyboard())
        return COUPON_EDIT_TYPE

    context.user_data.setdefault("coupon_edit_draft", {})["discount_type"] = discount_type
    await update.message.reply_text(prompt, parse_mode=constants.ParseMode.MARKDOWN)
    return COUPON_EDIT_AMOUNT


@require_auth(permission="coupons")
async def edit_coupon_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text.replace(",", "").strip())
    except ValueError:
        await update.message.reply_text("مقدار تخفیف باید عددی باشد.")
        return COUPON_EDIT_AMOUNT

    draft = context.user_data.setdefault("coupon_edit_draft", {})
    discount_type = draft.get("discount_type")
    if discount_type == "percent" and not 1 <= amount <= 100:
        await update.message.reply_text("درصد تخفیف باید بین ۱ تا ۱۰۰ باشد.")
        return COUPON_EDIT_AMOUNT
    if discount_type == "fixed" and amount <= 0:
        await update.message.reply_text("مبلغ تخفیف باید بیشتر از صفر باشد.")
        return COUPON_EDIT_AMOUNT

    draft["amount"] = amount
    await update.message.reply_text(
        "این کد تخفیف برای چه کسانی فعال باشد؟",
        reply_markup=coupon_target_keyboard(),
    )
    return COUPON_EDIT_TARGET


@require_auth(permission="coupons")
async def edit_coupon_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == COUPON_ALL_USERS:
        return await save_coupon_edit(update, context, [])
    if update.message.text == COUPON_SELECTED_USERS:
        await update.message.reply_text(
            "آیدی عددی کاربران را با فاصله، ویرگول یا هرکدام در یک خط ارسال کنید.",
            reply_markup=admin_coupons_keyboard(),
        )
        return COUPON_EDIT_TARGET_USERS

    await update.message.reply_text("محدوده کاربران معتبر نیست.", reply_markup=coupon_target_keyboard())
    return COUPON_EDIT_TARGET


@require_auth(permission="coupons")
async def edit_coupon_target_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_ids = re.split(r"[\s,]+", update.message.text.strip())
    user_ids = []
    for raw_id in raw_ids:
        if not raw_id:
            continue
        try:
            user_ids.append(int(raw_id))
        except ValueError:
            await update.message.reply_text("همه آیدی‌ها باید عددی باشند.")
            return COUPON_EDIT_TARGET_USERS

    if not user_ids:
        await update.message.reply_text("حداقل یک آیدی کاربر ارسال کنید.")
        return COUPON_EDIT_TARGET_USERS

    return await save_coupon_edit(update, context, user_ids)


async def save_coupon_edit(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_ids: list[int]):
    draft = context.user_data.get("coupon_edit_draft", {})
    async with async_session() as session:
        try:
            coupon = await CouponService.update_coupon(
                session,
                code=draft["code"],
                discount_type=draft["discount_type"],
                amount=draft["amount"],
                target_user_ids=target_user_ids,
            )
        except (KeyError, CouponError):
            await update.message.reply_text("کد تخفیف ویرایش نشد. اطلاعات واردشده را بررسی کنید.", reply_markup=admin_coupons_keyboard())
            return ConversationHandler.END

    if not coupon:
        await update.message.reply_text("کد تخفیف پیدا نشد.", reply_markup=admin_coupons_keyboard())
        return ConversationHandler.END

    target_text = "همه کاربران" if coupon.applies_to_all else f"{len(target_user_ids)} کاربر"
    if coupon.discount_type == "percent":
        amount_text = f"{coupon.amount} درصد"
    else:
        amount_text = f"{coupon.amount:,} تومان"

    context.user_data.pop("coupon_edit_draft", None)
    await update.message.reply_text(
        f"کد تخفیف **{coupon.code}** ویرایش شد.\nمقدار جدید: **{amount_text}**\nمحدوده جدید: **{target_text}**",
        reply_markup=admin_coupons_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


@require_auth(permission="coupons")
async def create_coupon_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("coupon_draft", None)
    await update.message.reply_text(
        "**ساخت کد تخفیف**\n\nکد تخفیف را ارسال کنید. مثال: `SPRING25`",
        reply_markup=admin_coupons_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return COUPON_CODE


@require_auth(permission="coupons")
async def create_coupon_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    if not code or any(char.isspace() for char in code):
        await update.message.reply_text("کد تخفیف نباید خالی باشد یا فاصله داشته باشد.")
        return COUPON_CODE

    context.user_data["coupon_draft"] = {"code": code}
    await update.message.reply_text(
        "نوع تخفیف را انتخاب کنید.",
        reply_markup=coupon_type_keyboard(),
    )
    return COUPON_TYPE


@require_auth(permission="coupons")
async def create_coupon_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == COUPON_PERCENT:
        discount_type = "percent"
        prompt = "درصد تخفیف را به صورت عددی بین ۱ تا ۱۰۰ ارسال کنید. مثال: `25`"
    elif update.message.text == COUPON_FIXED:
        discount_type = "fixed"
        prompt = "مبلغ تخفیف را به تومان ارسال کنید. مثال: `50000`"
    else:
        await update.message.reply_text("نوع تخفیف معتبر نیست.", reply_markup=coupon_type_keyboard())
        return COUPON_TYPE

    context.user_data.setdefault("coupon_draft", {})["discount_type"] = discount_type
    await update.message.reply_text(prompt, parse_mode=constants.ParseMode.MARKDOWN)
    return COUPON_AMOUNT


@require_auth(permission="coupons")
async def create_coupon_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text.replace(",", "").strip())
    except ValueError:
        await update.message.reply_text("مقدار تخفیف باید عددی باشد.")
        return COUPON_AMOUNT

    draft = context.user_data.setdefault("coupon_draft", {})
    discount_type = draft.get("discount_type")
    if discount_type == "percent" and not 1 <= amount <= 100:
        await update.message.reply_text("درصد تخفیف باید بین ۱ تا ۱۰۰ باشد.")
        return COUPON_AMOUNT
    if discount_type == "fixed" and amount <= 0:
        await update.message.reply_text("مبلغ تخفیف باید بیشتر از صفر باشد.")
        return COUPON_AMOUNT

    draft["amount"] = amount
    await update.message.reply_text(
        "این کد برای چه کسانی فعال باشد؟",
        reply_markup=coupon_target_keyboard(),
    )
    return COUPON_TARGET


@require_auth(permission="coupons")
async def create_coupon_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == COUPON_ALL_USERS:
        return await save_coupon(update, context, [])
    if update.message.text == COUPON_SELECTED_USERS:
        await update.message.reply_text(
            "آیدی عددی کاربران را با فاصله، ویرگول یا هرکدام در یک خط ارسال کنید.",
            reply_markup=admin_coupons_keyboard(),
        )
        return COUPON_TARGET_USERS

    await update.message.reply_text("محدوده کاربران معتبر نیست.", reply_markup=coupon_target_keyboard())
    return COUPON_TARGET


@require_auth(permission="coupons")
async def create_coupon_target_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_ids = re.split(r"[\s,]+", update.message.text.strip())
    user_ids = []
    for raw_id in raw_ids:
        if not raw_id:
            continue
        try:
            user_ids.append(int(raw_id))
        except ValueError:
            await update.message.reply_text("همه آیدی‌ها باید عددی باشند.")
            return COUPON_TARGET_USERS

    if not user_ids:
        await update.message.reply_text("حداقل یک آیدی کاربر ارسال کنید.")
        return COUPON_TARGET_USERS

    return await save_coupon(update, context, user_ids)


async def save_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_ids: list[int]):
    draft = context.user_data.get("coupon_draft", {})
    async with async_session() as session:
        try:
            coupon = await CouponService.create_coupon(
                session,
                code=draft["code"],
                discount_type=draft["discount_type"],
                amount=draft["amount"],
                created_by=update.effective_user.id,
                target_user_ids=target_user_ids,
            )
        except (KeyError, CouponError):
            await update.message.reply_text("کد تخفیف ساخته نشد. اطلاعات واردشده را بررسی کنید.", reply_markup=admin_coupons_keyboard())
            return ConversationHandler.END

    target_text = "همه کاربران" if coupon.applies_to_all else f"{len(target_user_ids)} کاربر"
    if coupon.discount_type == "percent":
        amount_text = f"{coupon.amount} درصد"
    else:
        amount_text = f"{coupon.amount:,} تومان"

    context.user_data.pop("coupon_draft", None)
    await update.message.reply_text(
        f"کد تخفیف **{coupon.code}** ساخته شد.\nمقدار: **{amount_text}**\nمحدوده: **{target_text}**",
        reply_markup=admin_coupons_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


@require_auth(owner_only=True)
async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        admins = await AdminService.list_admins(session)

    lines = ["**ادمین‌های فعال**\n"]
    for admin in admins:
        role = "مالک" if admin.is_owner else "ادمین"
        permissions = "all" if admin.is_owner else admin.permissions
        lines.append(f"`{admin.telegram_id}` | {role} | `{permissions}`")

    await update.effective_message.reply_text(
        "\n".join(lines),
        reply_markup=admin_management_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


@require_auth(owner_only=True)
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text(
            f"فرمت درست:\n`/addadmin <telegram_id> <permissions>`\n\nسطح دسترسی‌ها: {', '.join(ALL_PERMISSIONS)} یا all",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    try:
        telegram_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("آیدی تلگرام باید عددی باشد.")
        return

    permissions = normalize_permissions(context.args[1:] or "reports")
    if not permissions:
        await update.effective_message.reply_text(
            f"حداقل یک سطح دسترسی معتبر وارد کنید: {', '.join(ALL_PERMISSIONS)} یا all"
        )
        return

    async with async_session() as session:
        admin = await AdminService.add_or_update_admin(
            session,
            telegram_id=telegram_id,
            permissions=permissions,
            created_by=update.effective_user.id,
            is_owner=False,
        )
        await session.commit()

    await update.effective_message.reply_text(f"ادمین `{admin.telegram_id}` با دسترسی `{admin.permissions}` ذخیره شد.", parse_mode=constants.ParseMode.MARKDOWN)


@require_auth(owner_only=True)
async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("فرمت درست: `/removeadmin <telegram_id>`", parse_mode=constants.ParseMode.MARKDOWN)
        return

    try:
        telegram_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("آیدی تلگرام باید عددی باشد.")
        return

    if telegram_id == update.effective_user.id:
        await update.effective_message.reply_text("مالک نمی‌تواند خودش را حذف کند.")
        return

    async with async_session() as session:
        removed = await AdminService.remove_admin(session, telegram_id)
        await session.commit()

    if removed:
        await update.effective_message.reply_text(f"ادمین `{telegram_id}` غیرفعال شد.", parse_mode=constants.ParseMode.MARKDOWN)
    else:
        await update.effective_message.reply_text("ادمین پیدا نشد یا مالک است.")


@require_auth(owner_only=True)
async def set_admin_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.effective_message.reply_text(
            f"فرمت درست:\n`/setadminperms <telegram_id> <permissions>`\n\nسطح دسترسی‌ها: {', '.join(ALL_PERMISSIONS)} یا all",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return

    try:
        telegram_id = int(context.args[0])
    except ValueError:
        await update.effective_message.reply_text("آیدی تلگرام باید عددی باشد.")
        return

    permissions = normalize_permissions(context.args[1:])
    if not permissions:
        await update.effective_message.reply_text(
            f"حداقل یک سطح دسترسی معتبر وارد کنید: {', '.join(ALL_PERMISSIONS)} یا all"
        )
        return

    async with async_session() as session:
        admin = await AdminService.get_admin(session, telegram_id)
        if not admin:
            await update.effective_message.reply_text("ادمین پیدا نشد.")
            return
        if admin.is_owner:
            await update.effective_message.reply_text("دسترسی مالک قابل تغییر نیست.")
            return
        admin.permissions = permissions
        admin.updated_at = datetime.now(timezone.utc)
        await session.commit()

    await update.effective_message.reply_text(f"دسترسی ادمین `{telegram_id}` به `{permissions}` تغییر کرد.", parse_mode=constants.ParseMode.MARKDOWN)


@require_auth(owner_only=True)
async def admin_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "**افزودن ادمین**\n\nآیدی عددی تلگرام ادمین جدید را ارسال کنید.",
        reply_markup=admin_management_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ADMIN_ADD_ID


@require_auth(owner_only=True)
async def admin_add_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        telegram_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("آیدی تلگرام باید فقط عدد باشد.")
        return ADMIN_ADD_ID

    context.user_data["admin_target_id"] = telegram_id
    await update.message.reply_text(
        "**سطح دسترسی ادمین را ارسال کنید**\n\n"
        f"گزینه‌ها: `{', '.join(ALL_PERMISSIONS)}` یا `all`\n"
        "می‌توانید چند مورد را با فاصله یا ویرگول بفرستید. مثال: `users,reports,shop`",
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ADMIN_ADD_PERMS


@require_auth(owner_only=True)
async def admin_add_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = context.user_data.get("admin_target_id")
    permissions = normalize_permissions(update.message.text)
    if not permissions:
        await update.message.reply_text(
            f"حداقل یک سطح دسترسی معتبر ارسال کنید: {', '.join(ALL_PERMISSIONS)} یا all"
        )
        return ADMIN_ADD_PERMS

    async with async_session() as session:
        admin = await AdminService.add_or_update_admin(
            session,
            telegram_id=telegram_id,
            permissions=permissions,
            created_by=update.effective_user.id,
            is_owner=False,
        )
        await session.commit()

    context.user_data.pop("admin_target_id", None)
    await update.message.reply_text(
        f"ادمین `{admin.telegram_id}` با دسترسی `{admin.permissions}` ذخیره شد.",
        reply_markup=admin_management_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


@require_auth(owner_only=True)
async def admin_remove_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "**حذف ادمین**\n\nآیدی عددی ادمینی که می‌خواهید غیرفعال شود را ارسال کنید.",
        reply_markup=admin_management_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ADMIN_REMOVE_ID


@require_auth(owner_only=True)
async def admin_remove_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        telegram_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("آیدی تلگرام باید فقط عدد باشد.")
        return ADMIN_REMOVE_ID

    if telegram_id == update.effective_user.id:
        await update.message.reply_text("مالک نمی‌تواند خودش را حذف کند.")
        return ADMIN_REMOVE_ID

    async with async_session() as session:
        removed = await AdminService.remove_admin(session, telegram_id)
        await session.commit()

    if removed:
        await update.message.reply_text(
            f"ادمین `{telegram_id}` غیرفعال شد.",
            reply_markup=admin_management_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text("ادمین پیدا نشد یا مالک است.", reply_markup=admin_management_keyboard())
    return ConversationHandler.END


@require_auth(owner_only=True)
async def admin_perms_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "**تغییر دسترسی ادمین**\n\nآیدی عددی ادمین را ارسال کنید.",
        reply_markup=admin_management_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ADMIN_PERMS_ID


@require_auth(owner_only=True)
async def admin_perms_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        telegram_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("آیدی تلگرام باید فقط عدد باشد.")
        return ADMIN_PERMS_ID

    async with async_session() as session:
        admin = await AdminService.get_admin(session, telegram_id)

    if not admin:
        await update.message.reply_text("ادمین فعال پیدا نشد. دوباره آیدی را ارسال کنید.")
        return ADMIN_PERMS_ID
    if admin.is_owner:
        await update.message.reply_text("دسترسی مالک قابل تغییر نیست.", reply_markup=admin_management_keyboard())
        return ConversationHandler.END

    context.user_data["admin_target_id"] = telegram_id
    await update.message.reply_text(
        f"دسترسی فعلی: `{admin.permissions}`\n\n"
        f"دسترسی جدید را بفرستید: `{', '.join(ALL_PERMISSIONS)}` یا `all`",
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ADMIN_PERMS_VALUE


@require_auth(owner_only=True)
async def admin_perms_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = context.user_data.get("admin_target_id")
    permissions = normalize_permissions(update.message.text)
    if not permissions:
        await update.message.reply_text(
            f"حداقل یک سطح دسترسی معتبر ارسال کنید: {', '.join(ALL_PERMISSIONS)} یا all"
        )
        return ADMIN_PERMS_VALUE

    async with async_session() as session:
        admin = await AdminService.get_admin(session, telegram_id)
        if not admin:
            await update.message.reply_text("ادمین پیدا نشد.", reply_markup=admin_management_keyboard())
            return ConversationHandler.END
        if admin.is_owner:
            await update.message.reply_text("دسترسی مالک قابل تغییر نیست.", reply_markup=admin_management_keyboard())
            return ConversationHandler.END
        admin.permissions = permissions
        admin.updated_at = datetime.now(timezone.utc)
        await session.commit()

    context.user_data.pop("admin_target_id", None)
    await update.message.reply_text(
        f"دسترسی ادمین `{telegram_id}` به `{permissions}` تغییر کرد.",
        reply_markup=admin_management_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


def _required_channel_label(channel) -> str:
    status = "فعال" if channel.is_active else "غیرفعال"
    return f"#{channel.id} {channel.title} | `{channel.chat_id}` | {status}"


@require_auth(permission="shop")
async def required_channels_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        channels = await RequiredChannelService.list_channels(session)
    lines = ["**عضویت اجباری**\n"]
    if channels:
        lines.extend(_required_channel_label(channel) for channel in channels)
    else:
        lines.append("هنوز هیچ کانالی ثبت نشده است.")
    lines.append(
        "\nبرای افزودن یا آپدیت کانال، دکمه افزودن را بزنید.\n"
        "فرمت افزودن: `chat_id|عنوان|لینک عضویت`\n"
        "مثال: `@mychannel|کانال اخبار|https://t.me/mychannel`"
    )
    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=admin_required_channel_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return REQUIRED_CHANNEL_ACTION


@require_auth(permission="shop")
async def required_channel_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == ADMIN_ADD_CHANNEL:
        await update.message.reply_text(
            "کانال را با فرمت `chat_id|عنوان|لینک عضویت` ارسال کنید.\n"
            "برای کانال عمومی بهتر است `@username` را بفرستید.\n"
            "برای کانال خصوصی باید آیدی عددی کانال و لینک دعوت معتبر بدهید؛ ربات هم باید داخل کانال ادمین باشد.",
            reply_markup=_cancel_back_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return REQUIRED_CHANNEL_ADD
    if update.message.text == ADMIN_DELETE_CHANNEL:
        async with async_session() as session:
            channels = await RequiredChannelService.list_channels(session)
        labels = [f"#{channel.id} {channel.title}" for channel in channels]
        if not labels:
            await update.message.reply_text("کانالی برای حذف وجود ندارد.", reply_markup=admin_shop_settings_keyboard())
            return ConversationHandler.END
        await update.message.reply_text("کانالی که می‌خواهید حذف شود را انتخاب کنید.", reply_markup=_rows(labels, width=1))
        return REQUIRED_CHANNEL_DELETE
    await update.message.reply_text("گزینه معتبر نیست.", reply_markup=admin_required_channel_keyboard())
    return REQUIRED_CHANNEL_ACTION


@require_auth(permission="shop")
async def required_channel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = [part.strip() for part in update.message.text.split("|")]
    if len(parts) != 3 or not all(parts):
        await update.message.reply_text("فرمت درست نیست. مثال: `@mychannel|کانال اخبار|https://t.me/mychannel`", parse_mode=constants.ParseMode.MARKDOWN)
        return REQUIRED_CHANNEL_ADD
    chat_id, title, join_url = parts
    if not join_url.startswith(("http://", "https://", "tg://")):
        await update.message.reply_text("لینک عضویت باید با `https://` یا `tg://` شروع شود.", parse_mode=constants.ParseMode.MARKDOWN)
        return REQUIRED_CHANNEL_ADD
    async with async_session() as session:
        channel = await RequiredChannelService.upsert_channel(session, chat_id, title, join_url)
    await update.message.reply_text(
        f"کانال **{channel.title}** برای عضویت اجباری ذخیره شد.",
        reply_markup=admin_shop_settings_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


@require_auth(permission="shop")
async def required_channel_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_id = _parse_hash_id(update.message.text)
    if channel_id is None:
        await update.message.reply_text("کانال معتبر نیست.")
        return REQUIRED_CHANNEL_DELETE
    async with async_session() as session:
        deleted = await RequiredChannelService.delete_channel(session, channel_id)
    await update.message.reply_text(
        "کانال حذف شد." if deleted else "کانال پیدا نشد.",
        reply_markup=admin_shop_settings_keyboard(),
    )
    return ConversationHandler.END


@require_auth(permission="shop")
async def shop_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        branded_links = await SettingsService.branded_links_enabled(session)
    await update.message.reply_text(
        "**تنظیمات ربات فروش**\n\n"
        "از این بخش می‌توانید متن پیام‌ها، ظاهر و چینش دکمه‌ها، رنگ‌ها، ایموجی پریمیوم و سرویس‌های قابل فروش را مدیریت کنید.\n\n"
        f"لینک اختصاصی ساب: **{'روشن' if branded_links else 'خاموش'}**",
        reply_markup=admin_shop_settings_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


@require_auth(permission="shop")
async def toggle_branded_subscription_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        current = await SettingsService.branded_links_enabled(session)
        enabled = not current
        await SettingsService.set_branded_links_enabled(session, enabled)
    await update.message.reply_text(
        f"ساخت و تحویل لینک اختصاصی ساب **{'روشن' if enabled else 'خاموش'}** شد.",
        reply_markup=admin_shop_settings_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


@require_auth(permission="shop")
async def trial_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        enabled = await SettingsService.trial_enabled(session)
        volume_mb = await SettingsService.get_trial_volume_mb(session)
        duration_hours = await SettingsService.get_trial_duration_hours(session)
    await update.message.reply_text(
        "**تنظیمات کانفیگ تست**\n\n"
        f"وضعیت: **{'روشن' if enabled else 'خاموش'}**\n"
        f"حجم: **{volume_mb} مگابایت**\n"
        f"مدت: **{duration_hours} ساعت از اولین اتصال**\n"
        "هر حساب تلگرام فقط یک‌بار می‌تواند تست دریافت کند.",
        reply_markup=admin_trial_settings_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


@require_auth(permission="shop")
async def trial_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        enabled = not await SettingsService.trial_enabled(session)
        await SettingsService.set_trial_enabled(session, enabled)
    await update.message.reply_text(f"دریافت تست {'روشن' if enabled else 'خاموش'} شد.")
    await trial_settings_menu(update, context)


@require_auth(permission="shop")
async def trial_set_volume_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "حجم تست را به مگابایت وارد کنید. مثال: `500`",
        reply_markup=_cancel_back_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return TRIAL_SET_VOLUME_VALUE


@require_auth(permission="shop")
async def trial_set_volume_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = int(update.message.text.replace(",", "").strip())
    except ValueError:
        value = 0
    if value <= 0:
        await update.message.reply_text("حجم باید یک عدد مثبت برحسب مگابایت باشد.")
        return TRIAL_SET_VOLUME_VALUE
    async with async_session() as session:
        await SettingsService.set_trial_volume_mb(session, value)
    await update.message.reply_text("حجم کانفیگ تست ذخیره شد.")
    await trial_settings_menu(update, context)
    return ConversationHandler.END


@require_auth(permission="shop")
async def trial_set_duration_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مدت تست را به ساعت وارد کنید. مثال: `24`",
        reply_markup=_cancel_back_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return TRIAL_SET_DURATION_VALUE


@require_auth(permission="shop")
async def trial_set_duration_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        value = int(update.message.text.replace(",", "").strip())
    except ValueError:
        value = 0
    if value <= 0:
        await update.message.reply_text("مدت باید یک عدد مثبت برحسب ساعت باشد.")
        return TRIAL_SET_DURATION_VALUE
    async with async_session() as session:
        await SettingsService.set_trial_duration_hours(session, value)
    await update.message.reply_text("مدت کانفیگ تست ذخیره شد.")
    await trial_settings_menu(update, context)
    return ConversationHandler.END


@require_auth(permission="shop")
async def service_reminders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        enabled = await SettingsService.service_reminders_enabled(session)
        volume_percents = await SettingsService.get_service_reminder_volume_percents(session)
        time_days = await SettingsService.get_service_reminder_time_days(session)
        time_hours = await SettingsService.get_service_reminder_time_hours(session)
        interval = await SettingsService.get_service_reminder_interval_seconds(session)
    await update.message.reply_text(
        "**هشدار تمدید سرویس**\n\n"
        f"وضعیت: **{'روشن' if enabled else 'خاموش'}**\n"
        f"هشدار حجم: **{', '.join(str(value) + '٪' for value in volume_percents) or '-'}**\n"
        f"هشدار روزانه: **{', '.join(str(value) + ' روز' for value in time_days) or '-'}**\n"
        f"هشدار ساعتی: **{', '.join(str(value) + ' ساعت' for value in time_hours) or '-'}**\n"
        f"فاصله بررسی خودکار: **{interval // 60} دقیقه**\n\n"
        "متن پیام از بخش مدیریت پیام‌ها با کلید `service_expiry_reminder` قابل تغییر است.",
        reply_markup=admin_service_reminders_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


@require_auth(permission="shop")
async def service_reminders_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        enabled = not await SettingsService.service_reminders_enabled(session)
        await SettingsService.set_service_reminders_enabled(session, enabled)
    await update.message.reply_text(f"هشدار تمدید سرویس {'روشن' if enabled else 'خاموش'} شد.")
    await service_reminders_menu(update, context)


@require_auth(permission="shop")
async def service_reminder_volume_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "درصدهای هشدار حجم را با کاما بفرستید.\nمثال: `20,10`\nبرای غیرفعال کردن هشدار حجم، `-` بفرستید.",
        reply_markup=_cancel_back_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SERVICE_REMINDER_VOLUME_VALUE


@require_auth(permission="shop")
async def service_reminder_volume_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    values = _parse_positive_int_list(update.message.text, maximum=100)
    if update.message.text.strip() != "-" and not values:
        await update.message.reply_text("درصدها معتبر نیستند. مثال: `20,10`", parse_mode=constants.ParseMode.MARKDOWN)
        return SERVICE_REMINDER_VOLUME_VALUE
    async with async_session() as session:
        await SettingsService.set_service_reminder_volume_percents(session, values)
    await update.message.reply_text("درصدهای هشدار حجم ذخیره شد.")
    await service_reminders_menu(update, context)
    return ConversationHandler.END


@require_auth(permission="shop")
async def service_reminder_days_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "روزهای هشدار زمان را با کاما بفرستید.\nمثال: `3,1`\nبرای غیرفعال کردن هشدار زمان، `-` بفرستید.",
        reply_markup=_cancel_back_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SERVICE_REMINDER_DAYS_VALUE


@require_auth(permission="shop")
async def service_reminder_days_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    values = _parse_positive_int_list(update.message.text)
    if update.message.text.strip() != "-" and not values:
        await update.message.reply_text("روزها معتبر نیستند. مثال: `3,1`", parse_mode=constants.ParseMode.MARKDOWN)
        return SERVICE_REMINDER_DAYS_VALUE
    async with async_session() as session:
        await SettingsService.set_service_reminder_time_days(session, values)
    await update.message.reply_text("روزهای هشدار زمان ذخیره شد.")
    await service_reminders_menu(update, context)
    return ConversationHandler.END


@require_auth(permission="shop")
async def service_reminder_hours_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ساعت‌های هشدار زمان را با کاما بفرستید.\nمثال: `2,1`\nبرای غیرفعال کردن هشدار ساعتی، `-` بفرستید.",
        reply_markup=_cancel_back_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SERVICE_REMINDER_HOURS_VALUE


@require_auth(permission="shop")
async def service_reminder_hours_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    values = _parse_positive_int_list(update.message.text)
    if update.message.text.strip() != "-" and not values:
        await update.message.reply_text("ساعت‌ها معتبر نیستند. مثال: `2,1`", parse_mode=constants.ParseMode.MARKDOWN)
        return SERVICE_REMINDER_HOURS_VALUE
    async with async_session() as session:
        await SettingsService.set_service_reminder_time_hours(session, values)
    await update.message.reply_text("ساعت‌های هشدار زمان ذخیره شد.")
    await service_reminders_menu(update, context)
    return ConversationHandler.END


def _parse_positive_int_list(text: str, *, maximum: int | None = None) -> list[int]:
    if text.strip() == "-":
        return []
    values: list[int] = []
    for part in text.replace("،", ",").split(","):
        try:
            value = int(part.strip())
        except ValueError:
            continue
        if value <= 0:
            continue
        if maximum is not None:
            value = min(maximum, value)
        values.append(value)
    return sorted(set(values), reverse=True)


@require_auth(permission="shop")
async def shop_reset_defaults(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["shop_reset_pending"] = True
    await update.message.reply_text(
        "⚠️ با این کار تمام متن‌ها، دکمه‌ها، رنگ‌ها، ایموجی‌ها، دسته‌ها و سرویس‌های قابل فروش "
        "به نسخه پیش‌فرض برمی‌گردند.\n\nبرای ادامه، دکمه قرمز زیر را بزنید.",
        reply_markup=admin_reset_confirm_keyboard(),
    )
    return SHOP_RESET_CONFIRM


@require_auth(permission="shop")
async def shop_reset_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text != ADMIN_RESET_CONFIRM:
        await update.message.reply_text("بازگردانی لغو شد.", reply_markup=admin_shop_settings_keyboard())
        context.user_data.pop("shop_reset_pending", None)
        return ConversationHandler.END
    await update.message.reply_text(
        "برای تأیید نهایی، رمز ورود ربات ادمین را وارد کنید.\nرمز پس از بررسی از گفتگو حذف می‌شود.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return SHOP_RESET_PASSWORD


@require_auth(permission="shop")
async def shop_reset_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text
    try:
        await update.message.delete()
    except Exception:
        pass
    if password != BotConfig.ADMIN_PASSWORD:
        await update.effective_message.reply_text(
            "رمز اشتباه است؛ هیچ تغییری انجام نشد. دوباره رمز را وارد کنید یا /cancel بزنید."
        )
        return SHOP_RESET_PASSWORD

    async with async_session() as session:
        await ShopCustomizationService.reset_defaults(session)
    context.user_data.pop("shop_reset_pending", None)
    await update.message.reply_text(
        "تنظیمات ربات فروش به حالت پیش‌فرض برگشت.",
        reply_markup=admin_shop_settings_keyboard(),
    )
    return ConversationHandler.END


@require_auth(permission="shop")
async def shop_messages_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        messages = await ShopCustomizationService.list_messages(session)
    await update.message.reply_text(
        "**مدیریت پیام‌ها**\n\nپیامی را که می‌خواهید تغییر دهید انتخاب کنید.",
        reply_markup=_rows([_message_label(message.key) for message in messages], width=2),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SHOP_MESSAGE_SELECT


@require_auth(permission="shop")
async def shop_message_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        return ConversationHandler.END
    key = update.message.text.removeprefix("📝").strip()
    return await _show_shop_message_editor(update, context, key)


async def _show_shop_message_editor(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str):
    async with async_session() as session:
        message = await ShopCustomizationService.get_message_row(session, key)
    if not message:
        await update.message.reply_text("این پیام پیدا نشد.", reply_markup=admin_shop_settings_keyboard())
        return ConversationHandler.END

    context.user_data["shop_message_key"] = key
    context.user_data.pop("shop_message_field", None)
    button_type = message.response_button_type or "text"
    button_text = message.response_button_text or "-"
    button_url = message.response_button_url or "-"
    button_style = message.response_button_style or "default"
    button_premium_emoji = message.response_button_premium_emoji_id or "-"
    source_button_id = message.response_button_source_id or "-"
    premium_emoji = message.premium_emoji_id or "-"
    photo_status = "دارد" if message.photo_file_id else "ندارد"
    premium_position = {
        "left": "چپ",
        "right": "راست",
        "none": "غیرفعال",
    }.get(message.premium_emoji_position, "غیرفعال")
    extra_note = (
        "\n\nایموجی پریمیوم پیام:\n"
        f"آیدی فعلی: {premium_emoji}\n"
        f"جای فعلی: {premium_position}\n"
        "\n\nتنظیم دکمه جواب همین پیام:\n"
        f"نوع فعلی: {button_type}\n"
        f"متن دکمه: {button_text}\n"
        f"لینک/متن کپی: {button_url}\n"
        f"رنگ دکمه جواب: {button_style}\n"
        f"ایموجی پریمیوم دکمه جواب: {button_premium_emoji}\n"
        f"دکمه متصل: #{source_button_id}\n\n"
        "برای تغییر نوع دکمه، یکی از گزینه‌های کیبورد را بزنید.\n"
        "برای تغییر متن دکمه بنویسید: متن دکمه: دریافت لینک\n"
        "برای تنظیم لینک یا متن قابل کپی بنویسید: لینک دکمه: https://example.com\n"
        "برای حذف لینک/متن کپی بنویسید: لینک دکمه: -"
    )
    placeholder_note = MESSAGE_PLACEHOLDER_HINTS.get(key, "")
    await update.message.reply_text(
        f"ویرایش پیام {key}\n\n"
        f"عکس پیام: {photo_status}\n\n"
        f"متن فعلی:\n\n{message.text}{placeholder_note}{extra_note}\n\n"
        "متن جدید را ارسال کنید؛ اگر می‌خواهید پاسخ عکس‌دار باشد، عکس را همراه کپشن بفرستید.",
        reply_markup=admin_response_button_keyboard(),
    )
    return SHOP_MESSAGE_TEXT


@require_auth(permission="shop")
async def shop_message_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        context.user_data.pop("shop_message_key", None)
        return ConversationHandler.END
    key = context.user_data.get("shop_message_key")
    raw_value = (update.message.text or update.message.caption or "").strip()
    pending_field = context.user_data.get("shop_message_field")
    if pending_field == "premium_emoji_id":
        premium_emoji_id = _read_custom_emoji_id(update.message, raw_value)
        if premium_emoji_id == "":
            await update.message.reply_text(
                "ایموجی پریمیوم را مستقیم ارسال کنید تا آیدی‌اش خودکار خوانده شود. برای حذف، `-` بفرستید.",
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            return SHOP_MESSAGE_TEXT
        async with async_session() as session:
            await ShopCustomizationService.update_message_settings(
                session,
                key,
                premium_emoji_id=premium_emoji_id,
                premium_emoji_position="left" if premium_emoji_id else "none",
            )
        await update.message.reply_text("ایموجی پریمیوم پیام ذخیره شد.")
        return await _show_shop_message_editor(update, context, key)
    if pending_field == "premium_emoji_position":
        position = EMOJI_POSITION_VALUES.get(raw_value)
        if not position:
            await update.message.reply_text("جای ایموجی را از دکمه‌های چپ یا راست انتخاب کنید.")
            return SHOP_MESSAGE_TEXT
        async with async_session() as session:
            await ShopCustomizationService.update_message_settings(
                session,
                key,
                premium_emoji_position=position,
            )
        await update.message.reply_text("جای ایموجی پریمیوم پیام ذخیره شد.")
        return await _show_shop_message_editor(update, context, key)
    if pending_field == "response_button_style":
        style = raw_value if raw_value in STYLE_VALUES else None
        if style is None:
            await update.message.reply_text("رنگ معتبر نیست.", reply_markup=admin_style_keyboard())
            return SHOP_MESSAGE_TEXT
        async with async_session() as session:
            await ShopCustomizationService.update_message_settings(
                session,
                key,
                response_button_style=None if style == "default" else style,
            )
        await update.message.reply_text("رنگ دکمه جواب ذخیره شد.")
        return await _show_shop_message_editor(update, context, key)
    if pending_field == "response_button_premium_emoji_id":
        premium_emoji_id = _read_custom_emoji_id(update.message, raw_value)
        if premium_emoji_id == "":
            await update.message.reply_text("ایموجی پریمیوم معتبر بفرستید یا برای حذف `-` ارسال کنید.")
            return SHOP_MESSAGE_TEXT
        async with async_session() as session:
            await ShopCustomizationService.update_message_settings(
                session,
                key,
                response_button_premium_emoji_id=premium_emoji_id,
            )
        await update.message.reply_text("ایموجی پریمیوم دکمه جواب ذخیره شد.")
        return await _show_shop_message_editor(update, context, key)
    if pending_field == "response_button_source_id":
        button_id = _parse_hash_id(raw_value)
        async with async_session() as session:
            button = await ShopCustomizationService.get_button(session, button_id) if button_id else None
            if button:
                await ShopCustomizationService.update_message_settings(
                    session,
                    key,
                    response_button_source_id=button.id,
                    response_button_type="inline_action",
                    response_button_text=None,
                )
        if not button:
            await update.message.reply_text("دکمه معتبر نیست؛ یکی از دکمه‌های فهرست را انتخاب کنید.")
            return SHOP_MESSAGE_TEXT
        await update.message.reply_text("دکمه موجود به جواب متصل شد و اکشن آن حفظ می‌شود.")
        return await _show_shop_message_editor(update, context, key)
    if raw_value == ADMIN_EDIT_PREMIUM_EMOJI:
        context.user_data["shop_message_field"] = "premium_emoji_id"
        await update.message.reply_text(
            "ایموجی پریمیوم را مستقیم ارسال کنید تا آیدی آن خودکار خوانده شود.\nبرای حذف ایموجی، `-` بفرستید.",
            reply_markup=_cancel_back_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return SHOP_MESSAGE_TEXT
    if raw_value == ADMIN_EDIT_PREMIUM_EMOJI_POSITION:
        context.user_data["shop_message_field"] = "premium_emoji_position"
        await update.message.reply_text(
            "جای نمایش ایموجی پریمیوم را انتخاب کنید.",
            reply_markup=admin_emoji_position_keyboard(),
        )
        return SHOP_MESSAGE_TEXT
    if raw_value == ADMIN_RESPONSE_EDIT_STYLE:
        context.user_data["shop_message_field"] = "response_button_style"
        await update.message.reply_text("رنگ دکمه جواب را انتخاب کنید.", reply_markup=admin_style_keyboard())
        return SHOP_MESSAGE_TEXT
    if raw_value == ADMIN_RESPONSE_EDIT_PREMIUM_EMOJI:
        context.user_data["shop_message_field"] = "response_button_premium_emoji_id"
        await update.message.reply_text(
            "ایموجی پریمیوم دکمه جواب را بفرستید تا آیدی آن خودکار خوانده شود. برای حذف `-` بفرستید.",
            reply_markup=_cancel_back_keyboard(),
        )
        return SHOP_MESSAGE_TEXT
    if raw_value == ADMIN_RESPONSE_SELECT_EXISTING:
        async with async_session() as session:
            buttons = await ShopCustomizationService.list_buttons(session)
        labels = [_button_label(button) for button in buttons if button.is_enabled]
        if not labels:
            await update.message.reply_text("دکمه فعالی برای اتصال وجود ندارد.")
            return SHOP_MESSAGE_TEXT
        context.user_data["shop_message_field"] = "response_button_source_id"
        await update.message.reply_text(
            "دکمه‌ای را انتخاب کنید. دکمه شیشه‌ای جواب، همان اکشن این دکمه را اجرا خواهد کرد.",
            reply_markup=_rows(labels, width=1),
        )
        return SHOP_MESSAGE_TEXT
    if raw_value in RESPONSE_BUTTON_VALUES:
        async with async_session() as session:
            await ShopCustomizationService.update_message_settings(
                session,
                key,
                response_button_type=RESPONSE_BUTTON_VALUES[raw_value],
            )
        await update.message.reply_text("نوع دکمه جواب پیام ذخیره شد.")
        return await _show_shop_message_editor(update, context, key)
    if raw_value.startswith("متن دکمه:"):
        button_text = raw_value.split(":", 1)[1].strip()
        if not button_text:
            await update.message.reply_text("بعد از «متن دکمه:» یک عنوان بنویسید.")
            return SHOP_MESSAGE_TEXT
        async with async_session() as session:
            await ShopCustomizationService.update_message_settings(session, key, response_button_text=button_text)
        await update.message.reply_text("متن دکمه جواب پیام ذخیره شد.")
        return await _show_shop_message_editor(update, context, key)
    if raw_value.startswith("لینک دکمه:"):
        button_url = raw_value.split(":", 1)[1].strip()
        value = None if button_url in {"", "-", "حذف"} else button_url
        async with async_session() as session:
            await ShopCustomizationService.update_message_settings(session, key, response_button_url=value)
        await update.message.reply_text("لینک/متن کپی دکمه جواب پیام ذخیره شد.")
        return await _show_shop_message_editor(update, context, key)

    message_text, parse_mode, photo_file_id = _message_text_for_storage(update.message)
    async with async_session() as session:
        message = await ShopCustomizationService.update_message(
            session,
            key,
            message_text,
            parse_mode=parse_mode,
            photo_file_id=photo_file_id,
        )

    context.user_data.pop("shop_message_key", None)
    if not message:
        await update.message.reply_text("پیام ذخیره نشد.", reply_markup=admin_shop_settings_keyboard())
        return ConversationHandler.END

    await update.message.reply_text(
        f"پیام `{key}` ذخیره شد.",
    )
    return await shop_messages_start(update, context)


@require_auth(permission="shop")
async def shop_buttons_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "**مدیریت دکمه‌ها**\n\nمنویی را که می‌خواهید ویرایش کنید انتخاب کنید.",
        reply_markup=admin_shop_menus_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SHOP_BUTTON_MENU


@require_auth(permission="shop")
async def shop_button_menu_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        return ConversationHandler.END
    menu = SHOP_MENU_LABELS.get(update.message.text)
    if not menu:
        await update.message.reply_text("منوی انتخاب‌شده معتبر نیست.", reply_markup=admin_shop_menus_keyboard())
        return SHOP_BUTTON_MENU

    context.user_data["shop_button_menu"] = menu
    return await _show_shop_button_list(update, context)


async def _show_shop_button_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu = context.user_data.get("shop_button_menu")
    if not menu:
        return await shop_buttons_start(update, context)

    async with async_session() as session:
        buttons = await ShopCustomizationService.list_buttons(session, menu)

    if not buttons:
        labels = [ADMIN_ADD_BUTTON]
    else:
        labels = [_button_label(button) for button in buttons]
        labels.append(ADMIN_ADD_BUTTON)

    await update.message.reply_text(
        "دکمه موردنظر را انتخاب کنید.",
        reply_markup=_rows(labels, width=1),
    )
    return SHOP_BUTTON_SELECT


async def _show_shop_button_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    button_id = context.user_data.get("shop_button_id")
    async with async_session() as session:
        button = await ShopCustomizationService.get_button(session, button_id)

    if not button:
        await update.message.reply_text("دکمه پیدا نشد.", reply_markup=admin_shop_settings_keyboard())
        return ConversationHandler.END

    await update.message.reply_text(
        "**ویرایش دکمه**\n\n"
        f"اکشن: `{button.action}`\n"
        f"متن: {button.text}\n"
        f"ایموجی: {button.emoji or '-'}\n"
        f"جای ایموجی: {'راست' if button.emoji_position == 'right' else 'چپ'}\n"
        f"ایموجی پریمیوم: `{button.premium_emoji_id or '-'}`\n"
        f"جای ایموجی پریمیوم: {'راست' if button.premium_emoji_position == 'right' else 'چپ'}\n"
        f"رنگ: `{button.style or 'default'}`\n"
        f"چینش: ردیف {button.row}، ستون {button.col}\n"
        f"وضعیت: {'فعال' if button.is_enabled else 'غیرفعال'}",
        reply_markup=admin_shop_button_edit_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SHOP_BUTTON_OPTION


@require_auth(permission="shop")
async def shop_button_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        context.user_data.pop("shop_button_id", None)
        return ConversationHandler.END
    if update.message.text == ADMIN_ADD_BUTTON:
        await update.message.reply_text("متن دکمه سفارشی جدید را ارسال کنید.")
        return SHOP_BUTTON_ADD_TEXT

    button_id = _parse_hash_id(update.message.text)
    if button_id is None:
        await update.message.reply_text("دکمه معتبر نیست.")
        return SHOP_BUTTON_SELECT

    async with async_session() as session:
        button = await ShopCustomizationService.get_button(session, button_id)

    if not button:
        await update.message.reply_text("دکمه پیدا نشد.", reply_markup=admin_shop_settings_keyboard())
        return ConversationHandler.END

    context.user_data["shop_button_id"] = button_id
    return await _show_shop_button_options(update, context)


@require_auth(permission="shop")
async def shop_button_add_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        context.user_data.pop("shop_custom_button_text", None)
        return ConversationHandler.END
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("متن دکمه نمی‌تواند خالی باشد.")
        return SHOP_BUTTON_ADD_TEXT
    context.user_data["shop_custom_button_text"] = text
    await update.message.reply_text("متن جوابی که با زدن این دکمه نمایش داده شود را ارسال کنید.")
    return SHOP_BUTTON_ADD_MESSAGE


@require_auth(permission="shop")
async def shop_button_add_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        context.user_data.pop("shop_custom_button_text", None)
        return ConversationHandler.END
    menu = context.user_data.get("shop_button_menu")
    text = context.user_data.get("shop_custom_button_text")
    if not menu or not text:
        await update.message.reply_text("اطلاعات دکمه کامل نیست.", reply_markup=admin_shop_settings_keyboard())
        return ConversationHandler.END

    async with async_session() as session:
        button = await ShopCustomizationService.create_custom_button(session, menu, text, update.message.text)

    context.user_data.pop("shop_custom_button_text", None)
    await update.message.reply_text(
        f"دکمه سفارشی **{button.text}** ساخته شد.",
        reply_markup=admin_shop_settings_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


@require_auth(permission="shop")
async def shop_button_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        context.user_data.pop("shop_button_field", None)
        return ConversationHandler.END
    option = update.message.text
    button_id = context.user_data.get("shop_button_id")

    if option == ADMIN_TOGGLE_ENABLED:
        async with async_session() as session:
            button = await ShopCustomizationService.get_button(session, button_id)
            if button:
                await ShopCustomizationService.update_button(session, button_id, is_enabled=not button.is_enabled)
        await update.message.reply_text("وضعیت دکمه تغییر کرد.")
        return await _show_shop_button_options(update, context)
    if option == ADMIN_DELETE_BUTTON:
        async with async_session() as session:
            deleted = await ShopCustomizationService.delete_button(session, button_id)
        context.user_data.pop("shop_button_id", None)
        if deleted:
            await update.message.reply_text("دکمه حذف شد.")
            return await _show_shop_button_list(update, context)
        await update.message.reply_text("دکمه حذف نشد.", reply_markup=admin_shop_settings_keyboard())
        return ConversationHandler.END

    field_map = {
        ADMIN_EDIT_TEXT: ("text", "متن جدید دکمه را ارسال کنید."),
        ADMIN_EDIT_EMOJI: ("emoji", "ایموجی جدید را ارسال کنید. برای حذف، `-` بفرستید."),
        ADMIN_EDIT_PREMIUM_EMOJI: ("premium_emoji_id", "خود ایموجی پریمیوم را ارسال کنید تا آیدی‌اش خودکار خوانده شود. اگر آیدی عددی را دارید می‌توانید همان را بفرستید. برای حذف، `-` بفرستید."),
        ADMIN_EDIT_PREMIUM_EMOJI_POSITION: ("premium_emoji_position", "جای ایموجی پریمیوم را انتخاب کنید."),
        ADMIN_EDIT_EMOJI_POSITION: ("emoji_position", "جای ایموجی کنار متن را انتخاب کنید."),
        ADMIN_EDIT_STYLE: ("style", "رنگ دکمه را انتخاب کنید."),
        ADMIN_EDIT_POSITION: ("position", "چینش جدید را با فرمت `row,col` ارسال کنید. مثال: `1,0`"),
    }
    if option not in field_map:
        await update.message.reply_text("گزینه معتبر نیست.", reply_markup=admin_shop_button_edit_keyboard())
        return SHOP_BUTTON_OPTION

    field, prompt = field_map[option]
    context.user_data["shop_button_field"] = field
    await update.message.reply_text(
        prompt,
        reply_markup=admin_style_keyboard() if field == "style" else admin_emoji_position_keyboard() if field in {"emoji_position", "premium_emoji_position"} else None,
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SHOP_BUTTON_VALUE


@require_auth(permission="shop")
async def shop_button_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        context.user_data.pop("shop_button_field", None)
        return ConversationHandler.END
    button_id = context.user_data.get("shop_button_id")
    field = context.user_data.get("shop_button_field")
    raw_value = (update.message.text or update.message.caption or "").strip()
    updates = {}

    if field == "position":
        try:
            row_raw, col_raw = re.split(r"\s*,\s*", raw_value, maxsplit=1)
            updates = {"row": int(row_raw), "col": int(col_raw)}
        except (ValueError, TypeError):
            await update.message.reply_text("فرمت چینش درست نیست. مثال: `1,0`", parse_mode=constants.ParseMode.MARKDOWN)
            return SHOP_BUTTON_VALUE
    elif field == "style":
        value = raw_value if raw_value in STYLE_VALUES else None
        updates = {"style": None if value == "default" else value}
    elif field in {"emoji_position", "premium_emoji_position"}:
        value = EMOJI_POSITION_VALUES.get(raw_value)
        if not value:
            await update.message.reply_text("جای ایموجی را از بین چپ یا راست انتخاب کنید.", reply_markup=admin_emoji_position_keyboard())
            return SHOP_BUTTON_VALUE
        updates = {field: value}
    elif field in {"emoji", "premium_emoji_id"}:
        if field == "premium_emoji_id":
            value = _read_custom_emoji_id(update.message, raw_value)
            if value == "":
                await update.message.reply_text("ایموجی پریمیوم معتبر یا آیدی عددی آن را بفرستید. برای حذف، `-` بفرستید.", parse_mode=constants.ParseMode.MARKDOWN)
                return SHOP_BUTTON_VALUE
            updates = {field: value}
        else:
            updates = {field: _normalize_nullable(raw_value)}
    elif field == "text":
        if not raw_value:
            await update.message.reply_text("متن دکمه نمی‌تواند خالی باشد.")
            return SHOP_BUTTON_VALUE
        updates = {"text": raw_value}

    async with async_session() as session:
        button = await ShopCustomizationService.update_button(session, button_id, **updates)

    context.user_data.pop("shop_button_field", None)
    if not button:
        await update.message.reply_text("دکمه ذخیره نشد.", reply_markup=admin_shop_settings_keyboard())
        return ConversationHandler.END

    await update.message.reply_text("دکمه ذخیره شد.")
    return await _show_shop_button_options(update, context)


@require_auth(permission="shop")
async def shop_plans_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        plans = await ShopCustomizationService.list_plans(session)
    await update.message.reply_text(
        "**مدیریت سرویس‌ها**\n\n"
        f"تعداد کل سرویس‌ها: **{len(plans)}**\n"
        "سرویس موردنظر را انتخاب کنید یا سرویس جدید بسازید.",
        reply_markup=_shop_plan_management_keyboard(plans),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SHOP_PLAN_SELECT


@require_auth(permission="shop")
async def shop_plan_management_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = (query.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "noop":
        return SHOP_PLAN_SELECT
    if action == "back":
        await query.edit_message_text("از مدیریت سرویس‌ها خارج شدید.")
        await query.message.reply_text(
            "به تنظیمات ربات فروش برگشتید.",
            reply_markup=admin_shop_settings_keyboard(),
        )
        return ConversationHandler.END
    if action == "add":
        await query.edit_message_text("در حال ساخت سرویس جدید")
        await query.message.reply_text(
            "حجم سرویس جدید را به گیگ ارسال کنید؛ برای حجم نامحدود، `نامحدود` بفرستید. مثال: `30`",
            reply_markup=_cancel_back_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return SHOP_PLAN_ADD_VOLUME

    async with async_session() as session:
        plans = await ShopCustomizationService.list_plans(session)
    if action == "page":
        page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        await query.edit_message_reply_markup(
            reply_markup=_shop_plan_management_keyboard(plans, page)
        )
        return SHOP_PLAN_SELECT

    plan_id = int(parts[2]) if action == "select" and len(parts) > 2 and parts[2].isdigit() else None
    if plan_id is None:
        await query.message.reply_text("سرویس انتخاب‌شده معتبر نیست.")
        return SHOP_PLAN_SELECT
    context.user_data["shop_plan_id"] = plan_id
    await query.edit_message_text("سرویس انتخاب شد.")
    return await _show_shop_plan_options(update, context)


@require_auth(permission="shop")
async def shop_categories_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        categories = await ShopCustomizationService.list_categories(session)
    labels = [_category_label(category) for category in categories]
    labels.append(ADMIN_ADD_CATEGORY)
    await update.message.reply_text(
        "**مدیریت دسته‌های سرویس**\n\n"
        "برای اینکه منوی خرید سه دسته داشته باشد، سه دسته بسازید و بعد هر سرویس را از بخش مدیریت سرویس‌ها به یکی از این کلیدها وصل کنید.",
        reply_markup=_rows(labels, width=1),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SHOP_CATEGORY_SELECT


@require_auth(permission="shop")
async def shop_category_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        return ConversationHandler.END
    if update.message.text == ADMIN_ADD_CATEGORY:
        await update.message.reply_text(
            "دسته جدید را با فرمت `key|عنوان|emoji` ارسال کنید.\n"
            "مثال: `reality|سرورهای Reality|🌐`\n"
            "اگر ایموجی نمی‌خواهید: `vip|سرورهای VIP`",
            reply_markup=_cancel_back_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return SHOP_CATEGORY_ADD

    category_id = _parse_hash_id(update.message.text)
    async with async_session() as session:
        categories = await ShopCustomizationService.list_categories(session)
    matches = [
        category
        for category in categories
        if (category_id is not None and category.id == category_id)
        or _category_label(category) == update.message.text
    ]
    if len(matches) != 1:
        await update.message.reply_text("دسته انتخاب‌شده معتبر نیست.")
        return SHOP_CATEGORY_SELECT
    return await _show_shop_category_options(update, context, matches[0].key)


@require_auth(permission="shop")
async def shop_category_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        return ConversationHandler.END
    parts = [part.strip() for part in update.message.text.split("|")]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        await update.message.reply_text("فرمت درست نیست. مثال: `reality|سرورهای Reality|🌐`", parse_mode=constants.ParseMode.MARKDOWN)
        return SHOP_CATEGORY_ADD

    key, title = parts[0], parts[1]
    emoji = parts[2] if len(parts) >= 3 and parts[2] else "🧩"
    async with async_session() as session:
        category = await ShopCustomizationService.ensure_category(session, key, title)
        await ShopCustomizationService.update_category(session, category.key, title=title, emoji=emoji, is_active=True)

    await update.message.reply_text(
        f"دسته **{title}** با کلید `{category.key}` ذخیره شد.",
        reply_markup=admin_shop_settings_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def _show_shop_category_options(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str):
    async with async_session() as session:
        category = await ShopCustomizationService.get_category(session, key)
        if category:
            plan_count, config_count = await ShopCustomizationService.category_usage(session, key)
    if not category:
        await update.message.reply_text("دسته پیدا نشد.", reply_markup=admin_shop_settings_keyboard())
        return ConversationHandler.END

    context.user_data["shop_category_key"] = key
    context.user_data.pop("shop_category_field", None)
    await update.message.reply_text(
        f"**ویرایش دسته {category.title}**\n\n"
        f"کلید ثابت: `{category.key}`\n"
        f"عنوان: {category.title}\n"
        f"ایموجی: {category.emoji or '-'}\n"
        f"ایموجی پریمیوم: `{category.premium_emoji_id or '-'}`\n"
        f"جای ایموجی: {'راست' if category.emoji_position == 'right' else 'چپ'}\n"
        f"رنگ: `{category.style or 'default'}`\n"
        f"ترتیب: {category.display_order}\n"
        f"وضعیت: {'فعال' if category.is_active else 'غیرفعال'}\n"
        f"سرویس‌های متصل: {plan_count}\n"
        f"کانفیگ‌های متصل: {config_count}",
        reply_markup=admin_shop_category_edit_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SHOP_CATEGORY_OPTION


@require_auth(permission="shop")
async def shop_category_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        context.user_data.pop("shop_category_key", None)
        return ConversationHandler.END
    key = context.user_data.get("shop_category_key")
    if not key:
        return await shop_categories_start(update, context)

    option = update.message.text
    if option == ADMIN_TOGGLE_ENABLED:
        async with async_session() as session:
            category = await ShopCustomizationService.get_category(session, key)
            if category:
                await ShopCustomizationService.update_category(session, key, is_active=not category.is_active)
        await update.message.reply_text("وضعیت دسته تغییر کرد.")
        return await _show_shop_category_options(update, context, key)

    if option == ADMIN_DELETE_CATEGORY:
        async with async_session() as session:
            deleted = await ShopCustomizationService.delete_category(session, key)
        if deleted:
            context.user_data.pop("shop_category_key", None)
            await update.message.reply_text("دسته حذف شد. سرویس‌ها و کانفیگ‌های متصل بدون تغییر باقی ماندند.")
            return await shop_categories_start(update, context)
        if key == "default":
            await update.message.reply_text("دسته پیش‌فرض قابل حذف نیست.")
        else:
            await update.message.reply_text("دسته حذف نشد.")
        return await _show_shop_category_options(update, context, key)

    fields = {
        ADMIN_EDIT_TITLE: ("title", "عنوان جدید دسته را ارسال کنید."),
        ADMIN_EDIT_EMOJI: ("emoji", "ایموجی عادی را ارسال کنید. برای حذف، `-` بفرستید."),
        ADMIN_EDIT_PREMIUM_EMOJI: (
            "premium_emoji_id",
            "خود ایموجی پریمیوم را ارسال کنید تا آیدی‌اش خودکار خوانده شود. برای حذف، `-` بفرستید.",
        ),
        ADMIN_EDIT_EMOJI_POSITION: ("emoji_position", "جای ایموجی را انتخاب کنید."),
        ADMIN_EDIT_STYLE: ("style", "رنگ دکمه دسته را انتخاب کنید."),
        ADMIN_EDIT_ORDER: ("display_order", "شماره ترتیب نمایش دسته را ارسال کنید."),
    }
    selected = fields.get(option)
    if not selected:
        await update.message.reply_text("گزینه معتبر نیست.", reply_markup=admin_shop_category_edit_keyboard())
        return SHOP_CATEGORY_OPTION

    field, prompt = selected
    context.user_data["shop_category_field"] = field
    keyboard = admin_style_keyboard() if field == "style" else admin_emoji_position_keyboard() if field == "emoji_position" else _cancel_back_keyboard()
    await update.message.reply_text(prompt, reply_markup=keyboard, parse_mode=constants.ParseMode.MARKDOWN)
    return SHOP_CATEGORY_VALUE


@require_auth(permission="shop")
async def shop_category_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = context.user_data.get("shop_category_key")
    field = context.user_data.get("shop_category_field")
    if not key or not field:
        return await shop_categories_start(update, context)

    raw_value = update.message.text.strip()
    if field == "title":
        if not raw_value:
            await update.message.reply_text("عنوان دسته نمی‌تواند خالی باشد.")
            return SHOP_CATEGORY_VALUE
        value = raw_value
    elif field == "emoji":
        value = _normalize_nullable(raw_value)
    elif field == "premium_emoji_id":
        value = _read_custom_emoji_id(update.message, raw_value)
        if value == "":
            await update.message.reply_text("یک ایموجی پریمیوم معتبر یا آیدی عددی آن را ارسال کنید.")
            return SHOP_CATEGORY_VALUE
    elif field == "emoji_position":
        value = EMOJI_POSITION_VALUES.get(raw_value)
        if not value:
            await update.message.reply_text("جای ایموجی را از بین چپ یا راست انتخاب کنید.")
            return SHOP_CATEGORY_VALUE
    elif field == "style":
        value = raw_value if raw_value in STYLE_VALUES else None
        if value is None:
            await update.message.reply_text("رنگ معتبر نیست.", reply_markup=admin_style_keyboard())
            return SHOP_CATEGORY_VALUE
    elif field == "display_order":
        try:
            value = int(raw_value)
        except ValueError:
            await update.message.reply_text("ترتیب باید فقط عدد باشد.")
            return SHOP_CATEGORY_VALUE
    else:
        return await _show_shop_category_options(update, context, key)

    async with async_session() as session:
        category = await ShopCustomizationService.update_category(session, key, **{field: value})
    context.user_data.pop("shop_category_field", None)
    if not category:
        await update.message.reply_text("دسته ذخیره نشد.")
        return ConversationHandler.END
    await update.message.reply_text("تغییرات دسته ذخیره شد.")
    return await _show_shop_category_options(update, context, key)


@require_auth(permission="shop")
async def shop_plan_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        context.user_data.pop("shop_plan_id", None)
        return ConversationHandler.END
    if update.message.text == ADMIN_ADD_PLAN:
        await update.message.reply_text(
            "حجم سرویس جدید را به گیگ ارسال کنید؛ برای حجم نامحدود، `نامحدود` بفرستید. مثال: `30`",
            reply_markup=_cancel_back_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return SHOP_PLAN_ADD_VOLUME

    plan_id = _parse_hash_id(update.message.text)
    if plan_id is None:
        await update.message.reply_text("پلن معتبر نیست.")
        return SHOP_PLAN_SELECT

    context.user_data["shop_plan_id"] = plan_id
    return await _show_shop_plan_options(update, context)


async def _show_shop_plan_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_id = context.user_data.get("shop_plan_id")
    async with async_session() as session:
        plan = await ShopCustomizationService.get_plan(session, plan_id)
        price = await PriceService.get_plan_price(session, plan) if plan else None
        panel = await ProvisioningService.panel_for_plan(session, plan) if plan else None

    if not plan:
        await update.effective_message.reply_text(
            "پلن پیدا نشد.",
            reply_markup=admin_shop_settings_keyboard(),
        )
        return ConversationHandler.END

    await update.effective_message.reply_text(
        "**ویرایش سرویس**\n\n"
        f"شناسه: `#{plan.id}`\n"
        f"حجم: **{_volume_label(plan.volume_gb)}**\n"
        f"عنوان: {plan.title}\n"
        f"دسته‌بندی: `{plan.category_key}`\n"
        f"قیمت: **{price or 0:,} تومان**\n"
        f"ایموجی: {plan.emoji or '-'}\n"
        f"جای ایموجی: {'راست' if plan.emoji_position == 'right' else 'چپ'}\n"
        f"ایموجی پریمیوم: `{plan.premium_emoji_id or '-'}`\n"
        f"جای ایموجی پریمیوم: {'راست' if plan.premium_emoji_position == 'right' else 'چپ'}\n"
        f"رنگ: `{plan.style or 'default'}`\n"
        f"ترتیب: {plan.display_order}\n"
        f"ساخت از پنل: **{'روشن' if plan.provision_enabled else 'خاموش'}**\n"
        f"حالت تامین: **{_provision_mode_label(plan.provision_mode)}**\n"
        f"پنل ساخت: `{plan.provision_panel_key or (panel.key if panel else '-')}`\n"
        f"پیشوند نام ساب: `{plan.name_prefix or '-'}`\n"
        f"حجم واقعی ساخت/تمدید: **{_volume_label(plan.provision_volume_gb if plan.provision_volume_gb is not None else plan.volume_gb)}**\n"
        f"نوع زمان ساخت: **{_provision_time_mode_label(plan.provision_time_mode)}**\n"
        f"مدت واقعی ساخت/تمدید: **{plan.provision_duration_days if plan.provision_duration_days is not None else plan.duration_days} روز**\n"
        f"محدودیت کاربر لینک ساب: **{_subscription_device_limit_label(plan.subscription_device_limit)}**\n"
        f"تمدید: **{'روشن' if plan.renew_enabled else 'خاموش'}**\n"
        f"وضعیت: {'فعال' if plan.is_active else 'غیرفعال'}",
        reply_markup=admin_shop_plan_edit_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SHOP_PLAN_OPTION


async def _show_shop_plan_provision_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_id = context.user_data.get("shop_plan_id")
    async with async_session() as session:
        plan = await ShopCustomizationService.get_plan(session, plan_id)
        category = await ShopCustomizationService.get_category(session, plan.category_key) if plan else None
        panel = await ProvisioningService.panel_for_plan(session, plan) if plan else None
    if not plan:
        await update.effective_message.reply_text("سرویس پیدا نشد.", reply_markup=admin_shop_settings_keyboard())
        return ConversationHandler.END

    category_panel = category.provision_panel_key if category else None
    await update.effective_message.reply_text(
        "**تنظیمات ساخت از پنل**\n\n"
        f"سرویس: **{plan.title}** `#{plan.id}`\n"
        f"دسته: `{plan.category_key}`\n"
        f"ساخت خودکار پلن: **{'روشن' if plan.provision_enabled else 'خاموش'}**\n"
        f"ساخت خودکار دسته: **{'روشن' if category and category.provision_enabled else 'خاموش'}**\n"
        f"حالت تامین: **{_provision_mode_label(plan.provision_mode)}**\n"
        f"پنل سرویس: `{plan.provision_panel_key or '-'}`\n"
        f"پنل دسته: `{category_panel or '-'}`\n"
        f"پنل موثر: `{panel.key if panel else '-'}`\n"
        f"نوع پنل: `{panel.panel_type if panel else '-'}`\n"
        f"پیشوند نام ساب: `{plan.name_prefix or '-'}`\n"
        f"حجم واقعی ساخت/تمدید: **{_volume_label(plan.provision_volume_gb if plan.provision_volume_gb is not None else plan.volume_gb)}**\n"
        f"نوع زمان ساخت: **{_provision_time_mode_label(plan.provision_time_mode)}**\n"
        f"مدت واقعی ساخت/تمدید: **{plan.provision_duration_days if plan.provision_duration_days is not None else plan.duration_days} روز**\n"
        f"محدودیت کاربر لینک ساب: **{_subscription_device_limit_label(plan.subscription_device_limit)}**\n"
        f"تمدید: **{'روشن' if plan.renew_enabled else 'خاموش'}**\n\n"
        "حالت‌ها:\n"
        "`انبار فقط`: فقط از لینک‌های آماده می‌فروشد.\n"
        "`اول انبار بعد پنل`: اول انبار، اگر نبود از پنل می‌سازد.\n"
        "`فقط پنل`: همیشه مستقیم از پنل می‌سازد.",
        reply_markup=admin_shop_plan_provision_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SHOP_PLAN_OPTION


@require_auth(permission="shop")
async def shop_plan_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        context.user_data.pop("shop_plan_field", None)
        return ConversationHandler.END
    option = update.message.text
    plan_id = context.user_data.get("shop_plan_id")

    if option == ADMIN_PLAN_BACK_TO_EDIT:
        context.user_data.pop("shop_plan_provision_mode", None)
        return await _show_shop_plan_options(update, context)

    if option == ADMIN_PLAN_PROVISION_SETTINGS:
        context.user_data["shop_plan_provision_mode"] = True
        return await _show_shop_plan_provision_options(update, context)

    if context.user_data.get("shop_plan_provision_mode"):
        if option == ADMIN_TOGGLE_PROVISION:
            async with async_session() as session:
                plan = await ShopCustomizationService.get_plan(session, plan_id)
                if plan:
                    await ShopCustomizationService.update_plan(
                        session,
                        plan_id,
                        provision_enabled=not plan.provision_enabled,
                    )
            await update.message.reply_text("وضعیت ساخت خودکار تغییر کرد.")
            return await _show_shop_plan_provision_options(update, context)

        if option == ADMIN_TOGGLE_RENEW:
            async with async_session() as session:
                plan = await ShopCustomizationService.get_plan(session, plan_id)
                if plan:
                    await ShopCustomizationService.update_plan(
                        session,
                        plan_id,
                        renew_enabled=not plan.renew_enabled,
                    )
            await update.message.reply_text("وضعیت تمدید تغییر کرد.")
            return await _show_shop_plan_provision_options(update, context)

        provision_fields = {
            ADMIN_SET_PROVISION_MODE: (
                "provision_mode",
                "حالت تامین را انتخاب کنید.",
                admin_provision_mode_keyboard(),
            ),
            ADMIN_SET_PROVISION_PANEL: (
                "provision_panel_key",
                "پنل ساخت را انتخاب کنید یا کلیدش را بفرستید.",
                None,
            ),
            ADMIN_SET_NAME_PREFIX: (
                "name_prefix",
                "پیشوند نام ساب را بفرستید.\nمثال: `PhantomHubs_Express10gig`\nبرای پاک کردن، `-` بفرستید.",
                _cancel_back_keyboard(),
            ),
            ADMIN_SET_PROVISION_VOLUME: (
                "provision_volume_gb",
                "حجم واقعی ساخت/تمدید در پنل را به گیگ بفرستید.\nبرای استفاده از حجم نمایشی سرویس، `-` بفرستید.\nبرای ۳۰۰ گیگ: `300`",
                _cancel_back_keyboard(),
            ),
            ADMIN_SET_PROVISION_TIME_MODE: (
                "provision_time_mode",
                "نوع زمان ساخت کانفیگ از پنل را انتخاب کنید.",
                admin_provision_time_mode_keyboard(),
            ),
            ADMIN_SET_PROVISION_DURATION: (
                "provision_duration_days",
                "مدت واقعی ساخت/تمدید در پنل را به روز بفرستید.\nبرای استفاده از مدت سرویس، `-` بفرستید.\nبرای نامحدود کردن زمان، از گزینه «نوع زمان ساخت» مقدار `زمان نامحدود` را انتخاب کنید.",
                _cancel_back_keyboard(),
            ),
            ADMIN_SET_SUBSCRIPTION_DEVICE_LIMIT: (
                "subscription_device_limit",
                "محدودیت کاربر/دستگاه لینک ساب برای همین سرویس را عددی بفرستید.\n`0` یعنی نامحدود و بدون شمارش، یعنی هیچ فشاری برای ثبت دستگاه روی پنل ساب ندارد.\nمثال: `2`",
                _cancel_back_keyboard(),
            ),
        }
        selected = provision_fields.get(option)
        if selected:
            field, prompt, keyboard = selected
            context.user_data["shop_plan_field"] = field
            if field == "provision_panel_key":
                async with async_session() as session:
                    await ProvisioningService.ensure_env_panels(session)
                    panels = (await session.execute(select(ProvisionPanel).order_by(ProvisionPanel.id))).scalars().all()
                labels = [_panel_label(panel) for panel in panels]
                labels.append("استفاده از پنل دسته")
                keyboard = _rows(labels, width=1)
            await update.message.reply_text(prompt, reply_markup=keyboard, parse_mode=constants.ParseMode.MARKDOWN)
            return SHOP_PLAN_VALUE

        await update.message.reply_text("گزینه تنظیمات ساخت معتبر نیست.", reply_markup=admin_shop_plan_provision_keyboard())
        return SHOP_PLAN_OPTION

    if option == ADMIN_DELETE_PLAN:
        async with async_session() as session:
            plan = await ShopCustomizationService.get_plan(session, plan_id)
            if not plan:
                await update.message.reply_text("سرویس پیدا نشد.")
                return await shop_plans_start(update, context)
            stock = await session.execute(
                select(Config).where(
                    Config.volume_gb == plan.volume_gb,
                    Config.category_key == plan.category_key,
                    Config.is_sold.is_(False),
                )
            )
            stock_count = len(stock.scalars().all())
        context.user_data["shop_plan_delete_pending"] = True
        await update.message.reply_text(
            "⚠️ **تأیید حذف کامل سرویس**\n\n"
            f"سرویس: **{plan.title}**\n"
            f"دسته: `{plan.category_key}`\n"
            f"موجودی فروخته‌نشده‌ای که پاک می‌شود: **{stock_count} لینک**\n\n"
            "خریدها و سرویس‌های تحویل‌شده مشتریان حذف نمی‌شوند.\n"
            "قوانین رفرال وابسته به این سرویس غیرفعال خواهند شد.",
            reply_markup=admin_shop_plan_delete_confirm_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return SHOP_PLAN_OPTION

    if option == ADMIN_DELETE_PLAN_CONFIRM:
        if not context.user_data.pop("shop_plan_delete_pending", False):
            await update.message.reply_text("ابتدا دکمه «حذف کامل سرویس» را بزنید.")
            return await _show_shop_plan_options(update, context)
        async with async_session() as session:
            result = await ShopCustomizationService.delete_plan(session, plan_id)
        context.user_data.pop("shop_plan_id", None)
        if not result:
            await update.message.reply_text("سرویس پیدا نشد یا قبلاً حذف شده است.")
        else:
            await update.message.reply_text(
                "✅ **سرویس کامل حذف شد**\n\n"
                f"عنوان: {result['title']}\n"
                f"موجودی حذف‌شده: **{result['removed_inventory']} لینک**\n"
                f"قوانین جایزه غیرفعال‌شده: **{result['disabled_reward_rules']}**",
                parse_mode=constants.ParseMode.MARKDOWN,
            )
        return await shop_plans_start(update, context)

    context.user_data.pop("shop_plan_delete_pending", None)
    if option == ADMIN_TOGGLE_ENABLED:
        async with async_session() as session:
            plan = await ShopCustomizationService.get_plan(session, plan_id)
            if plan:
                await ShopCustomizationService.update_plan(session, plan_id, is_active=not plan.is_active)
        await update.message.reply_text("وضعیت سرویس تغییر کرد.")
        return await _show_shop_plan_options(update, context)

    field_map = {
        ADMIN_EDIT_TITLE: ("title", "عنوان جدید سرویس را ارسال کنید. مثال: `۳۰ گیگ ویژه`"),
        ADMIN_EDIT_PRICE: ("price", "قیمت جدید را به تومان ارسال کنید. مثال: `250000`"),
        ADMIN_EDIT_EMOJI: ("emoji", "ایموجی جدید را ارسال کنید. برای حذف، `-` بفرستید."),
        ADMIN_EDIT_PREMIUM_EMOJI: ("premium_emoji_id", "خود ایموجی پریمیوم را ارسال کنید تا آیدی‌اش خودکار خوانده شود. اگر آیدی عددی را دارید می‌توانید همان را بفرستید. برای حذف، `-` بفرستید."),
        ADMIN_EDIT_PREMIUM_EMOJI_POSITION: ("premium_emoji_position", "جای ایموجی پریمیوم را انتخاب کنید."),
        ADMIN_EDIT_EMOJI_POSITION: ("emoji_position", "جای ایموجی کنار متن سرویس را انتخاب کنید."),
        ADMIN_EDIT_STYLE: ("style", "رنگ دکمه سرویس را انتخاب کنید."),
        ADMIN_EDIT_CATEGORY: ("category_key", "دسته‌بندی سرویس را ارسال کنید. مثال: `reality|سرویس‌های Reality` یا فقط `vip`"),
        ADMIN_EDIT_ORDER: ("display_order", "ترتیب نمایش را عددی ارسال کنید. مثال: `2`"),
    }
    if option not in field_map:
        await update.message.reply_text("گزینه معتبر نیست.", reply_markup=admin_shop_plan_edit_keyboard())
        return SHOP_PLAN_OPTION

    field, prompt = field_map[option]
    context.user_data["shop_plan_field"] = field
    await update.message.reply_text(
        prompt,
        reply_markup=admin_style_keyboard() if field == "style" else admin_emoji_position_keyboard() if field in {"emoji_position", "premium_emoji_position"} else None,
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SHOP_PLAN_VALUE


@require_auth(permission="shop")
async def shop_plan_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        context.user_data.pop("shop_plan_field", None)
        return ConversationHandler.END
    plan_id = context.user_data.get("shop_plan_id")
    field = context.user_data.get("shop_plan_field")
    raw_value = update.message.text.strip()
    updates = {}

    if field == "price":
        try:
            price = int(raw_value.replace(",", ""))
        except ValueError:
            await update.message.reply_text("قیمت باید عددی باشد.")
            return SHOP_PLAN_VALUE
        if price <= 0:
            await update.message.reply_text("قیمت باید بیشتر از صفر باشد.")
            return SHOP_PLAN_VALUE
        async with async_session() as session:
            await ShopCustomizationService.update_plan(session, plan_id, price=price)
        context.user_data.pop("shop_plan_field", None)
        await update.message.reply_text("قیمت سرویس ذخیره شد.")
        return await _show_shop_plan_options(update, context)

    if field == "provision_mode":
        value = PROVISION_MODE_VALUES.get(raw_value)
        if not value:
            await update.message.reply_text("حالت تامین معتبر نیست.", reply_markup=admin_provision_mode_keyboard())
            return SHOP_PLAN_VALUE
        updates = {"provision_mode": value, "provision_enabled": value != "inventory"}
    elif field == "provision_panel_key":
        if raw_value == "استفاده از پنل دسته" or raw_value == "-":
            updates = {"provision_panel_key": None}
        else:
            panel_id = _parse_hash_id(raw_value)
            panel_text = _normalize_button_text(raw_value)
            async with async_session() as session:
                await ProvisioningService.ensure_env_panels(session)
                panels = (await session.execute(select(ProvisionPanel).order_by(ProvisionPanel.id))).scalars().all()
            panel = next(
                (
                    item
                    for item in panels
                    if (panel_id is not None and item.id == panel_id)
                    or item.key == panel_text
                    or item.title == panel_text
                    or f"({item.key})" in panel_text
                    or _normalize_button_text(_panel_label(item)) == panel_text
                ),
                None,
            )
            if not panel:
                await update.message.reply_text("پنل معتبر نیست. از لیست انتخاب کنید یا کلید پنل را بفرستید.")
                return SHOP_PLAN_VALUE
            updates = {"provision_panel_key": panel.key}
    elif field == "name_prefix":
        updates = {"name_prefix": _normalize_nullable(raw_value)}
    elif field == "provision_volume_gb":
        if raw_value == "-":
            updates = {"provision_volume_gb": None}
        else:
            try:
                value = int(raw_value.replace(",", ""))
            except ValueError:
                await update.message.reply_text("حجم واقعی باید عدد باشد یا `-` بفرستید.", parse_mode=constants.ParseMode.MARKDOWN)
                return SHOP_PLAN_VALUE
            if value < 0:
                await update.message.reply_text("حجم واقعی نمی‌تواند منفی باشد.")
                return SHOP_PLAN_VALUE
            updates = {"provision_volume_gb": value}
    elif field == "provision_time_mode":
        value = PROVISION_TIME_MODE_VALUES.get(raw_value)
        if not value:
            await update.message.reply_text("نوع زمان ساخت معتبر نیست.", reply_markup=admin_provision_time_mode_keyboard())
            return SHOP_PLAN_VALUE
        updates = {"provision_time_mode": value}
    elif field == "provision_duration_days":
        if raw_value == "-":
            updates = {"provision_duration_days": None}
        else:
            try:
                value = int(raw_value.replace(",", ""))
            except ValueError:
                await update.message.reply_text("مدت واقعی باید عدد روز باشد یا `-` بفرستید.", parse_mode=constants.ParseMode.MARKDOWN)
                return SHOP_PLAN_VALUE
            if value <= 0:
                await update.message.reply_text("مدت واقعی باید بیشتر از صفر باشد.")
                return SHOP_PLAN_VALUE
            updates = {"provision_duration_days": value}
    elif field == "subscription_device_limit":
        try:
            value = int(raw_value.replace(",", ""))
        except ValueError:
            await update.message.reply_text("محدودیت کاربر/دستگاه باید عدد باشد. برای نامحدود `0` بفرستید.", parse_mode=constants.ParseMode.MARKDOWN)
            return SHOP_PLAN_VALUE
        if value < 0:
            await update.message.reply_text("محدودیت نمی‌تواند منفی باشد.")
            return SHOP_PLAN_VALUE
        updates = {"subscription_device_limit": value}
    elif field == "display_order":
        try:
            updates = {"display_order": int(raw_value)}
        except ValueError:
            await update.message.reply_text("ترتیب باید عددی باشد.")
            return SHOP_PLAN_VALUE
    elif field == "style":
        value = raw_value if raw_value in STYLE_VALUES else None
        updates = {"style": None if value == "default" else value}
    elif field in {"emoji_position", "premium_emoji_position"}:
        value = EMOJI_POSITION_VALUES.get(raw_value)
        if not value:
            await update.message.reply_text("جای ایموجی را از بین چپ یا راست انتخاب کنید.", reply_markup=admin_emoji_position_keyboard())
            return SHOP_PLAN_VALUE
        updates = {field: value}
    elif field == "category_key":
        if not raw_value:
            await update.message.reply_text("کلید دسته‌بندی نمی‌تواند خالی باشد.")
            return SHOP_PLAN_VALUE
        if "|" in raw_value:
            category_key, category_title = [part.strip() for part in raw_value.split("|", 1)]
            updates = {"category_key": category_key, "category_title": category_title or category_key}
        else:
            updates = {"category_key": raw_value}
    elif field in {"emoji", "premium_emoji_id"}:
        if field == "premium_emoji_id":
            value = _read_custom_emoji_id(update.message, raw_value)
            if value == "":
                await update.message.reply_text("ایموجی پریمیوم معتبر یا آیدی عددی آن را بفرستید. برای حذف، `-` بفرستید.", parse_mode=constants.ParseMode.MARKDOWN)
                return SHOP_PLAN_VALUE
            updates = {field: value}
        else:
            updates = {field: _normalize_nullable(raw_value)}
    elif field == "title":
        if not raw_value:
            await update.message.reply_text("عنوان نمی‌تواند خالی باشد.")
            return SHOP_PLAN_VALUE
        updates = {"title": raw_value}

    async with async_session() as session:
        plan = await ShopCustomizationService.update_plan(session, plan_id, **updates)

    context.user_data.pop("shop_plan_field", None)
    if not plan:
        await update.message.reply_text("سرویس ذخیره نشد.", reply_markup=admin_shop_settings_keyboard())
        return ConversationHandler.END

    synced_count = 0
    if field == "subscription_device_limit":
        synced_count = await _sync_plan_subscription_device_limit(plan_id, updates["subscription_device_limit"])

    message = "سرویس ذخیره شد."
    if synced_count:
        message += f"\nمحدودیت کاربر برای {synced_count} لینک قبلی این سرویس هم به‌روزرسانی شد."
    await update.message.reply_text(message)
    if context.user_data.get("shop_plan_provision_mode"):
        return await _show_shop_plan_provision_options(update, context)
    return await _show_shop_plan_options(update, context)


@require_auth(permission="shop")
async def shop_plan_add_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        context.user_data.pop("shop_new_plan", None)
        return ConversationHandler.END
    raw_volume = update.message.text.strip().lower()
    if raw_volume in {"نامحدود", "unlimited", "0"}:
        volume = 0
    else:
        try:
            volume = int(raw_volume)
        except ValueError:
            await update.message.reply_text("حجم باید عددی باشد یا کلمه «نامحدود» را ارسال کنید.")
            return SHOP_PLAN_ADD_VOLUME
    if volume < 0:
        await update.message.reply_text("حجم نمی‌تواند منفی باشد.")
        return SHOP_PLAN_ADD_VOLUME

    context.user_data["shop_new_plan"] = {"volume": volume}
    await update.message.reply_text("عنوان نمایشی سرویس را ارسال کنید. مثال: `۳۰ گیگ ویژه`", reply_markup=_cancel_back_keyboard())
    return SHOP_PLAN_ADD_TITLE


@require_auth(permission="shop")
async def shop_plan_add_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        context.user_data.pop("shop_new_plan", None)
        return ConversationHandler.END
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text("عنوان نمی‌تواند خالی باشد.")
        return SHOP_PLAN_ADD_TITLE
    context.user_data.setdefault("shop_new_plan", {})["title"] = title
    async with async_session() as session:
        categories = await ShopCustomizationService.list_categories(session, active_only=True)
    labels = [_category_label(category) for category in categories]
    await update.message.reply_text(
        "دسته این سرویس را انتخاب کنید.",
        reply_markup=_rows(labels, width=1),
    )
    return SHOP_PLAN_ADD_CATEGORY


@require_auth(permission="shop")
async def shop_plan_add_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        context.user_data.pop("shop_new_plan", None)
        return ConversationHandler.END
    category_id = _parse_hash_id(update.message.text)
    category_key = update.message.text.strip()
    async with async_session() as session:
        categories = await ShopCustomizationService.list_categories(session, active_only=True)
    category = next(
        (
            item
            for item in categories
            if (category_id is not None and item.id == category_id)
            or item.key == category_key
            or _category_label(item) == update.message.text
        ),
        None,
    )
    if not category:
        await update.message.reply_text("دسته معتبر نیست. از لیست دکمه‌ها انتخاب کنید.")
        return SHOP_PLAN_ADD_CATEGORY
    context.user_data.setdefault("shop_new_plan", {})["category_key"] = category.key
    await update.message.reply_text("قیمت سرویس را به تومان ارسال کنید. مثال: `250000`", reply_markup=_cancel_back_keyboard())
    return SHOP_PLAN_ADD_PRICE


@require_auth(permission="shop")
async def shop_plan_add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        context.user_data.pop("shop_new_plan", None)
        return ConversationHandler.END
    try:
        price = int(update.message.text.replace(",", "").strip())
    except ValueError:
        await update.message.reply_text("قیمت باید عددی باشد.")
        return SHOP_PLAN_ADD_PRICE
    if price <= 0:
        await update.message.reply_text("قیمت باید بیشتر از صفر باشد.")
        return SHOP_PLAN_ADD_PRICE

    draft = context.user_data.get("shop_new_plan", {})
    async with async_session() as session:
        plan = await ShopCustomizationService.create_plan(
            session,
            volume_gb=draft["volume"],
            title=draft["title"],
            price=price,
            category_key=draft.get("category_key", "default"),
        )

    context.user_data.pop("shop_new_plan", None)
    await update.message.reply_text(
        f"سرویس **{plan.title}** با حجم **{_volume_label(plan.volume_gb)}** ساخته شد.",
        reply_markup=admin_shop_settings_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


@require_auth(permission="shop")
async def provision_panels_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        await ProvisioningService.ensure_env_panels(session)
        panels = (await session.execute(select(ProvisionPanel).order_by(ProvisionPanel.id))).scalars().all()
    labels = [_panel_label(panel) for panel in panels]
    await update.message.reply_text(
        "**مدیریت پنل‌های ساخت**\n\n"
        "پنل موردنظر را انتخاب کنید.\n"
        "برای پنل‌های گروهی می‌توانید گروه و HWID را جداگانه تنظیم کنید. برای Marzban/Alien/Pasarguard هم اینباندها و پروتکل‌ها قابل انتخاب هستند.",
        reply_markup=_rows(labels, width=1),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return PROVISION_PANEL_SELECT


@require_auth(permission="shop")
async def provision_panel_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        context.user_data.pop("provision_panel_key", None)
        return ConversationHandler.END
    panel_id = _parse_hash_id(update.message.text)
    raw_text = _normalize_button_text(update.message.text)
    async with async_session() as session:
        await ProvisioningService.ensure_env_panels(session)
        panels = (await session.execute(select(ProvisionPanel).order_by(ProvisionPanel.id))).scalars().all()
    panel = next(
        (
            item
            for item in panels
            if (panel_id is not None and item.id == panel_id)
            or item.key == raw_text
            or item.title == raw_text
            or f"({item.key})" in raw_text
            or _normalize_button_text(_panel_label(item)) == raw_text
        ),
        None,
    )
    if not panel:
        await update.message.reply_text("پنل انتخاب‌شده معتبر نیست.")
        return PROVISION_PANEL_SELECT
    context.user_data["provision_panel_key"] = panel.key
    return await _show_provision_panel_options(update, context)


async def _show_provision_panel_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = context.user_data.get("provision_panel_key")
    async with async_session() as session:
        panel = (
            await session.execute(select(ProvisionPanel).where(ProvisionPanel.key == key))
        ).scalar_one_or_none()
    if not panel:
        await update.effective_message.reply_text("پنل پیدا نشد.", reply_markup=admin_shop_settings_keyboard())
        return ConversationHandler.END

    group_ids = json.loads(panel.group_ids or "[]")
    inbounds = json.loads(panel.inbounds_json or "{}")
    protocols = json.loads(panel.protocols_json or "[]")
    if panel.panel_type in {"easy", "pasarguard"}:
        panel_specific = (
            f"گروه‌های پنل: `{group_ids or '-'}`\n"
            f"محدودیت HWID: `{panel.hwid_limit if panel.hwid_limit is not None else '-'}`"
        )
        if panel.panel_type == "pasarguard":
            panel_specific += (
                f"\nاینباندهای پنل: `{inbounds or '-'}`\n"
                f"پروتکل‌ها: `{protocols or '-'}`"
            )
    else:
        panel_specific = (
            f"اینباندهای پنل: `{inbounds or '-'}`\n"
            f"پروتکل‌ها: `{protocols or '-'}`"
        )
    await update.effective_message.reply_text(
        "**تنظیمات پنل ساخت**\n\n"
        f"عنوان: **{panel.title}**\n"
        f"کلید: `{panel.key}`\n"
        f"نوع: `{_panel_type_label(panel.panel_type)}`\n"
        f"آدرس: `{panel.base_url}`\n"
        f"وضعیت: **{'فعال' if panel.is_enabled else 'غیرفعال'}**\n"
        f"{panel_specific}",
        reply_markup=admin_provision_panel_keyboard(panel.panel_type),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return PROVISION_PANEL_OPTION


@require_auth(permission="shop")
async def provision_panel_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        context.user_data.pop("provision_panel_key", None)
        context.user_data.pop("provision_panel_field", None)
        return ConversationHandler.END
    key = context.user_data.get("provision_panel_key")
    if not key:
        return await provision_panels_start(update, context)
    option = update.message.text
    if option == ADMIN_TOGGLE_PANEL_ENABLED:
        async with async_session() as session:
            panel = (
                await session.execute(select(ProvisionPanel).where(ProvisionPanel.key == key))
            ).scalar_one_or_none()
            if panel:
                panel.is_enabled = not panel.is_enabled
                panel.updated_at = datetime.now(timezone.utc)
                await session.commit()
        await update.message.reply_text("وضعیت پنل تغییر کرد.")
        return await _show_provision_panel_options(update, context)

    if option == ADMIN_SET_PANEL_INBOUNDS:
        return await _show_panel_inbound_selector(update, context, refresh=True)

    fields = {
        ADMIN_SET_PANEL_GROUPS: (
            "group_ids",
            "شناسه گروه‌های همین پنل را با کاما بفرستید.\nمثال: `1,2,3`\nبرای پیش‌فرض/خالی، `-` بفرستید.",
        ),
        ADMIN_SET_PANEL_HWID: (
            "hwid_limit",
            "عدد محدودیت HWID این پنل را بفرستید.\nبرای حذف مقدار اختصاصی و استفاده از پیش‌فرض پنل، `-` بفرستید.\nمثال: `2`",
        ),
        ADMIN_SET_PANEL_PROTOCOLS: (
            "protocols_json",
            "پروتکل‌ها را با کاما بفرستید.\nمثال: `vless,trojan,shadowsocks`\nبرای خالی، `-` بفرستید.",
        ),
    }
    selected = fields.get(option)
    if not selected:
        async with async_session() as session:
            panel = (
                await session.execute(select(ProvisionPanel).where(ProvisionPanel.key == key))
            ).scalar_one_or_none()
        await update.message.reply_text(
            "گزینه معتبر نیست.",
            reply_markup=admin_provision_panel_keyboard(panel.panel_type if panel else None),
        )
        return PROVISION_PANEL_OPTION
    field, prompt = selected
    context.user_data["provision_panel_field"] = field
    await update.message.reply_text(prompt, reply_markup=_cancel_back_keyboard(), parse_mode=constants.ParseMode.MARKDOWN)
    return PROVISION_PANEL_VALUE


async def _show_panel_inbound_selector(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    refresh: bool = False,
):
    key = context.user_data.get("provision_panel_key")
    async with async_session() as session:
        panel = (
            await session.execute(select(ProvisionPanel).where(ProvisionPanel.key == key))
        ).scalar_one_or_none()
    if not panel:
        await update.effective_message.reply_text("پنل پیدا نشد.", reply_markup=admin_shop_settings_keyboard())
        return ConversationHandler.END
    if panel.panel_type == "easy":
        await update.effective_message.reply_text(
            "این پنل از نوع Easy است و اینباند جداگانه ندارد. برای این پنل از گزینه «گروه‌های پنل» استفاده کنید.",
            reply_markup=admin_provision_panel_keyboard(panel.panel_type),
        )
        return PROVISION_PANEL_OPTION

    cached_key = context.user_data.get("provision_inbounds_panel_key")
    available = context.user_data.get("provision_inbounds_available")
    if refresh or cached_key != panel.key or not isinstance(available, dict):
        try:
            available = await ProvisioningService.fetch_inbounds(panel)
        except Exception as exc:
            await update.effective_message.reply_text(
                f"دریافت اینباندها از پنل انجام نشد:\n{exc}",
                reply_markup=admin_provision_panel_keyboard(panel.panel_type),
            )
            return PROVISION_PANEL_OPTION
        if not available:
            await update.effective_message.reply_text(
                "هیچ اینباند فعالی از پنل دریافت نشد.",
                reply_markup=admin_provision_panel_keyboard(panel.panel_type),
            )
            return PROVISION_PANEL_OPTION
        selected = _selected_inbounds_from_panel(panel, available)
        context.user_data["provision_inbounds_panel_key"] = panel.key
        context.user_data["provision_inbounds_available"] = available
        context.user_data["provision_inbounds_selected"] = list(selected)
    else:
        selected = {
            tuple(item)
            for item in context.user_data.get("provision_inbounds_selected", [])
            if isinstance(item, (list, tuple)) and len(item) == 2
        }

    text = (
        "**انتخاب اینباندهای پنل**\n\n"
        f"پنل: **{panel.title}** `{panel.key}`\n"
        "اینباندهایی که روشن باشند برای ساخت کانفیگ استفاده می‌شوند.\n"
        "روی هر مورد بزنید تا روشن/خاموش شود، بعد «ذخیره» را بزنید."
    )
    markup = _inbounds_keyboard(available, selected)
    message = update.effective_message
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=markup, parse_mode=constants.ParseMode.MARKDOWN)
        except Exception:
            await message.reply_text(text, reply_markup=markup, parse_mode=constants.ParseMode.MARKDOWN)
    else:
        await message.reply_text(text, reply_markup=markup, parse_mode=constants.ParseMode.MARKDOWN)
    return PROVISION_PANEL_OPTION


@require_auth(permission="shop")
async def provision_inbound_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = (query.data or "").split(":")
    action = parts[1] if len(parts) > 1 else ""
    key = context.user_data.get("provision_panel_key")
    available = context.user_data.get("provision_inbounds_available")
    if not key or not isinstance(available, dict):
        await query.message.reply_text("ابتدا پنل را دوباره انتخاب کنید.", reply_markup=admin_provision_panel_keyboard())
        return PROVISION_PANEL_OPTION

    items = _flatten_inbounds(available)
    selected = {
        tuple(item)
        for item in context.user_data.get("provision_inbounds_selected", [])
        if isinstance(item, (list, tuple)) and len(item) == 2
    }

    if action == "toggle":
        index = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else -1
        if 0 <= index < len(items):
            item = items[index]
            if item in selected:
                selected.remove(item)
            else:
                selected.add(item)
            context.user_data["provision_inbounds_selected"] = list(selected)
        return await _show_panel_inbound_selector(update, context)

    if action == "all":
        context.user_data["provision_inbounds_selected"] = list(items)
        return await _show_panel_inbound_selector(update, context)

    if action == "none":
        context.user_data["provision_inbounds_selected"] = []
        return await _show_panel_inbound_selector(update, context)

    if action == "refresh":
        return await _show_panel_inbound_selector(update, context, refresh=True)

    if action == "back":
        await query.edit_message_text("به تنظیمات پنل برگشتید.")
        return await _show_provision_panel_options(update, context)

    if action == "save":
        configured: dict[str, list[str]] = {}
        for protocol, tag in sorted(selected):
            configured.setdefault(protocol, []).append(tag)
        async with async_session() as session:
            panel = (
                await session.execute(select(ProvisionPanel).where(ProvisionPanel.key == key))
            ).scalar_one_or_none()
            if not panel:
                await query.message.reply_text("پنل پیدا نشد.")
                return ConversationHandler.END
            panel.inbounds_json = json.dumps(configured, ensure_ascii=False)
            panel.protocols_json = json.dumps(sorted(configured), ensure_ascii=False)
            panel.updated_at = datetime.now(timezone.utc)
            await session.commit()
        context.user_data.pop("provision_inbounds_available", None)
        context.user_data.pop("provision_inbounds_selected", None)
        context.user_data.pop("provision_inbounds_panel_key", None)
        await query.edit_message_text("اینباندهای انتخاب‌شده ذخیره شدند.")
        return await _show_provision_panel_options(update, context)

    return PROVISION_PANEL_OPTION


@require_auth(permission="shop")
async def provision_panel_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        context.user_data.pop("provision_panel_key", None)
        context.user_data.pop("provision_panel_field", None)
        return ConversationHandler.END
    key = context.user_data.get("provision_panel_key")
    field = context.user_data.get("provision_panel_field")
    raw_value = update.message.text.strip()
    if not key or not field:
        return await provision_panels_start(update, context)

    if field == "group_ids":
        if raw_value == "-":
            value = None
        else:
            try:
                value = json.dumps([int(item.strip()) for item in raw_value.split(",") if item.strip()])
            except ValueError:
                await update.message.reply_text("گروه‌ها باید عددی و با کاما جدا شده باشند.")
                return PROVISION_PANEL_VALUE
    elif field == "hwid_limit":
        if raw_value == "-":
            value = None
        else:
            try:
                value = int(raw_value)
            except ValueError:
                await update.message.reply_text("محدودیت HWID باید عدد صحیح باشد.")
                return PROVISION_PANEL_VALUE
            if value < 0:
                await update.message.reply_text("محدودیت HWID نمی‌تواند منفی باشد.")
                return PROVISION_PANEL_VALUE
    elif field == "inbounds_json":
        parsed = _parse_inbounds_text(raw_value)
        if parsed is None:
            await update.message.reply_text("فرمت اینباندها معتبر نیست.")
            return PROVISION_PANEL_VALUE
        value = json.dumps(parsed, ensure_ascii=False)
    elif field == "protocols_json":
        if raw_value == "-":
            value = None
        else:
            value = json.dumps([item.strip() for item in raw_value.split(",") if item.strip()], ensure_ascii=False)
    else:
        return await _show_provision_panel_options(update, context)

    async with async_session() as session:
        panel = (
            await session.execute(select(ProvisionPanel).where(ProvisionPanel.key == key))
        ).scalar_one_or_none()
        if not panel:
            await update.message.reply_text("پنل پیدا نشد.")
            return ConversationHandler.END
        setattr(panel, field, value)
        panel.updated_at = datetime.now(timezone.utc)
        await session.commit()

    context.user_data.pop("provision_panel_field", None)
    await update.message.reply_text("تنظیمات پنل ذخیره شد.")
    return await _show_provision_panel_options(update, context)


# ---------------------------------------------------------------------------
# Crypto payments admin section
# ---------------------------------------------------------------------------

_CRYPTO_STATUS_FA = {
    "pending": "⏳ در انتظار",
    "credited": "✅ موفق",
    "underpaid": "⚠️ کسری پرداخت",
    "expired": "⛔️ منقضی",
    "cancelled": "🚫 لغو شده",
    "error": "❌ خطا",
}


def _shorten(value: str | None, head: int = 8, tail: int = 6) -> str:
    if not value:
        return "-"
    if len(value) <= head + tail + 3:
        return value
    return f"{value[:head]}…{value[-tail:]}"


def _format_invoice(invoice) -> str:
    status = _CRYPTO_STATUS_FA.get(invoice.status, invoice.status)
    when = invoice.created_at.strftime("%Y-%m-%d %H:%M") if invoice.created_at else "-"
    lines = [
        f"#{invoice.id} | {status}",
        f"👤 کاربر: `{invoice.user_id}`",
        f"💰 مبلغ: {invoice.quoted_toman:,} تومان",
        f"🪙 ارز: {invoice.coin}/{invoice.network} | مقدار: {invoice.expected_crypto}",
    ]
    if invoice.received_crypto:
        lines.append(f"📥 دریافت‌شده: {invoice.received_crypto} {invoice.coin}")
    lines.append(f"🏦 به آدرس: `{_shorten(invoice.deposit_address)}`")
    if invoice.memo:
        lines.append(f"📝 ممو: `{invoice.memo}`")
    if invoice.from_address:
        lines.append(f"📤 از آدرس: `{_shorten(invoice.from_address)}`")
    if invoice.tx_hash:
        lines.append(f"🔗 تراکنش: `{_shorten(invoice.tx_hash)}`")
    lines.append(f"🕒 {when}")
    return "\n".join(lines)


@require_auth(permission="users")
async def crypto_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    enabled = bool(available_coins())
    status_line = (
        "وضعیت: ✅ فعال" if enabled else "وضعیت: ⛔️ غیرفعال (تنظیمات کیف‌پول/شبکه ناقص است)"
    )
    await update.message.reply_text(
        "**مدیریت پرداخت‌ها**\n\n"
        f"{status_line}\n\n"
        "از این بخش می‌توانید تراکنش‌های کریپتو، درخواست‌های کارت‌به‌کارت و تنظیمات هر روش پرداخت را مدیریت کنید.",
        reply_markup=admin_crypto_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


@require_auth(permission="users")
async def crypto_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        invoices = await CryptoPaymentService.list_recent(session, limit=10)

    if not invoices:
        await update.message.reply_text(
            "هنوز هیچ تراکنش کریپتویی ثبت نشده است.",
            reply_markup=admin_crypto_keyboard(),
        )
        return

    header = "**آخرین تراکنش‌های کریپتو**\n\n"
    body = "\n\n".join(_format_invoice(invoice) for invoice in invoices)
    await update.message.reply_text(
        header + body,
        reply_markup=admin_crypto_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


@require_auth(permission="users")
async def crypto_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "آیدی عددی کاربر را برای مشاهده تراکنش‌های کریپتو ارسال کنید.",
        reply_markup=_cancel_back_keyboard(),
    )
    return CRYPTO_SEARCH_ID


@require_auth(permission="users")
async def crypto_search_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    async with async_session() as session:
        user = await UserService.search_user(session, query_text)
        if not user:
            await update.message.reply_text("کاربر پیدا نشد. دوباره ارسال کنید یا لغو را بزنید.")
            return CRYPTO_SEARCH_ID
        invoices = await CryptoPaymentService.list_for_user(session, user.telegram_id, limit=10)

    if not invoices:
        await update.message.reply_text(
            f"برای کاربر `{user.telegram_id}` تراکنش کریپتویی ثبت نشده است.",
            reply_markup=admin_crypto_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        return ConversationHandler.END

    total_credited = sum(i.quoted_toman for i in invoices if i.status == "credited")
    header = (
        f"**تراکنش‌های کریپتو کاربر** `{user.telegram_id}`\n"
        f"نمایش {len(invoices)} مورد اخیر | مجموع شارژ موفق (همین موارد): {total_credited:,} تومان\n\n"
    )
    body = "\n\n".join(_format_invoice(invoice) for invoice in invoices)
    await update.message.reply_text(
        header + body,
        reply_markup=admin_crypto_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


@require_auth(permission="users")
async def crypto_rates_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        mode = await SettingsService.get_rate_mode(session)
        margin = await SettingsService.get_margin(session)
        manual_usdt = await SettingsService.get_manual_rate(session, "USDT")
        manual_ton = await SettingsService.get_manual_rate(session, "TON")

    online_usdt = RateService.cached_online_rate("USDT")
    online_ton = RateService.cached_online_rate("TON")
    mode_fa = "🌐 آنلاین (API)" if mode == "online" else "✋ دستی"

    def _fmt(value):
        return f"{int(value):,}" if value else "-"

    text = (
        "**تنظیمات نرخ ارز**\n\n"
        f"حالت فعلی: *{mode_fa}*\n"
        f"کارمزد: *{margin}%*\n\n"
        "نرخ‌های دستی (تومان به ازای هر واحد):\n"
        f"• USDT: {manual_usdt:,}\n"
        f"• TON: {manual_ton:,}\n\n"
        "آخرین نرخ آنلاین کش‌شده:\n"
        f"• USDT: {_fmt(online_usdt)}\n"
        f"• TON: {_fmt(online_ton)}"
    )
    await update.message.reply_text(
        text,
        reply_markup=admin_crypto_rates_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


@require_auth(permission="users")
async def crypto_toggle_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        mode = await SettingsService.get_rate_mode(session)
        new_mode = "manual" if mode == "online" else "online"
        await SettingsService.set_rate_mode(session, new_mode)
    await crypto_rates_menu(update, context)


def _parse_amount(text: str) -> int | None:
    digits = text.strip().replace(",", "").replace("،", "").replace(" ", "")
    if not digits.isdigit():
        return None
    return int(digits)


@require_auth(permission="users")
async def crypto_set_margin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "درصد کارمزد را وارد کنید (مثلا 2.5):",
        reply_markup=_cancel_back_keyboard(),
    )
    return CRYPTO_SET_MARGIN_VALUE


@require_auth(permission="users")
async def crypto_set_margin_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip().replace("،", ".").replace("%", "").replace("٪", "")
    try:
        margin = float(raw)
    except ValueError:
        await update.message.reply_text("عدد نامعتبر است. دوباره وارد کنید یا لغو را بزنید.")
        return CRYPTO_SET_MARGIN_VALUE
    if margin < 0 or margin >= 100:
        await update.message.reply_text("کارمزد باید بین 0 تا 100 باشد.")
        return CRYPTO_SET_MARGIN_VALUE
    async with async_session() as session:
        await SettingsService.set_margin(session, margin)
    await update.message.reply_text(f"کارمزد روی {margin}% تنظیم شد.")
    await crypto_rates_menu(update, context)
    return ConversationHandler.END


@require_auth(permission="users")
async def crypto_set_usdt_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "نرخ دستی USDT را به تومان وارد کنید (به ازای هر ۱ USDT):",
        reply_markup=_cancel_back_keyboard(),
    )
    return CRYPTO_SET_USDT_VALUE


@require_auth(permission="users")
async def crypto_set_usdt_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount = _parse_amount(update.message.text)
    if amount is None or amount <= 0:
        await update.message.reply_text("عدد نامعتبر است. دوباره وارد کنید یا لغو را بزنید.")
        return CRYPTO_SET_USDT_VALUE
    async with async_session() as session:
        await SettingsService.set_manual_rate(session, "USDT", amount)
    await update.message.reply_text(f"نرخ دستی USDT روی {amount:,} تومان تنظیم شد.")
    await crypto_rates_menu(update, context)
    return ConversationHandler.END


@require_auth(permission="users")
async def crypto_set_ton_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "نرخ دستی TON را به تومان وارد کنید (به ازای هر ۱ TON):",
        reply_markup=_cancel_back_keyboard(),
    )
    return CRYPTO_SET_TON_VALUE


@require_auth(permission="users")
async def crypto_set_ton_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount = _parse_amount(update.message.text)
    if amount is None or amount <= 0:
        await update.message.reply_text("عدد نامعتبر است. دوباره وارد کنید یا لغو را بزنید.")
        return CRYPTO_SET_TON_VALUE
    async with async_session() as session:
        await SettingsService.set_manual_rate(session, "TON", amount)
    await update.message.reply_text(f"نرخ دستی TON روی {amount:,} تومان تنظیم شد.")
    await crypto_rates_menu(update, context)
    return ConversationHandler.END


def _format_rial_request(request) -> str:
    when = request.created_at.strftime("%Y-%m-%d %H:%M") if request.created_at else "-"
    phone = request.phone_number or "دریافت نشده"
    return (
        f"#{request.id} | {request.status}\n"
        f"👤 کاربر: `{request.user_id}`\n"
        f"💰 مبلغ: **{request.amount_toman:,} تومان**\n"
        f"📱 تماس: `{phone}`\n"
        f"💳 کارت مبدا: `{request.source_card}`\n"
        f"🧾 کد پیگیری: `{request.tracking_code}`\n"
        f"🕒 {when}"
    )


@require_auth(permission="users")
async def rial_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        requests = await RialPaymentService.list_recent(session, limit=10)
    if not requests:
        await update.message.reply_text(
            "هنوز درخواست کارت‌به‌کارتی ثبت نشده است.",
            reply_markup=admin_crypto_keyboard(),
        )
        return
    await update.message.reply_text(
        "**آخرین درخواست‌های کارت‌به‌کارت**\n\n"
        + "\n\n".join(_format_rial_request(request) for request in requests),
        reply_markup=admin_crypto_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


@require_auth(permission="users")
async def rial_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        minimum = await SettingsService.get_rial_min_amount(session)
        require_phone = await SettingsService.rial_phone_required(session)
        support_handle = await SettingsService.get_rial_support_handle(session)
    await update.message.reply_text(
        "**تنظیمات کارت‌به‌کارت**\n\n"
        f"حداقل مبلغ: **{minimum:,} تومان**\n"
        f"الزام تایید شماره در ربات: **{'روشن' if require_phone else 'خاموش'}**\n"
        f"آیدی پشتیبانی: **{support_handle}**",
        reply_markup=admin_rial_settings_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


@require_auth(permission="users")
async def rial_toggle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        enabled = not await SettingsService.rial_phone_required(session)
        await SettingsService.set_rial_phone_required(session, enabled)
    await update.message.reply_text(
        f"الزام تایید شماره در ربات برای پرداخت ریالی **{'روشن' if enabled else 'خاموش'}** شد.",
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    await rial_settings_menu(update, context)


@require_auth(permission="users")
async def rial_set_min_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "حداقل مبلغ پرداخت ریالی را به تومان وارد کنید:",
        reply_markup=_cancel_back_keyboard(),
    )
    return RIAL_SET_MIN_VALUE


@require_auth(permission="users")
async def rial_set_min_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount = _parse_amount(update.message.text)
    if amount is None or amount <= 0:
        await update.message.reply_text("مبلغ معتبر نیست. یک عدد مثبت وارد کنید.")
        return RIAL_SET_MIN_VALUE
    async with async_session() as session:
        await SettingsService.set_rial_min_amount(session, amount)
    await update.message.reply_text(f"حداقل پرداخت ریالی روی **{amount:,} تومان** تنظیم شد.", parse_mode=constants.ParseMode.MARKDOWN)
    await rial_settings_menu(update, context)
    return ConversationHandler.END


@require_auth(permission="users")
async def rial_set_support_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "یوزرنیم پشتیبانی را با یا بدون @ ارسال کنید.\nمثال: `@PhantomHubsSupport`",
        reply_markup=_cancel_back_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return RIAL_SET_SUPPORT_VALUE


@require_auth(permission="users")
async def rial_set_support_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
        await update.message.reply_text("یوزرنیم معتبر نیست. دوباره ارسال کنید.")
        return RIAL_SET_SUPPORT_VALUE
    async with async_session() as session:
        await SettingsService.set_rial_support_handle(session, username)
    await update.message.reply_text(f"آیدی پشتیبانی ریالی روی **@{username}** تنظیم شد.", parse_mode=constants.ParseMode.MARKDOWN)
    await rial_settings_menu(update, context)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد.", reply_markup=admin_main_keyboard())
    return ConversationHandler.END


async def shop_settings_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "به تنظیمات ربات فروش برگشتید.",
        reply_markup=admin_shop_settings_keyboard(),
    )
    return ConversationHandler.END


@require_auth(permission="shop")
async def shop_message_text_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("shop_message_key", None)
    return await shop_messages_start(update, context)


@require_auth(permission="shop")
async def shop_category_option_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("shop_category_key", None)
    context.user_data.pop("shop_category_field", None)
    return await shop_categories_start(update, context)


@require_auth(permission="shop")
async def shop_category_value_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = context.user_data.get("shop_category_key")
    context.user_data.pop("shop_category_field", None)
    if not key:
        return await shop_categories_start(update, context)
    return await _show_shop_category_options(update, context, key)


@require_auth(permission="shop")
async def shop_button_list_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("shop_button_menu", None)
    return await shop_buttons_start(update, context)


@require_auth(permission="shop")
async def shop_button_options_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _show_shop_button_list(update, context)


@require_auth(permission="shop")
async def shop_button_value_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("shop_button_field", None)
    return await _show_shop_button_options(update, context)


@require_auth(permission="shop")
async def shop_button_add_message_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("shop_custom_button_text", None)
    await update.message.reply_text("متن دکمه سفارشی جدید را ارسال کنید.")
    return SHOP_BUTTON_ADD_TEXT


@require_auth(permission="shop")
async def shop_plan_options_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("shop_plan_id", None)
    return await shop_plans_start(update, context)


@require_auth(permission="shop")
async def shop_plan_value_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("shop_plan_field", None)
    return await _show_shop_plan_options(update, context)


@require_auth(permission="shop")
async def shop_plan_add_title_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("shop_new_plan", None)
    await update.message.reply_text(
        "حجم سرویس جدید را به گیگ ارسال کنید؛ برای حجم نامحدود، `نامحدود` بفرستید. مثال: `30`",
        reply_markup=_cancel_back_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SHOP_PLAN_ADD_VOLUME


@require_auth(permission="shop")
async def shop_plan_add_price_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    draft = context.user_data.get("shop_new_plan", {})
    if "volume" not in draft:
        return await shop_plan_add_title_back(update, context)
    async with async_session() as session:
        categories = await ShopCustomizationService.list_categories(session, active_only=True)
    labels = [_category_label(category) for category in categories]
    await update.message.reply_text("دسته این سرویس را انتخاب کنید.", reply_markup=_rows(labels, width=1))
    return SHOP_PLAN_ADD_CATEGORY


@require_auth(permission="shop")
async def shop_plan_add_category_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عنوان نمایشی سرویس را ارسال کنید. مثال: `۳۰ گیگ ویژه`", reply_markup=_cancel_back_keyboard())
    return SHOP_PLAN_ADD_TITLE


@require_auth(owner_only=True)
async def admin_management_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        ADMIN_MANAGEMENT_MENU,
        reply_markup=admin_management_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


add_config_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_ADD_CONFIG), add_config_start)],
    states={
        CHOOSE_VOLUME_ADD: [
            CallbackQueryHandler(
                add_config_plan_callback,
                pattern=rf"^{ADD_CONFIG_CALLBACK_PREFIX}:",
            ),
            MessageHandler(filters.TEXT & ~filters.COMMAND, add_config_volume),
        ],
        COLLECT_LINKS: [
            MessageHandler(_exact_filter(DONE_ADDING_CONFIGS), done_collecting),
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, collect_links),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

edit_price_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_EDIT_PRICE), edit_price_select)],
    states={
        CHOOSE_VOLUME_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_price_enter)],
        ENTER_NEW_PRICE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_price),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

search_user_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_SEARCH_USER), search_user_start)],
    states={
        SEARCH_USER: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, search_user_result),
        ]
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

charge_wallet_conv = ConversationHandler(
    entry_points=[
        CommandHandler("chargeuser", charge_wallet_start),
        MessageHandler(_exact_filter(ADMIN_CHARGE_WALLET), charge_wallet_start),
    ],
    states={
        CHARGE_USER_ID: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, charge_wallet_user),
        ],
        CHARGE_CONFIRM_USER: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(
                filters.Regex(f"^({re.escape(CONFIRM_USER)}|{re.escape(CHANGE_USER)})$"),
                charge_wallet_confirm_user,
            ),
            MessageHandler(filters.TEXT & ~filters.COMMAND, charge_wallet_confirm_user),
        ],
        CHARGE_AMOUNT: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, charge_wallet_execute),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

set_wallet_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_SET_WALLET), set_wallet_start)],
    states={
        SET_WALLET_USER_ID: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_wallet_user),
        ],
        SET_WALLET_CONFIRM_USER: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(
                filters.Regex(f"^({re.escape(CONFIRM_USER)}|{re.escape(CHANGE_USER)})$"),
                set_wallet_confirm_user,
            ),
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_wallet_confirm_user),
        ],
        SET_WALLET_AMOUNT: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, set_wallet_execute),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

create_coupon_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_CREATE_COUPON), create_coupon_start)],
    states={
        COUPON_CODE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, create_coupon_code),
        ],
        COUPON_TYPE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.Regex(f"^({re.escape(COUPON_PERCENT)}|{re.escape(COUPON_FIXED)})$"), create_coupon_type),
        ],
        COUPON_AMOUNT: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, create_coupon_amount),
        ],
        COUPON_TARGET: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(
                filters.Regex(f"^({re.escape(COUPON_ALL_USERS)}|{re.escape(COUPON_SELECTED_USERS)})$"),
                create_coupon_target,
            ),
        ],
        COUPON_TARGET_USERS: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, create_coupon_target_users),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

edit_coupon_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_EDIT_COUPON), edit_coupon_start)],
    states={
        COUPON_EDIT_CODE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, edit_coupon_code),
        ],
        COUPON_EDIT_TYPE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.Regex(f"^({re.escape(COUPON_PERCENT)}|{re.escape(COUPON_FIXED)})$"), edit_coupon_type),
        ],
        COUPON_EDIT_AMOUNT: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, edit_coupon_amount),
        ],
        COUPON_EDIT_TARGET: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(
                filters.Regex(f"^({re.escape(COUPON_ALL_USERS)}|{re.escape(COUPON_SELECTED_USERS)})$"),
                edit_coupon_target,
            ),
        ],
        COUPON_EDIT_TARGET_USERS: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, edit_coupon_target_users),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

deactivate_coupon_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_DEACTIVATE_COUPON), deactivate_coupon_start)],
    states={
        COUPON_DEACTIVATE_CODE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, deactivate_coupon_code),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

delete_coupon_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_DELETE_COUPON), delete_coupon_start)],
    states={
        COUPON_DELETE_CODE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, delete_coupon_code),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

admin_add_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_ADD_ADMIN), admin_add_start)],
    states={
        ADMIN_ADD_ID: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), admin_management_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_id),
        ],
        ADMIN_ADD_PERMS: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), admin_management_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_permissions),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

admin_remove_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_REMOVE_ADMIN), admin_remove_start)],
    states={
        ADMIN_REMOVE_ID: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), admin_management_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_remove_execute),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

admin_perms_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_CHANGE_ADMIN_PERMS), admin_perms_start)],
    states={
        ADMIN_PERMS_ID: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), admin_management_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_perms_id),
        ],
        ADMIN_PERMS_VALUE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), admin_management_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, admin_perms_save),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

required_channels_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_REQUIRED_CHANNELS), required_channels_start)],
    states={
        REQUIRED_CHANNEL_ACTION: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_settings_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, required_channel_action),
        ],
        REQUIRED_CHANNEL_ADD: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_settings_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, required_channel_add),
        ],
        REQUIRED_CHANNEL_DELETE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), required_channels_start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, required_channel_delete),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
    allow_reentry=True,
)

shop_categories_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_SHOP_CATEGORIES), shop_categories_start)],
    states={
        SHOP_CATEGORY_SELECT: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_settings_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_category_select),
        ],
        SHOP_CATEGORY_ADD: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_categories_start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_category_add),
        ],
        SHOP_CATEGORY_OPTION: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_category_option_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_category_option),
        ],
        SHOP_CATEGORY_VALUE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_category_value_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_category_value),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

shop_messages_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_SHOP_MESSAGES), shop_messages_start)],
    states={
        SHOP_MESSAGE_SELECT: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_settings_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_message_select),
        ],
        SHOP_MESSAGE_TEXT: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_message_text_back),
            MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, shop_message_save),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
    allow_reentry=True,
)

shop_buttons_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_SHOP_BUTTONS), shop_buttons_start)],
    states={
        SHOP_BUTTON_MENU: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_settings_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_button_menu_select),
        ],
        SHOP_BUTTON_SELECT: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_button_list_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_button_select),
        ],
        SHOP_BUTTON_OPTION: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_button_options_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_button_option),
        ],
        SHOP_BUTTON_VALUE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_button_value_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_button_value),
        ],
        SHOP_BUTTON_ADD_TEXT: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_button_options_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_button_add_text),
        ],
        SHOP_BUTTON_ADD_MESSAGE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_button_add_message_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_button_add_message),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

shop_plans_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_SHOP_PLANS), shop_plans_start)],
    states={
        SHOP_PLAN_SELECT: [
            CallbackQueryHandler(
                shop_plan_management_callback,
                pattern=rf"^{SHOP_PLAN_CALLBACK_PREFIX}:",
            ),
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_settings_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_plan_select),
        ],
        SHOP_PLAN_OPTION: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_plan_options_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_plan_option),
        ],
        SHOP_PLAN_VALUE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_plan_value_back),
            MessageHandler((filters.TEXT | filters.Sticker.ALL | filters.PHOTO) & ~filters.COMMAND, shop_plan_value),
        ],
        SHOP_PLAN_ADD_VOLUME: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_plan_options_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_plan_add_volume),
        ],
        SHOP_PLAN_ADD_TITLE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_plan_add_title_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_plan_add_title),
        ],
        SHOP_PLAN_ADD_CATEGORY: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_plan_add_category_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_plan_add_category),
        ],
        SHOP_PLAN_ADD_PRICE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_plan_add_price_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_plan_add_price),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

provision_panels_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_PROVISION_PANELS), provision_panels_start)],
    states={
        PROVISION_PANEL_SELECT: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_settings_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, provision_panel_select),
        ],
        PROVISION_PANEL_OPTION: [
            CallbackQueryHandler(
                provision_inbound_callback,
                pattern=rf"^{PROVISION_INBOUND_CALLBACK_PREFIX}:",
            ),
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_settings_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, provision_panel_option),
        ],
        PROVISION_PANEL_VALUE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), provision_panels_start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, provision_panel_value),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

crypto_search_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_CRYPTO_SEARCH), crypto_search_start)],
    states={
        CRYPTO_SEARCH_ID: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, crypto_search_result),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

crypto_set_margin_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_CRYPTO_SET_MARGIN), crypto_set_margin_start)],
    states={
        CRYPTO_SET_MARGIN_VALUE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, crypto_set_margin_save),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

crypto_set_usdt_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_CRYPTO_SET_USDT), crypto_set_usdt_start)],
    states={
        CRYPTO_SET_USDT_VALUE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, crypto_set_usdt_save),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

crypto_set_ton_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_CRYPTO_SET_TON), crypto_set_ton_start)],
    states={
        CRYPTO_SET_TON_VALUE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, crypto_set_ton_save),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

rial_set_min_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_RIAL_SET_MIN), rial_set_min_start)],
    states={
        RIAL_SET_MIN_VALUE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, rial_set_min_save),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

rial_set_support_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_RIAL_SET_SUPPORT), rial_set_support_start)],
    states={
        RIAL_SET_SUPPORT_VALUE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, rial_set_support_save),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

trial_set_volume_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_TRIAL_SET_VOLUME), trial_set_volume_start)],
    states={
        TRIAL_SET_VOLUME_VALUE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_settings_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, trial_set_volume_save),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

trial_set_duration_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_TRIAL_SET_DURATION), trial_set_duration_start)],
    states={
        TRIAL_SET_DURATION_VALUE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_settings_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, trial_set_duration_save),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

service_reminder_volume_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_SERVICE_REMINDER_SET_VOLUME), service_reminder_volume_start)],
    states={
        SERVICE_REMINDER_VOLUME_VALUE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_settings_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, service_reminder_volume_save),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

service_reminder_days_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_SERVICE_REMINDER_SET_DAYS), service_reminder_days_start)],
    states={
        SERVICE_REMINDER_DAYS_VALUE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_settings_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, service_reminder_days_save),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

service_reminder_hours_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_SERVICE_REMINDER_SET_HOURS), service_reminder_hours_start)],
    states={
        SERVICE_REMINDER_HOURS_VALUE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_settings_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, service_reminder_hours_save),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

shop_reset_defaults_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_SHOP_RESET_DEFAULTS), shop_reset_defaults)],
    states={
        SHOP_RESET_CONFIRM: [
            MessageHandler(_exact_filter(ADMIN_RESET_CONFIRM), shop_reset_confirm),
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_settings_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_reset_confirm),
        ],
        SHOP_RESET_PASSWORD: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), shop_settings_back),
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_reset_password),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
)

referral_rewards_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_REFERRAL_REWARDS), referral_rewards_start)],
    states={
        REFERRAL_RULE_SELECT: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, referral_rule_select),
        ],
        REFERRAL_RULE_TITLE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), referral_rewards_start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, referral_rule_title),
        ],
        REFERRAL_RULE_QUALIFICATION: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), referral_rewards_start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, referral_rule_qualification),
        ],
        REFERRAL_RULE_COUNT: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), referral_rewards_start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, referral_rule_count),
        ],
        REFERRAL_RULE_REPEAT: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), referral_rewards_start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, referral_rule_repeat),
        ],
        REFERRAL_RULE_REWARD_TYPE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), referral_rewards_start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, referral_rule_reward_type),
        ],
        REFERRAL_RULE_REWARD_VALUE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), referral_rewards_start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, referral_rule_reward_value),
        ],
        REFERRAL_RULE_OPTION: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), referral_rewards_start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, referral_rule_option),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
    allow_reentry=True,
)

broadcast_conv = ConversationHandler(
    entry_points=[
        MessageHandler(_exact_filter(ADMIN_BROADCAST), broadcast_start),
        CommandHandler("broadcast", broadcast_start),
    ],
    states={
        BROADCAST_MESSAGE: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_preview),
        ],
        BROADCAST_CONFIRM: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_confirm),
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel), MessageHandler(_exact_filter(CANCEL), cancel)],
    allow_reentry=True,
)

admin_handlers = [
    CommandHandler("start", admin_start),
    CommandHandler("admins", list_admins),
    CommandHandler("addadmin", add_admin),
    CommandHandler("removeadmin", remove_admin),
    CommandHandler("setadminperms", set_admin_permissions),
    add_config_conv,
    edit_price_conv,
    search_user_conv,
    charge_wallet_conv,
    set_wallet_conv,
    create_coupon_conv,
    edit_coupon_conv,
    deactivate_coupon_conv,
    delete_coupon_conv,
    admin_add_conv,
    admin_remove_conv,
    admin_perms_conv,
    required_channels_conv,
    shop_categories_conv,
    shop_messages_conv,
    shop_buttons_conv,
    shop_plans_conv,
    provision_panels_conv,
    crypto_search_conv,
    crypto_set_margin_conv,
    crypto_set_usdt_conv,
    crypto_set_ton_conv,
    rial_set_min_conv,
    rial_set_support_conv,
    trial_set_volume_conv,
    trial_set_duration_conv,
    service_reminder_volume_conv,
    service_reminder_days_conv,
    service_reminder_hours_conv,
    shop_reset_defaults_conv,
    referral_rewards_conv,
    broadcast_conv,
    MessageHandler(_exact_filter(ADMIN_CRYPTO), crypto_menu),
    MessageHandler(_exact_filter(ADMIN_CRYPTO_HISTORY), crypto_history),
    MessageHandler(_exact_filter(ADMIN_CRYPTO_RATES), crypto_rates_menu),
    MessageHandler(_exact_filter(ADMIN_CRYPTO_TOGGLE_MODE), crypto_toggle_mode),
    MessageHandler(_exact_filter(ADMIN_RIAL_HISTORY), rial_history),
    MessageHandler(_exact_filter(ADMIN_RIAL_SETTINGS), rial_settings_menu),
    MessageHandler(_exact_filter(ADMIN_RIAL_TOGGLE_PHONE), rial_toggle_phone),
    MessageHandler(_exact_filter(ADMIN_LOGOUT), admin_logout),
    MessageHandler(_exact_filter(ADMIN_ADMINS), admin_management_menu),
    MessageHandler(_exact_filter(ADMIN_REFRESH_ADMINS), list_admins),
    MessageHandler(_exact_filter(ADMIN_SHOP_SETTINGS), shop_settings_menu),
    MessageHandler(_exact_filter(ADMIN_PROVISION_PANELS), provision_panels_start),
    MessageHandler(_exact_filter(ADMIN_TRIAL_SETTINGS), trial_settings_menu),
    MessageHandler(_exact_filter(ADMIN_TRIAL_TOGGLE), trial_toggle),
    MessageHandler(_exact_filter(ADMIN_SERVICE_REMINDERS), service_reminders_menu),
    MessageHandler(_exact_filter(ADMIN_SERVICE_REMINDER_TOGGLE), service_reminders_toggle),
    MessageHandler(_exact_filter(ADMIN_TOGGLE_BRANDED_LINKS), toggle_branded_subscription_links),
    MessageHandler(
        filters.Regex(
            f"^({re.escape(ADMIN_BACK)}|{re.escape(ADMIN_INVENTORY)}|{re.escape(ADMIN_PRICES)}|"
            f"{re.escape(ADMIN_USERS)}|{re.escape(ADMIN_REPORTS)}|{re.escape(ADMIN_COUPONS)}|"
            f"{re.escape(ADMIN_SHOP_SETTINGS)})$"
        ),
        admin_menu_navigation,
    ),
    MessageHandler(_exact_filter(ADMIN_STOCK_STATUS), stock_status),
    MessageHandler(_exact_filter(ADMIN_VIEW_PRICES), view_prices),
    MessageHandler(_exact_filter(ADMIN_VIEW_COUPONS), list_coupons),
    MessageHandler(
        filters.Regex(
            f"^({re.escape(REPORT_TODAY)}|{re.escape(REPORT_WEEK)}|{re.escape(REPORT_MONTH)}|"
            f"{re.escape(REPORT_45_DAYS)}|{re.escape(REPORT_90_DAYS)})$"
        ),
        sales_report,
    ),
    MessageHandler(_exact_filter(ADMIN_USER_STATS), user_stats),
    MessageHandler(_exact_filter(ADMIN_REFERRAL_REPORT), referral_report),
    MessageHandler(filters.TEXT & ~filters.COMMAND, check_admin_password),
]
