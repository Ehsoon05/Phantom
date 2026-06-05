import re
from datetime import datetime, timezone
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from telegram import ReplyKeyboardMarkup, Update, constants
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters
try:
    from telegram.helpers import escape_markdown
except ImportError:
    def escape_markdown(text: str, version: int = 1) -> str:
        del version
        return text.replace("\\", "\\\\").replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

from ..database import async_session
from ..models import Purchase, Transaction, User
from ..services.coupon_service import CouponError, CouponService
from ..services.inventory_service import InventoryService
from ..services.price_service import PriceService
from ..services.referral_service import ReferralService
from ..services.required_channel_service import RequiredChannelService
from ..services.shop_customization_service import ShopCustomizationService
from ..services.subscription_link_service import SubscriptionLinkService
from ..services.user_service import UserService
from ..utils.keyboards import (
    referral_share_keyboard,
)
from ..utils.messages import (
    SUPPORT_HANDLE,
)


ACCEPT_RULES = "✅ تایید قوانین"


async def get_or_create_user(telegram_id: int, name: str, username: str | None, payload: str | None = None):
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            user = User(telegram_id=telegram_id, first_name=name, username=username)
            session.add(user)
            await session.flush()

        user.first_name = name or user.first_name
        user.username = username
        await ReferralService.ensure_referral_code(session, user)
        await ReferralService.apply_start_payload(session, user, payload)
        await session.commit()
        return user


def _exact_filter(text: str):
    return filters.Regex(f"^{re.escape(text)}$")


def _extract_volume(text: str) -> int | None:
    match = re.search(r"(\d+)\s*گیگ", text)
    return int(match.group(1)) if match else None


async def _message_markup(session, key: str, fallback_markup=None, *, default_url: str | None = None, copy_text: str | None = None):
    return await ShopCustomizationService.message_reply_markup(
        session,
        key,
        fallback_markup=fallback_markup,
        default_url=default_url,
        copy_text=copy_text,
    )


async def ensure_required_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    async with async_session() as session:
        channels = await RequiredChannelService.list_channels(session, active_only=True)
    if not channels:
        return True

    missing = await RequiredChannelService.missing_channels(context.bot, update.effective_user.id, channels)
    if not missing:
        return True

    await update.effective_message.reply_text(
        "برای استفاده از ربات، ابتدا در کانال‌های زیر عضو شوید و سپس دوباره /start را بزنید.",
        reply_markup=RequiredChannelService.join_keyboard(missing),
    )
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    payload = context.args[0] if context.args else None
    context.user_data.pop("awaiting_coupon_code", None)
    context.user_data.pop("awaiting_service_name", None)
    context.user_data.pop("pending_purchase_volume", None)
    context.user_data.pop("pending_purchase_plan_id", None)
    context.user_data.pop("selected_plan_category", None)
    if not await ensure_required_membership(update, context):
        return
    db_user = await get_or_create_user(user.id, user.first_name, user.username, payload)
    if db_user.accepted_rules_at is None:
        await rules_menu(update, context)
        return
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "main_menu")
        fallback_keyboard = await ShopCustomizationService.main_menu_keyboard(session)
        keyboard = await _message_markup(session, "main_menu", fallback_keyboard, copy_text=text)
    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting_coupon_code", None)
    context.user_data.pop("awaiting_service_name", None)
    context.user_data.pop("pending_purchase_volume", None)
    context.user_data.pop("pending_purchase_plan_id", None)
    context.user_data.pop("selected_plan_category", None)
    user = await get_or_create_user(
        update.effective_user.id,
        update.effective_user.first_name,
        update.effective_user.username,
    )
    if user.accepted_rules_at is None:
        await rules_menu(update, context)
        return
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "main_menu")
        fallback_keyboard = await ShopCustomizationService.main_menu_keyboard(session)
        keyboard = await _message_markup(session, "main_menu", fallback_keyboard, copy_text=text)
    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def buy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("selected_plan_category", None)
    context.user_data.pop("awaiting_service_name", None)
    context.user_data.pop("pending_purchase_volume", None)
    context.user_data.pop("pending_purchase_plan_id", None)
    user = await get_or_create_user(
        update.effective_user.id,
        update.effective_user.first_name,
        update.effective_user.username,
    )
    if user.accepted_rules_at is None:
        await rules_menu(update, context)
        return
    async with async_session() as session:
        prices = await PriceService.get_all_prices(session)
        discounted_prices = await CouponService.prices_with_active_discount(session, update.effective_user.id, prices)
        text = await ShopCustomizationService.get_message(session, "buy_menu")
        fallback_keyboard = await ShopCustomizationService.buy_volume_keyboard(session, discounted_prices)
        keyboard = await _message_markup(session, "buy_menu", fallback_keyboard, copy_text=text)

    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def buy_category_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, category_key: str):
    context.user_data["selected_plan_category"] = category_key
    async with async_session() as session:
        prices = await PriceService.get_all_prices(session)
        discounted_prices = await CouponService.prices_with_active_discount(session, update.effective_user.id, prices)
        text = await ShopCustomizationService.get_message(session, "buy_menu")
        fallback_keyboard = await ShopCustomizationService.buy_category_keyboard(session, category_key, discounted_prices)
        keyboard = await _message_markup(session, "buy_menu", fallback_keyboard, copy_text=text)

    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def wallet_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_or_create_user(
        update.effective_user.id,
        update.effective_user.first_name,
        update.effective_user.username,
    )
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(
            session,
            "wallet",
            wallet_balance=f"{user.wallet_balance:,}",
            support_handle=SUPPORT_HANDLE,
        )
        fallback_keyboard = await ShopCustomizationService.wallet_keyboard(session)
        keyboard = await _message_markup(session, "wallet", fallback_keyboard, copy_text=text)
    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_or_create_user(
        update.effective_user.id,
        update.effective_user.first_name,
        update.effective_user.username,
    )
    bot_username = context.bot.username or "PhantomHubs_bot"
    link = f"https://t.me/{bot_username}?start=ref_{user.referral_code}"
    async with async_session() as session:
        count = await ReferralService.count_referrals(session, user.telegram_id)
        text = await ShopCustomizationService.get_message(session, "referral", link=link, count=count)
        followup = await ShopCustomizationService.get_message(session, "referral_followup")
        keyboard = await ShopCustomizationService.main_menu_keyboard(session)

    share_text = (
        "سلام، من از فانتوم VPN استفاده می‌کنم. "
        "از این لینک وارد شو و سرویس‌هات رو راحت‌تر تهیه کن:"
    )
    share_url = f"https://t.me/share/url?url={quote(link)}&text={quote(share_text)}"
    await update.message.reply_text(
        text,
        reply_markup=referral_share_keyboard(share_url),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    await update.message.reply_text(
        followup,
        reply_markup=keyboard,
    )


async def account_info_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_or_create_user(
        update.effective_user.id,
        update.effective_user.first_name,
        update.effective_user.username,
    )
    async with async_session() as session:
        purchase_summary = await UserService.get_user_purchase_summary(session, user.telegram_id, limit=0)
        referral_count = await ReferralService.count_referrals(session, user.telegram_id)
        text = await ShopCustomizationService.get_message(
            session,
            "account_info",
            telegram_id=user.telegram_id,
            first_name=escape_markdown(user.first_name or "-", version=1),
            username=escape_markdown(f"@{user.username}" if user.username else "ثبت نشده", version=1),
            wallet_balance=f"{user.wallet_balance:,}",
            total_count=purchase_summary["total_count"],
            total_gb=f"{purchase_summary['total_gb']:,}",
            total_spent=f"{purchase_summary['total_spent']:,}",
            referral_count=referral_count,
        )
        fallback_keyboard = await ShopCustomizationService.back_keyboard(session)
        keyboard = await _message_markup(session, "account_info", fallback_keyboard, copy_text=text)

    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def apply_coupon_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting_coupon_code"] = True
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "coupon_prompt")
        fallback_keyboard = await ShopCustomizationService.back_keyboard(session)
        keyboard = await _message_markup(session, "coupon_prompt", fallback_keyboard, copy_text=text)
    await update.message.reply_text(
        text,
        reply_markup=keyboard,
    )


async def apply_coupon_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await get_or_create_user(
        update.effective_user.id,
        update.effective_user.first_name,
        update.effective_user.username,
    )
    async with async_session() as session:
        try:
            coupon = await CouponService.apply_coupon(session, update.effective_user.id, update.message.text)
        except CouponError:
            text = await ShopCustomizationService.get_message(session, "coupon_invalid")
            fallback_keyboard = await ShopCustomizationService.wallet_keyboard(session)
            keyboard = await _message_markup(session, "coupon_invalid", fallback_keyboard, copy_text=text)
            await update.message.reply_text(
                text,
                reply_markup=keyboard,
            )
            context.user_data.pop("awaiting_coupon_code", None)
            return

        if coupon.discount_type == "percent":
            discount_text = f"{coupon.amount} درصد"
        else:
            discount_text = f"{coupon.amount:,} تومان"
        text = await ShopCustomizationService.get_message(
            session,
            "coupon_applied",
            code=coupon.code,
            discount_text=discount_text,
        )
        fallback_keyboard = await ShopCustomizationService.wallet_keyboard(session)
        keyboard = await _message_markup(session, "coupon_applied", fallback_keyboard, copy_text=text)

    context.user_data.pop("awaiting_coupon_code", None)
    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def process_purchase(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    selected_plan_id: int | None = None,
    service_name: str | None = None,
):
    if selected_plan_id is None:
        async with async_session() as session:
            text = await ShopCustomizationService.get_message(session, "invalid_plan")
            fallback_keyboard = await ShopCustomizationService.main_menu_keyboard(session)
            keyboard = await _message_markup(session, "invalid_plan", fallback_keyboard, copy_text=text)
        await update.message.reply_text(
            text,
            reply_markup=keyboard,
        )
        return

    await get_or_create_user(
        update.effective_user.id,
        update.effective_user.first_name,
        update.effective_user.username,
    )

    async with async_session() as session:
        plan = await ShopCustomizationService.get_plan(session, selected_plan_id)
        if not plan or not plan.is_active:
            text = await ShopCustomizationService.get_message(session, "inactive_plan")
            fallback_keyboard = await ShopCustomizationService.main_menu_keyboard(session)
            keyboard = await _message_markup(session, "inactive_plan", fallback_keyboard, copy_text=text)
            await update.message.reply_text(text, reply_markup=keyboard)
            return

        volume = plan.volume_gb
        category_key = plan.category_key or "default"
        # Lock the user row for the duration of the purchase transaction so that
        # two concurrent buy clicks cannot both observe the pre-deduction balance
        # and double-spend. SQLAlchemy emits FOR UPDATE on PostgreSQL and silently
        # omits it on SQLite (which serializes writes via BEGIN IMMEDIATE anyway).
        user_result = await session.execute(
            select(User)
            .where(User.telegram_id == update.effective_user.id)
            .with_for_update()
        )
        db_user = user_result.scalar_one()

        if db_user.is_blocked:
            text = await ShopCustomizationService.get_message(session, "blocked_user")
            fallback_keyboard = await ShopCustomizationService.main_menu_keyboard(session)
            keyboard = await _message_markup(session, "blocked_user", fallback_keyboard, copy_text=text)
            await update.message.reply_text(text, reply_markup=keyboard)
            return

        original_price = await PriceService.get_plan_price(session, plan)
        if not original_price:
            text = await ShopCustomizationService.get_message(session, "inactive_plan")
            fallback_keyboard = await ShopCustomizationService.main_menu_keyboard(session)
            keyboard = await _message_markup(session, "inactive_plan", fallback_keyboard, copy_text=text)
            await update.message.reply_text(text, reply_markup=keyboard)
            return

        coupon = await CouponService.get_active_coupon(session, db_user.telegram_id)
        final_price, discount_amount = CouponService.calculate_discount(original_price, coupon)

        if db_user.wallet_balance < final_price:
            text = await ShopCustomizationService.get_message(
                session,
                "insufficient_balance",
                required_price=f"{final_price:,}",
            )
            fallback_keyboard = await ShopCustomizationService.wallet_keyboard(session)
            keyboard = await _message_markup(session, "insufficient_balance", fallback_keyboard, copy_text=text)
            await update.message.reply_text(
                text,
                reply_markup=keyboard,
            )
            return

        config = await InventoryService.get_available_config(session, volume, category_key)
        if not config:
            text = await ShopCustomizationService.get_message(session, "plan_unavailable", volume=volume)
            fallback_keyboard = await ShopCustomizationService.main_menu_keyboard(session)
            keyboard = await _message_markup(session, "plan_unavailable", fallback_keyboard, copy_text=text)
            await update.message.reply_text(
                text,
                reply_markup=keyboard,
            )
            return

        db_user.wallet_balance -= final_price
        sold = await InventoryService.sell_config(session, config, db_user.telegram_id)
        if not sold:
            await session.rollback()
            text = await ShopCustomizationService.get_message(session, "plan_sold_out", volume=volume)
            fallback_keyboard = await ShopCustomizationService.main_menu_keyboard(session)
            keyboard = await _message_markup(session, "plan_sold_out", fallback_keyboard, copy_text=text)
            await update.message.reply_text(
                text,
                reply_markup=keyboard,
            )
            return

        purchase = Purchase(
            user_id=db_user.telegram_id,
            config_id=config.id,
            volume_gb=volume,
            category_key=category_key,
            price=final_price,
            original_price=original_price,
            discount_amount=discount_amount,
            coupon_id=coupon.id if coupon else None,
            coupon_code=coupon.code if coupon else None,
            service_name=service_name,
        )
        session.add(purchase)
        await session.flush()
        await CouponService.mark_active_coupon_redeemed(session, db_user.telegram_id, purchase.id)
        session.add(
            Transaction(
                user_id=db_user.telegram_id,
                amount=-final_price,
                type="purchase",
                description=f"Purchase {volume}GB - {service_name or 'بدون نام'}",
            )
        )
        await session.commit()

        public_sub_link = await SubscriptionLinkService.public_link_for_config(session, config)
        await SubscriptionLinkService.sync_to_panel(config, service_name)
        await session.commit()

        text = await ShopCustomizationService.get_message(
            session,
            "purchase_success",
            service_name=escape_markdown(service_name or f"{volume} گیگ", version=1),
            volume=volume,
            price=f"{final_price:,}",
            sub_link=public_sub_link,
        )
        keyboard = await ShopCustomizationService.purchase_success_reply_markup(session, public_sub_link)
        if keyboard is None:
            keyboard = await ShopCustomizationService.back_keyboard(session)
        await update.message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode=constants.ParseMode.MARKDOWN,
        )


async def help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "help")
        fallback_keyboard = await ShopCustomizationService.back_keyboard(session)
        keyboard = await _message_markup(session, "help", fallback_keyboard, copy_text=text)
    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def support_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "support")
        fallback_keyboard = await ShopCustomizationService.back_keyboard(session)
        keyboard = await _message_markup(session, "support", fallback_keyboard, copy_text=text)
    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def history_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        stmt = (
            select(Purchase)
            .options(selectinload(Purchase.config))
            .where(Purchase.user_id == update.effective_user.id)
            .order_by(Purchase.purchased_at.desc())
            .limit(10)
        )
        result = await session.execute(stmt)
        purchases = result.scalars().all()

    if not purchases:
        async with async_session() as session:
            text = await ShopCustomizationService.get_message(session, "no_purchase")
            fallback_keyboard = await ShopCustomizationService.back_keyboard(session)
            keyboard = await _message_markup(session, "no_purchase", fallback_keyboard, copy_text=text)
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode=constants.ParseMode.MARKDOWN)
        return

    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "purchase_history_header")
        fallback_keyboard = await ShopCustomizationService.back_keyboard(session)
        keyboard = await _message_markup(session, "purchase_history_header", fallback_keyboard, copy_text=text)

        for purchase in purchases:
            sub_link = await SubscriptionLinkService.public_link_for_config(session, purchase.config)
            discount = f" | تخفیف: {purchase.discount_amount:,} تومان" if purchase.discount_amount else ""
            coupon = f" | کد: {purchase.coupon_code}" if purchase.coupon_code else ""
            text += await ShopCustomizationService.get_message(
                session,
                "purchase_history_item",
                service_name=escape_markdown(purchase.service_name or f"{purchase.volume_gb} گیگ", version=1),
                volume=purchase.volume_gb,
                category=purchase.category_key or "default",
                price=f"{purchase.price:,}",
                discount=discount,
                coupon=coupon,
                purchased_at=purchase.purchased_at.strftime("%Y-%m-%d %H:%M"),
                sub_link=sub_link,
            )
        await session.commit()

    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def cancel_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting_coupon_code", None)
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "coupon_cancelled")
        fallback_keyboard = await ShopCustomizationService.wallet_keyboard(session)
        keyboard = await _message_markup(session, "coupon_cancelled", fallback_keyboard, copy_text=text)
    await update.message.reply_text(text, reply_markup=keyboard)


async def ask_service_name(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_id: int):
    context.user_data["awaiting_service_name"] = True
    context.user_data["pending_purchase_plan_id"] = plan_id
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "service_name_prompt")
        fallback_keyboard = await ShopCustomizationService.back_keyboard(session)
        keyboard = await _message_markup(session, "service_name_prompt", fallback_keyboard, copy_text=text)
    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def receive_service_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service_name = update.message.text.strip()
    if not service_name or len(service_name) > 60:
        async with async_session() as session:
            text = await ShopCustomizationService.get_message(session, "service_name_invalid")
            fallback_keyboard = await ShopCustomizationService.back_keyboard(session)
            keyboard = await _message_markup(session, "service_name_invalid", fallback_keyboard, copy_text=text)
        await update.message.reply_text(text, reply_markup=keyboard)
        return

    plan_id = context.user_data.get("pending_purchase_plan_id")
    context.user_data.pop("awaiting_service_name", None)
    context.user_data.pop("pending_purchase_volume", None)
    context.user_data.pop("pending_purchase_plan_id", None)
    context.user_data.pop("selected_plan_category", None)
    await process_purchase(update, context, selected_plan_id=plan_id, service_name=service_name)


async def rules_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "rules_text")
    keyboard = ReplyKeyboardMarkup([[ACCEPT_RULES]], resize_keyboard=True, one_time_keyboard=True)
    await update.effective_message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def accept_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == update.effective_user.id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                telegram_id=update.effective_user.id,
                first_name=update.effective_user.first_name or "-",
                username=update.effective_user.username,
            )
            session.add(user)
            await session.flush()
        user.accepted_rules_at = datetime.now(timezone.utc)
        await ReferralService.ensure_referral_code(session, user)
        text = await ShopCustomizationService.get_message(session, "rules_accepted")
        await session.commit()
    await update.message.reply_text(text)
    await main_menu(update, context)


async def shop_text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_required_membership(update, context):
        return
    text = update.message.text
    if text == ACCEPT_RULES:
        await accept_rules(update, context)
        return

    user = await get_or_create_user(
        update.effective_user.id,
        update.effective_user.first_name,
        update.effective_user.username,
    )
    if user.accepted_rules_at is None:
        await rules_menu(update, context)
        return

    async with async_session() as session:
        prices = await PriceService.get_all_prices(session)
        discounted_prices = await CouponService.prices_with_active_discount(session, update.effective_user.id, prices)
        action = await ShopCustomizationService.action_for_text(session, text)
        category_key = await ShopCustomizationService.category_for_text(session, text)
        selected_category = context.user_data.get("selected_plan_category")
        plan_id = await ShopCustomizationService.plan_for_text(session, text, discounted_prices, selected_category)

    if context.user_data.get("awaiting_coupon_code"):
        if action == "back_to_main":
            await cancel_coupon(update, context)
            return
        await apply_coupon_code(update, context)
        return

    if context.user_data.get("awaiting_service_name"):
        if action == "back_to_main":
            await main_menu(update, context)
            return
        await receive_service_name(update, context)
        return

    if category_key:
        await buy_category_menu(update, context, category_key)
        return

    if plan_id is not None:
        await ask_service_name(update, context, plan_id)
        return

    if action == "back_to_main":
        await main_menu(update, context)
    elif action == "buy_subscription":
        await buy_menu(update, context)
    elif action == "wallet":
        await wallet_menu(update, context)
    elif action == "purchase_history":
        await history_menu(update, context)
    elif action == "referrals":
        await referral_menu(update, context)
    elif action == "account_info":
        await account_info_menu(update, context)
    elif action == "support":
        await support_menu(update, context)
    elif action == "help":
        await help_menu(update, context)
    elif action == "apply_coupon":
        await apply_coupon_start(update, context)
    elif action and action.startswith("custom_message:"):
        async with async_session() as session:
            message = await ShopCustomizationService.get_message(session, action)
            fallback_keyboard = await ShopCustomizationService.main_menu_keyboard(session)
            keyboard = await _message_markup(session, action, fallback_keyboard, copy_text=message)
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode=constants.ParseMode.MARKDOWN,
        )
    else:
        await main_menu(update, context)


user_handlers = [
    CommandHandler("start", start),
    CommandHandler("buy", buy_menu),
    CommandHandler("wallet", wallet_menu),
    CommandHandler("referrals", referral_menu),
    CommandHandler("account", account_info_menu),
    CommandHandler("help", help_menu),
    CommandHandler("support", support_menu),
    CommandHandler("cancel", cancel_coupon),
    MessageHandler(filters.TEXT & ~filters.COMMAND, shop_text_router),
]
