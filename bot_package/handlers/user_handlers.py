import re

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from telegram import Update, constants
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from ..database import async_session
from ..models import Purchase, Transaction, User
from ..services.inventory_service import InventoryService
from ..services.price_service import PriceService
from ..utils.keyboards import (
    BACK_TO_MAIN,
    BUY_SUBSCRIPTION,
    HELP,
    PURCHASE_HISTORY,
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


async def get_or_create_user(telegram_id: int, name: str, username: str | None):
    async with async_session() as session:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            user = User(telegram_id=telegram_id, first_name=name, username=username)
            session.add(user)
            await session.commit()
        return user


def _extract_volume(text: str) -> int | None:
    match = re.search(r"(\d+)\s*گیگ", text)
    return int(match.group(1)) if match else None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await get_or_create_user(user.id, user.first_name, user.username)
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
    async with async_session() as session:
        prices = await PriceService.get_all_prices(session)

    await update.message.reply_text(
        BUY_MENU_TEXT,
        reply_markup=buy_volume_keyboard(prices),
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

        price = await PriceService.get_price(session, volume)
        if not price:
            await update.message.reply_text("این پلن در حال حاضر فعال نیست.", reply_markup=main_menu_keyboard())
            return

        if db_user.wallet_balance < price:
            await update.message.reply_text(
                f"موجودی کیف پول کافی نیست.\nمبلغ موردنیاز: {price:,} تومان",
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

        db_user.wallet_balance -= price
        sold = await InventoryService.sell_config(session, config, db_user.telegram_id)
        if not sold:
            await session.rollback()
            await update.message.reply_text(
                f"پلن {volume} گیگ همین الان ناموجود شد. لطفا دوباره تلاش کنید.",
                reply_markup=main_menu_keyboard(),
            )
            return

        session.add(
            Purchase(
                user_id=db_user.telegram_id,
                config_id=config.id,
                volume_gb=volume,
                price=price,
            )
        )
        session.add(
            Transaction(
                user_id=db_user.telegram_id,
                amount=-price,
                type="purchase",
                description=f"Purchase {volume}GB",
            )
        )
        await session.commit()

        await update.message.reply_text(
            PURCHASE_SUCCESS.format(volume, f"{price:,}", config.sub_link),
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
        text += (
            f"حجم: {purchase.volume_gb} گیگ | مبلغ: {purchase.price:,} تومان\n"
            f"زمان: {purchase.purchased_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"`{purchase.config.sub_link}`\n\n"
        )

    await update.message.reply_text(
        text,
        reply_markup=back_to_main(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


user_handlers = [
    CommandHandler("start", start),
    MessageHandler(filters.Regex(f"^{re.escape(BACK_TO_MAIN)}$"), main_menu),
    MessageHandler(filters.Regex(f"^{re.escape(BUY_SUBSCRIPTION)}$"), buy_menu),
    MessageHandler(filters.Regex(r"^📦 \d+ گیگ \|"), process_purchase),
    MessageHandler(filters.Regex(f"^{re.escape(WALLET)}$"), wallet_menu),
    MessageHandler(filters.Regex(f"^{re.escape(PURCHASE_HISTORY)}$"), history_menu),
    MessageHandler(filters.Regex(f"^{re.escape(SUPPORT)}$"), support_menu),
    MessageHandler(filters.Regex(f"^{re.escape(HELP)}$"), help_menu),
]
