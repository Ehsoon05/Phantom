import re

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from telegram import Update, constants
from telegram.ext import CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from ..database import async_session
from ..models import Purchase, Transaction, User
from ..services.coupon_service import CouponError, CouponService
from ..services.inventory_service import InventoryService
from ..services.price_service import PriceService
from ..services.referral_service import ReferralService
from ..utils.keyboards import (
    APPLY_COUPON,
    BACK_TO_MAIN,
    BUY_SUBSCRIPTION,
    HELP,
    PURCHASE_HISTORY,
    REFERRALS,
    SUPPORT,
    WALLET,
    back_to_main,
    buy_volume_keyboard,
    main_menu_keyboard,
    wallet_keyboard,
)
from ..utils.messages import (
    BUY_MENU_TEXT,
    HELP_TEXT,
    MAIN_MENU_TEXT,
    NO_PURCHASE,
    PURCHASE_SUCCESS,
    SUPPORT_HANDLE,
    SUPPORT_TEXT,
    WALLET_TEXT,
)


ENTER_COUPON_CODE = 0


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
    await update.message.reply_text(
        MAIN_MENU_TEXT,
        reply_markup=main_menu_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        MAIN_MENU_TEXT,
        reply_markup=main_menu_keyboard(),
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

    await update.message.reply_text(
        BUY_MENU_TEXT,
        reply_markup=buy_volume_keyboard(discounted_prices),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def wallet_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_or_create_user(
        update.effective_user.id,
        update.effective_user.first_name,
        update.effective_user.username,
    )
    await update.message.reply_text(
        WALLET_TEXT.format(f"{user.wallet_balance:,}", SUPPORT_HANDLE),
        reply_markup=wallet_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_or_create_user(
        update.effective_user.id,
        update.effective_user.first_name,
        update.effective_user.username,
    )
    bot_username = context.bot.username or "PhantomHubs_bot"
    async with async_session() as session:
        count = await ReferralService.count_referrals(session, user.telegram_id)

    link = f"https://t.me/{bot_username}?start=ref_{user.referral_code}"
    text = (
        "**دعوت دوستان**\n\n"
        f"لینک اختصاصی شما:\n`{link}`\n\n"
        f"تعداد کاربرانی که با لینک شما عضو شده‌اند: **{count}**"
    )
    await update.message.reply_text(text, reply_markup=wallet_keyboard(), parse_mode=constants.ParseMode.MARKDOWN)


async def apply_coupon_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "کد تخفیف را ارسال کنید.",
        reply_markup=back_to_main(),
    )
    return ENTER_COUPON_CODE


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
            await update.message.reply_text(
                "این کد تخفیف معتبر نیست یا برای حساب شما فعال نشده است.",
                reply_markup=wallet_keyboard(),
            )
            return ConversationHandler.END

    if coupon.discount_type == "percent":
        discount_text = f"{coupon.amount} درصد"
    else:
        discount_text = f"{coupon.amount:,} تومان"
    await update.message.reply_text(
        f"کد تخفیف **{coupon.code}** با مقدار **{discount_text}** فعال شد.\nقیمت‌ها در منوی خرید با تخفیف نمایش داده می‌شوند.",
        reply_markup=wallet_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def process_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    volume = _extract_volume(update.message.text)
    if volume is None:
        await update.message.reply_text(
            "پلن انتخاب‌شده معتبر نیست. لطفا دوباره از منوی خرید انتخاب کنید.",
            reply_markup=main_menu_keyboard(),
        )
        return

    await get_or_create_user(
        update.effective_user.id,
        update.effective_user.first_name,
        update.effective_user.username,
    )

    async with async_session() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == update.effective_user.id))
        db_user = user_result.scalar_one()

        if db_user.is_blocked:
            await update.message.reply_text("حساب شما مسدود شده است.", reply_markup=main_menu_keyboard())
            return

        original_price = await PriceService.get_price(session, volume)
        if not original_price:
            await update.message.reply_text("این پلن در حال حاضر فعال نیست.", reply_markup=main_menu_keyboard())
            return

        coupon = await CouponService.get_active_coupon(session, db_user.telegram_id)
        final_price, discount_amount = CouponService.calculate_discount(original_price, coupon)

        if db_user.wallet_balance < final_price:
            await update.message.reply_text(
                f"موجودی کیف پول کافی نیست.\nمبلغ موردنیاز: {final_price:,} تومان",
                reply_markup=wallet_keyboard(),
            )
            return

        config = await InventoryService.get_available_config(session, volume)
        if not config:
            await update.message.reply_text(
                f"پلن {volume} گیگ فعلا ناموجود است.",
                reply_markup=main_menu_keyboard(),
            )
            return

        db_user.wallet_balance -= final_price
        sold = await InventoryService.sell_config(session, config, db_user.telegram_id)
        if not sold:
            await session.rollback()
            await update.message.reply_text(
                f"پلن {volume} گیگ همین الان ناموجود شد. لطفا دوباره تلاش کنید.",
                reply_markup=main_menu_keyboard(),
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

        await update.message.reply_text(
            PURCHASE_SUCCESS.format(volume, f"{final_price:,}", config.sub_link),
            reply_markup=back_to_main(),
            parse_mode=constants.ParseMode.MARKDOWN,
        )


async def help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        HELP_TEXT,
        reply_markup=back_to_main(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def support_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        SUPPORT_TEXT,
        reply_markup=back_to_main(),
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
        await update.message.reply_text(NO_PURCHASE, reply_markup=back_to_main(), parse_mode=constants.ParseMode.MARKDOWN)
        return

    text = "**آخرین خریدهای شما**\n\n"
    for purchase in purchases:
        discount = f" | تخفیف: {purchase.discount_amount:,} تومان" if purchase.discount_amount else ""
        text += (
            f"حجم: {purchase.volume_gb} گیگ | مبلغ: {purchase.price:,} تومان{discount}\n"
            f"زمان: {purchase.purchased_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"`{purchase.config.sub_link}`\n\n"
        )

    await update.message.reply_text(
        text,
        reply_markup=back_to_main(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def cancel_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد.", reply_markup=wallet_keyboard())
    return ConversationHandler.END


coupon_conv = ConversationHandler(
    entry_points=[MessageHandler(_exact_filter(APPLY_COUPON), apply_coupon_start)],
    states={
        ENTER_COUPON_CODE: [
            MessageHandler(_exact_filter(BACK_TO_MAIN), cancel_coupon),
            MessageHandler(filters.TEXT & ~filters.COMMAND, apply_coupon_code),
        ]
    },
    fallbacks=[CommandHandler("cancel", cancel_coupon), MessageHandler(_exact_filter(BACK_TO_MAIN), cancel_coupon)],
)


user_handlers = [
    CommandHandler("start", start),
    coupon_conv,
    MessageHandler(_exact_filter(BACK_TO_MAIN), main_menu),
    MessageHandler(_exact_filter(BUY_SUBSCRIPTION), buy_menu),
    MessageHandler(filters.Regex(r"^📦 \d+ گیگ \|"), process_purchase),
    MessageHandler(_exact_filter(WALLET), wallet_menu),
    MessageHandler(_exact_filter(REFERRALS), referral_menu),
    MessageHandler(_exact_filter(PURCHASE_HISTORY), history_menu),
    MessageHandler(_exact_filter(SUPPORT), support_menu),
    MessageHandler(_exact_filter(HELP), help_menu),
]
