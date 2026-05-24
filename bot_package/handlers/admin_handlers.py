import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from telegram import ReplyKeyboardRemove, Update, constants
from telegram.ext import CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from ..auth import AuthManager
from ..config_loader import BotConfig
from ..database import async_session
from ..models import Purchase
from ..services.admin_service import ALL_PERMISSIONS, AdminService, normalize_permissions
from ..services.inventory_service import InventoryService
from ..services.price_service import PriceService
from ..services.user_service import UserService
from ..utils.keyboards import (
    ADMIN_ADMINS,
    ADMIN_ADD_CONFIG,
    ADMIN_BACK,
    ADMIN_CHARGE_WALLET,
    ADMIN_EDIT_PRICE,
    ADMIN_INVENTORY,
    ADMIN_LOGOUT,
    ADMIN_PRICES,
    ADMIN_REFRESH_ADMINS,
    ADMIN_REPORTS,
    ADMIN_SEARCH_USER,
    ADMIN_STOCK_STATUS,
    ADMIN_USERS,
    ADMIN_USER_STATS,
    ADMIN_VIEW_PRICES,
    CANCEL,
    DONE_ADDING_CONFIGS,
    REPORT_MONTH,
    REPORT_TODAY,
    REPORT_WEEK,
    add_links_collecting_keyboard,
    admin_inventory_keyboard,
    admin_main_keyboard,
    admin_management_keyboard,
    admin_prices_keyboard,
    admin_reports_keyboard,
    admin_users_keyboard,
    volume_selection_keyboard,
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


(CHOOSE_VOLUME_ADD, COLLECT_LINKS, CHOOSE_VOLUME_PRICE, ENTER_NEW_PRICE, SEARCH_USER, CHARGE_USER_ID, CHARGE_AMOUNT) = range(7)


def _exact_filter(text: str):
    return filters.Regex(f"^{re.escape(text)}$")


def _extract_volume(text: str) -> int | None:
    match = re.search(r"(\d+)\s*گیگ", text)
    return int(match.group(1)) if match else None


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
    await update.message.reply_text(
        ADD_CONFIG_VOLUME,
        reply_markup=volume_selection_keyboard("add"),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return CHOOSE_VOLUME_ADD


@require_auth(permission="inventory")
async def add_config_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    volume = _extract_volume(update.message.text)
    if volume is None:
        await update.message.reply_text("حجم انتخاب‌شده معتبر نیست.", reply_markup=admin_inventory_keyboard())
        return ConversationHandler.END

    context.user_data["adding_volume"] = volume
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
    links = context.user_data.get("collected_links", [])
    if not volume or not links:
        await update.message.reply_text("لینکی برای ثبت وجود ندارد.", reply_markup=admin_inventory_keyboard())
        return ConversationHandler.END

    async with async_session() as session:
        count = await InventoryService.add_configs(session, volume, links)

    await update.message.reply_text(
        f"{count} لینک برای پلن {volume} گیگ ثبت شد.",
        reply_markup=admin_inventory_keyboard(),
    )
    return ConversationHandler.END


@require_auth(permission="inventory")
async def stock_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        stock = await InventoryService.get_stock_status(session)

    message = STOCK_STATUS_HEADER
    for volume, count in stock.items():
        if count < 5:
            status = "بحرانی"
        elif count <= 10:
            status = "متوسط"
        else:
            status = "مناسب"
        message += f"{volume} گیگ: {count} عدد ({status})\n"

    await update.message.reply_text(
        message,
        reply_markup=admin_inventory_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


@require_auth(permission="prices")
async def view_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        prices = await PriceService.get_all_prices(session)

    message = PRICE_LIST_HEADER.format(datetime.now().strftime("%Y-%m-%d %H:%M"))
    for volume, price in prices.items():
        message += f"{volume} گیگ: {price:,} تومان\n"

    await update.message.reply_text(
        message,
        reply_markup=admin_prices_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


@require_auth(permission="prices")
async def edit_price_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "حجم پلنی که می‌خواهید قیمتش را تغییر دهید انتخاب کنید:",
        reply_markup=volume_selection_keyboard("edit_price"),
    )
    return CHOOSE_VOLUME_PRICE


@require_auth(permission="prices")
async def edit_price_enter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    volume = _extract_volume(update.message.text)
    if volume is None:
        await update.message.reply_text("حجم انتخاب‌شده معتبر نیست.", reply_markup=admin_prices_keyboard())
        return ConversationHandler.END

    context.user_data["editing_volume"] = volume
    async with async_session() as session:
        current_price = await PriceService.get_price(session, volume)

    await update.message.reply_text(
        EDIT_PRICE_PROMPT.format(volume, f"{current_price:,}"),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ENTER_NEW_PRICE


@require_auth(permission="prices")
async def save_new_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    volume = context.user_data.get("editing_volume")
    try:
        new_price = int(update.message.text.replace(",", "").strip())
    except ValueError:
        await update.message.reply_text("لطفا قیمت را فقط به صورت عددی ارسال کنید.")
        return ENTER_NEW_PRICE

    if new_price <= 0:
        await update.message.reply_text("قیمت باید بیشتر از صفر باشد.")
        return ENTER_NEW_PRICE

    async with async_session() as session:
        success = await PriceService.update_price(session, volume, new_price)

    if success:
        await update.message.reply_text(
            PRICE_UPDATED.format(volume, f"{new_price:,}", datetime.now().strftime("%H:%M:%S")),
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

    if user:
        status = "مسدود" if user.is_blocked else "فعال"
        message = (
            "**اطلاعات کاربر**\n\n"
            f"آیدی عددی: `{user.telegram_id}`\n"
            f"نام: {user.first_name}\n"
            f"یوزرنیم: @{user.username or 'ندارد'}\n"
            f"موجودی کیف پول: **{user.wallet_balance:,} تومان**\n"
            f"تاریخ عضویت: {user.created_at.strftime('%Y-%m-%d')}\n"
            f"وضعیت: {status}"
        )
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
    try:
        context.user_data["charge_user_id"] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("آیدی عددی تلگرام باید فقط عدد باشد.")
        return CHARGE_USER_ID

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
    )

    await update.message.reply_text(
        message,
        reply_markup=admin_users_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


@require_auth(owner_only=True)
async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        admins = await AdminService.list_admins(session)

    lines = ["**ادمین‌های فعال**\n"]
    for admin in admins:
        role = "مالک" if admin.is_owner else "ادمین"
        permissions = "all" if admin.is_owner else admin.permissions
        lines.append(f"`{admin.telegram_id}` | {role} | `{permissions}`")

    await update.effective_message.reply_text("\n".join(lines), parse_mode=constants.ParseMode.MARKDOWN)


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


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد.", reply_markup=admin_main_keyboard())
    return ConversationHandler.END


add_config_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(ADMIN_ADD_CONFIG), add_config_start)],
    states={
        CHOOSE_VOLUME_ADD: [MessageHandler(filters.Regex(r"^📦 \d+ گیگ$"), add_config_volume)],
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
        CHOOSE_VOLUME_PRICE: [MessageHandler(filters.Regex(r"^✏️ قیمت \d+ گیگ$"), edit_price_enter)],
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
        CHARGE_AMOUNT: [
            MessageHandler(_exact_filter(CANCEL), cancel),
            MessageHandler(_exact_filter(ADMIN_BACK), cancel),
            MessageHandler(filters.TEXT & ~filters.COMMAND, charge_wallet_execute),
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
    MessageHandler(_exact_filter(ADMIN_LOGOUT), admin_logout),
    MessageHandler(_exact_filter(ADMIN_ADMINS), admin_management_menu),
    MessageHandler(_exact_filter(ADMIN_REFRESH_ADMINS), admin_management_menu),
    MessageHandler(
        filters.Regex(
            f"^({re.escape(ADMIN_BACK)}|{re.escape(ADMIN_INVENTORY)}|{re.escape(ADMIN_PRICES)}|"
            f"{re.escape(ADMIN_USERS)}|{re.escape(ADMIN_REPORTS)})$"
        ),
        admin_menu_navigation,
    ),
    MessageHandler(_exact_filter(ADMIN_STOCK_STATUS), stock_status),
    MessageHandler(_exact_filter(ADMIN_VIEW_PRICES), view_prices),
    MessageHandler(
        filters.Regex(f"^({re.escape(REPORT_TODAY)}|{re.escape(REPORT_WEEK)}|{re.escape(REPORT_MONTH)})$"),
        sales_report,
    ),
    MessageHandler(_exact_filter(ADMIN_USER_STATS), user_stats),
    MessageHandler(filters.TEXT & ~filters.COMMAND, check_admin_password),
]
