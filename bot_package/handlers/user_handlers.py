import re
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from telegram import Update, constants
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from ..database import async_session
from ..models import Purchase, Transaction, User
from ..services.coupon_service import CouponError, CouponService
from ..services.inventory_service import InventoryService
from ..services.price_service import PriceService
from ..services.referral_service import ReferralService
from ..services.shop_customization_service import ShopCustomizationService
from ..services.user_service import UserService
from ..utils.keyboards import (
    referral_share_keyboard,
)
from ..utils.messages import (
    SUPPORT_HANDLE,
)


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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    payload = context.args[0] if context.args else None
    await get_or_create_user(user.id, user.first_name, user.username, payload)
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "main_menu")
        keyboard = await ShopCustomizationService.main_menu_keyboard(session)
    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting_coupon_code", None)
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "main_menu")
        keyboard = await ShopCustomizationService.main_menu_keyboard(session)
    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def buy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await get_or_create_user(
        update.effective_user.id,
        update.effective_user.first_name,
        update.effective_user.username,
    )
    async with async_session() as session:
        prices = await PriceService.get_all_prices(session)
        discounted_prices = await CouponService.prices_with_active_discount(session, update.effective_user.id, prices)
        text = await ShopCustomizationService.get_message(session, "buy_menu")
        keyboard = await ShopCustomizationService.buy_volume_keyboard(session, discounted_prices)

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
        keyboard = await ShopCustomizationService.wallet_keyboard(session)
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
            first_name=user.first_name,
            username=f"@{user.username}" if user.username else "ثبت نشده",
            wallet_balance=f"{user.wallet_balance:,}",
            total_count=purchase_summary["total_count"],
            total_gb=f"{purchase_summary['total_gb']:,}",
            total_spent=f"{purchase_summary['total_spent']:,}",
            referral_count=referral_count,
        )
        keyboard = await ShopCustomizationService.back_keyboard(session)

    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def apply_coupon_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting_coupon_code"] = True
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "coupon_prompt")
        keyboard = await ShopCustomizationService.back_keyboard(session)
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
            keyboard = await ShopCustomizationService.wallet_keyboard(session)
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
        keyboard = await ShopCustomizationService.wallet_keyboard(session)

    context.user_data.pop("awaiting_coupon_code", None)
    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def process_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE, selected_volume: int | None = None):
    volume = selected_volume or _extract_volume(update.message.text)
    if volume is None:
        async with async_session() as session:
            text = await ShopCustomizationService.get_message(session, "invalid_plan")
            keyboard = await ShopCustomizationService.main_menu_keyboard(session)
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
            keyboard = await ShopCustomizationService.main_menu_keyboard(session)
            await update.message.reply_text(text, reply_markup=keyboard)
            return

        original_price = await PriceService.get_price(session, volume)
        if not original_price:
            text = await ShopCustomizationService.get_message(session, "inactive_plan")
            keyboard = await ShopCustomizationService.main_menu_keyboard(session)
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
            keyboard = await ShopCustomizationService.wallet_keyboard(session)
            await update.message.reply_text(
                text,
                reply_markup=keyboard,
            )
            return

        config = await InventoryService.get_available_config(session, volume)
        if not config:
            text = await ShopCustomizationService.get_message(session, "plan_unavailable", volume=volume)
            keyboard = await ShopCustomizationService.main_menu_keyboard(session)
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
            keyboard = await ShopCustomizationService.main_menu_keyboard(session)
            await update.message.reply_text(
                text,
                reply_markup=keyboard,
            )
            return

        purchase = Purchase(
            user_id=db_user.telegram_id,
            config_id=config.id,
            volume_gb=volume,
            price=final_price,
            original_price=original_price,
            discount_amount=discount_amount,
            coupon_id=coupon.id if coupon else None,
            coupon_code=coupon.code if coupon else None,
        )
        session.add(purchase)
        await session.flush()
        await CouponService.mark_active_coupon_redeemed(session, db_user.telegram_id, purchase.id)
        session.add(
            Transaction(
                user_id=db_user.telegram_id,
                amount=-final_price,
                type="purchase",
                description=f"Purchase {volume}GB",
            )
        )
        await session.commit()

        text = await ShopCustomizationService.get_message(
            session,
            "purchase_success",
            volume=volume,
            price=f"{final_price:,}",
            sub_link=config.sub_link,
        )
        keyboard = await ShopCustomizationService.back_keyboard(session)
        await update.message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode=constants.ParseMode.MARKDOWN,
        )


async def help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "help")
        keyboard = await ShopCustomizationService.back_keyboard(session)
    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def support_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "support")
        keyboard = await ShopCustomizationService.back_keyboard(session)
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
            keyboard = await ShopCustomizationService.back_keyboard(session)
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode=constants.ParseMode.MARKDOWN)
        return

    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "purchase_history_header")
        keyboard = await ShopCustomizationService.back_keyboard(session)

        for purchase in purchases:
            discount = f" | تخفیف: {purchase.discount_amount:,} تومان" if purchase.discount_amount else ""
            coupon = f" | کد: {purchase.coupon_code}" if purchase.coupon_code else ""
            text += await ShopCustomizationService.get_message(
                session,
                "purchase_history_item",
                volume=purchase.volume_gb,
                price=f"{purchase.price:,}",
                discount=discount,
                coupon=coupon,
                purchased_at=purchase.purchased_at.strftime("%Y-%m-%d %H:%M"),
                sub_link=purchase.config.sub_link,
            )

    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def cancel_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting_coupon_code", None)
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "coupon_cancelled")
        keyboard = await ShopCustomizationService.wallet_keyboard(session)
    await update.message.reply_text(text, reply_markup=keyboard)


async def shop_text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    async with async_session() as session:
        prices = await PriceService.get_all_prices(session)
        discounted_prices = await CouponService.prices_with_active_discount(session, update.effective_user.id, prices)
        action = await ShopCustomizationService.action_for_text(session, text)
        volume = await ShopCustomizationService.volume_for_text(session, text, discounted_prices)

    if context.user_data.get("awaiting_coupon_code"):
        if action == "back_to_main":
            await cancel_coupon(update, context)
            return
        await apply_coupon_code(update, context)
        return

    if volume is not None:
        await process_purchase(update, context, selected_volume=volume)
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
            keyboard = await ShopCustomizationService.main_menu_keyboard(session)
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
