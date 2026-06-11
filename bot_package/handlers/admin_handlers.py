import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, constants
from telegram.ext import CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from ..auth import AuthManager
from ..config_loader import BotConfig
from ..database import async_session
from ..models import Purchase
from ..services.admin_service import ALL_PERMISSIONS, AdminService, normalize_permissions
from ..services.coupon_service import CouponError, CouponService
from ..services.crypto_payment_service import CryptoPaymentService, available_coins
from ..services.rate_service import RateService
from ..services.rial_payment_service import RialPaymentService
from ..services.settings_service import SettingsService
from ..services.inventory_service import InventoryService
from ..services.price_service import PriceService
from ..services.referral_service import ReferralService
from ..services.required_channel_service import RequiredChannelService
from ..services.shop_customization_service import ShopCustomizationService
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
    ADMIN_SHOP_RESET_DEFAULTS,
    ADMIN_SHOP_SETTINGS,
    ADMIN_STOCK_STATUS,
    ADMIN_TOGGLE_ENABLED,
    ADMIN_TOGGLE_BRANDED_LINKS,
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
    REPORT_MONTH,
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
    admin_shop_settings_keyboard,
    admin_emoji_position_keyboard,
    admin_response_button_keyboard,
    admin_reset_confirm_keyboard,
    admin_required_channel_keyboard,
    admin_style_keyboard,
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
) = range(58)


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
    ADMIN_SHOP_RESET_DEFAULTS,
    ADMIN_REQUIRED_CHANNELS,
    ADMIN_TOGGLE_BRANDED_LINKS,
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


def _plan_label(plan) -> str:
    status = "فعال" if plan.is_active else "غیرفعال"
    emoji = f"{plan.emoji} " if plan.emoji else ""
    return f"#{plan.id} [{plan.category_key}] {emoji}{plan.title} - {plan.volume_gb} گیگ ({status})"


def _category_label(category) -> str:
    status = "✅" if category.is_active else "⏸"
    emoji = f"{category.emoji} " if category.emoji else ""
    return f"#{category.id} {status} {emoji}{category.title}"


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
        elif text == ADMIN_REQUIRED_CHANNELS:
            await required_channels_start(update, context)
        elif text == ADMIN_TOGGLE_BRANDED_LINKS:
            await toggle_branded_subscription_links(update, context)
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
        labels = [f"#{plan.id} ✏️ [{plan.category_key}] {plan.title} - {plan.volume_gb} گیگ" for plan in active_plans]
    else:
        labels = [f"#{plan.id} 📦 [{plan.category_key}] {plan.title} - {plan.volume_gb} گیگ" for plan in active_plans]
    if not labels:
        labels = [f"📦 {volume} گیگ" for volume in (1, 2, 3, 5, 10, 20)]
    return _rows(labels, width=2)


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
    custom_emoji_type = getattr(constants.MessageEntityType, "CUSTOM_EMOJI", "custom_emoji")
    for entity in message.entities or []:
        entity_type = getattr(entity, "type", "")
        if entity_type == custom_emoji_type or str(entity_type) == "custom_emoji":
            custom_emoji_id = getattr(entity, "custom_emoji_id", None)
            if custom_emoji_id:
                return str(custom_emoji_id)
    return None


def _read_custom_emoji_id(message, raw_text: str) -> str | None:
    return _extract_custom_emoji_id(message) or _normalize_custom_emoji_id(raw_text)


def _message_text_for_storage(message) -> tuple[str, str]:
    if _extract_custom_emoji_id(message):
        text_html = getattr(message, "text_html", None)
        if isinstance(text_html, str) and text_html:
            return text_html, constants.ParseMode.HTML
    return message.text, constants.ParseMode.MARKDOWN


def _admin_user_preview(user) -> str:
    username = f"@{user.username}" if user.username else "ندارد"
    status = "مسدود" if user.is_blocked else "فعال"
    return (
        "**تایید کاربر**\n\n"
        f"آیدی عددی: `{user.telegram_id}`\n"
        f"نام: {user.first_name}\n"
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
        keyboard = await _admin_volume_keyboard(session, "add")
    await update.message.reply_text(
        ADD_CONFIG_VOLUME,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return CHOOSE_VOLUME_ADD


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
    if not volume or not links:
        await update.message.reply_text("لینکی برای ثبت وجود ندارد.", reply_markup=admin_inventory_keyboard())
        return ConversationHandler.END

    async with async_session() as session:
        count = await InventoryService.add_configs(session, volume, links, category_key)

    await update.message.reply_text(
        f"{count} لینک برای پلن {volume} گیگ در دسته `{category_key}` ثبت شد.",
        reply_markup=admin_inventory_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


@require_auth(permission="inventory")
async def stock_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        stock = await InventoryService.get_stock_status(session)

    message = STOCK_STATUS_HEADER
    for category_key, volume, title, count in stock:
        if count < 5:
            status = "بحرانی"
        elif count <= 10:
            status = "متوسط"
        else:
            status = "مناسب"
        message += f"[{category_key}] {title} - {volume} گیگ: {count} عدد ({status})\n"

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
            message += f"#{plan.id} [{plan.category_key}] {plan.title} - {plan.volume_gb} گیگ: {(price or 0):,} تومان\n"

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
        await update.message.reply_text(
            CHARGE_SUCCESS.format(user_id, f"{amount:,}", datetime.now().strftime("%H:%M:%S")),
            reply_markup=admin_users_keyboard(),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text("کاربر پیدا نشد.", reply_markup=admin_users_keyboard())

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
    }
    days, period_name = period_map[update.message.text]
    since = datetime.now(timezone.utc) - timedelta(days=days)

    async with async_session() as session:
        result = await session.execute(select(Purchase).where(Purchase.purchased_at >= since))
        purchases = result.scalars().all()

    total_revenue = sum(purchase.price for purchase in purchases)
    volume_stats = {}
    for purchase in purchases:
        volume_stats[purchase.volume_gb] = volume_stats.get(purchase.volume_gb, 0) + 1

    message = f"**گزارش فروش {period_name}**\n\n"
    message += f"تعداد فروش: {len(purchases)}\n"
    message += f"درآمد کل: **{total_revenue:,} تومان**\n\n"
    if volume_stats:
        message += "تفکیک بر اساس حجم:\n"
        for volume, count in sorted(volume_stats.items()):
            message += f"{volume} گیگ: {count} فروش\n"

    await update.message.reply_text(
        message,
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
        f"ویرایش پیام {key}\n\nمتن فعلی:\n\n{message.text}{placeholder_note}{extra_note}\n\nمتن جدید را ارسال کنید.",
        reply_markup=admin_response_button_keyboard(),
    )
    return SHOP_MESSAGE_TEXT


@require_auth(permission="shop")
async def shop_message_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        context.user_data.pop("shop_message_key", None)
        return ConversationHandler.END
    key = context.user_data.get("shop_message_key")
    raw_value = update.message.text.strip()
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

    message_text, parse_mode = _message_text_for_storage(update.message)
    async with async_session() as session:
        message = await ShopCustomizationService.update_message(
            session,
            key,
            message_text,
            parse_mode=parse_mode,
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
    raw_value = update.message.text.strip()
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
    labels = [_plan_label(plan) for plan in plans]
    labels.append(ADMIN_ADD_PLAN)
    await update.message.reply_text(
        "**مدیریت سرویس‌ها**\n\nپلن موردنظر را انتخاب کنید یا سرویس جدید بسازید.",
        reply_markup=_rows(labels, width=1),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return SHOP_PLAN_SELECT


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
            "حجم سرویس جدید را به گیگ ارسال کنید. مثال: `30`",
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

    if not plan:
        await update.message.reply_text("پلن پیدا نشد.", reply_markup=admin_shop_settings_keyboard())
        return ConversationHandler.END

    await update.message.reply_text(
        "**ویرایش سرویس**\n\n"
        f"شناسه: `#{plan.id}`\n"
        f"حجم: **{plan.volume_gb} گیگ**\n"
        f"عنوان: {plan.title}\n"
        f"دسته‌بندی: `{plan.category_key}`\n"
        f"قیمت: **{price or 0:,} تومان**\n"
        f"ایموجی: {plan.emoji or '-'}\n"
        f"جای ایموجی: {'راست' if plan.emoji_position == 'right' else 'چپ'}\n"
        f"ایموجی پریمیوم: `{plan.premium_emoji_id or '-'}`\n"
        f"جای ایموجی پریمیوم: {'راست' if plan.premium_emoji_position == 'right' else 'چپ'}\n"
        f"رنگ: `{plan.style or 'default'}`\n"
        f"ترتیب: {plan.display_order}\n"
        f"وضعیت: {'فعال' if plan.is_active else 'غیرفعال'}",
        reply_markup=admin_shop_plan_edit_keyboard(),
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

    if field == "display_order":
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

    await update.message.reply_text("سرویس ذخیره شد.")
    return await _show_shop_plan_options(update, context)


@require_auth(permission="shop")
async def shop_plan_add_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _leave_shop_flow_if_navigation(update, context):
        context.user_data.pop("shop_new_plan", None)
        return ConversationHandler.END
    try:
        volume = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("حجم باید عددی باشد.")
        return SHOP_PLAN_ADD_VOLUME
    if volume <= 0:
        await update.message.reply_text("حجم باید بیشتر از صفر باشد.")
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
        plan = await ShopCustomizationService.upsert_plan(
            session,
            volume_gb=draft["volume"],
            title=draft["title"],
            price=price,
            category_key=draft.get("category_key", "default"),
        )

    context.user_data.pop("shop_new_plan", None)
    await update.message.reply_text(
        f"سرویس **{plan.title}** با حجم **{plan.volume_gb} گیگ** ساخته شد.",
        reply_markup=admin_shop_settings_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


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
        f"دریافت شماره تماس: **{'روشن' if require_phone else 'خاموش'}**\n"
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
        f"دریافت شماره تماس برای پرداخت ریالی **{'روشن' if enabled else 'خاموش'}** شد.",
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
        "حجم سرویس جدید را به گیگ ارسال کنید. مثال: `30`",
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
        CHOOSE_VOLUME_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_config_volume)],
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
    entry_points=[MessageHandler(_exact_filter(ADMIN_CHARGE_WALLET), charge_wallet_start)],
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
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_message_save),
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
            MessageHandler(filters.TEXT & ~filters.COMMAND, shop_plan_value),
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
    crypto_search_conv,
    crypto_set_margin_conv,
    crypto_set_usdt_conv,
    crypto_set_ton_conv,
    rial_set_min_conv,
    rial_set_support_conv,
    shop_reset_defaults_conv,
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
        filters.Regex(f"^({re.escape(REPORT_TODAY)}|{re.escape(REPORT_WEEK)}|{re.escape(REPORT_MONTH)})$"),
        sales_report,
    ),
    MessageHandler(_exact_filter(ADMIN_USER_STATS), user_stats),
    MessageHandler(_exact_filter(ADMIN_REFERRAL_REPORT), referral_report),
    MessageHandler(filters.TEXT & ~filters.COMMAND, check_admin_password),
]
