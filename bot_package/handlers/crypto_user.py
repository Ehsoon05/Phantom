"""User-facing crypto top-up flow (main bot).

Mirrors the coupon flow's style: state is kept in ``context.user_data`` and the
shop text router delegates here while a charge is in progress. No
ConversationHandler, to stay consistent with the rest of the user bot.

Steps:
  choose_coin -> enter_amount -> invoice shown
"""
from urllib.parse import quote

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, Update, constants
from telegram.ext import ContextTypes

from ..database import async_session
from ..services.crypto_payment_service import (
    SUPPORTED_COINS,
    CryptoPaymentError,
    CryptoPaymentService,
    available_coins,
)
from ..services.shop_customization_service import ShopCustomizationService
from ..utils.keyboards import BACK_TO_MAIN

STEP_KEY = "crypto_step"
COIN_KEY = "crypto_coin"

_MIN_TOMAN = 1000

# The crypto method we steer users toward (fastest + cheapest fees).
RECOMMENDED_COIN_KEY = "TON"
RECOMMENDED_TAG = "⭐ پیشنهادی"


def _display_label(key: str) -> str:
    """Coin button label, with a recommended marker on the preferred coin."""
    label = SUPPORTED_COINS[key]["label"]
    if key == RECOMMENDED_COIN_KEY:
        return f"{label} — {RECOMMENDED_TAG}"
    return label


def _coin_keyboard() -> ReplyKeyboardMarkup:
    # List the recommended coin first so it's the most prominent option.
    keys = sorted(available_coins(), key=lambda k: 0 if k == RECOMMENDED_COIN_KEY else 1)
    rows = [[KeyboardButton(_display_label(key))] for key in keys]
    rows.append([KeyboardButton(BACK_TO_MAIN)])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


def _back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[KeyboardButton(BACK_TO_MAIN)]], resize_keyboard=True)


def _coin_key_for_label(label: str) -> str | None:
    for key in available_coins():
        if _display_label(key) == label:
            return key
    return None


def _parse_toman(text: str) -> int | None:
    digits = text.strip().replace(",", "").replace("،", "").replace(" ", "")
    if not digits.isdigit():
        return None
    return int(digits)


async def charge_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point: shown when the user taps the crypto charge button or /charge."""
    coins = available_coins()
    if not coins:
        await update.message.reply_text(
            "پرداخت با ارز دیجیتال در حال حاضر فعال نیست. لطفا با پشتیبانی در تماس باشید.",
        )
        return
    context.user_data[STEP_KEY] = "choose_coin"
    context.user_data.pop(COIN_KEY, None)
    note = ""
    if RECOMMENDED_COIN_KEY in coins:
        note = "\n\n🌟 *پیشنهاد ما: TON* — سریع‌تر، کم‌هزینه‌تر و مطمئن‌تر."
    await update.message.reply_text(
        "💎 *شارژ کیف پول با ارز دیجیتال*\n\nارز مورد نظر خود را انتخاب کنید:" + note,
        reply_markup=_coin_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(STEP_KEY, None)
    context.user_data.pop(COIN_KEY, None)
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "main_menu")
        keyboard = await ShopCustomizationService.main_menu_keyboard(session)
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=constants.ParseMode.MARKDOWN)


async def handle_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process the next message while a crypto charge is in progress."""
    text = (update.message.text or "").strip()
    if text == BACK_TO_MAIN:
        await _cancel(update, context)
        return

    step = context.user_data.get(STEP_KEY)
    if step == "choose_coin":
        await _handle_choose_coin(update, context, text)
    elif step == "enter_amount":
        await _handle_enter_amount(update, context, text)
    else:
        await _cancel(update, context)


async def _handle_choose_coin(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    coin_key = _coin_key_for_label(text)
    if not coin_key:
        await update.message.reply_text(
            "لطفا یکی از ارزهای موجود را از دکمه‌های زیر انتخاب کنید.",
            reply_markup=_coin_keyboard(),
        )
        return
    context.user_data[COIN_KEY] = coin_key
    context.user_data[STEP_KEY] = "enter_amount"
    await update.message.reply_text(
        f"ارز انتخاب‌شده: *{SUPPORTED_COINS[coin_key]['label']}*\n\n"
        "مبلغی که می‌خواهید کیف پول شما شارژ شود را به *تومان* وارد کنید:\n"
        f"(حداقل {_MIN_TOMAN:,} تومان)",
        reply_markup=_back_keyboard(),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def _handle_enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    toman = _parse_toman(text)
    if toman is None or toman < _MIN_TOMAN:
        await update.message.reply_text(
            f"مبلغ نامعتبر است. یک عدد بزرگ‌تر از {_MIN_TOMAN:,} تومان وارد کنید.",
            reply_markup=_back_keyboard(),
        )
        return

    coin_key = context.user_data.get(COIN_KEY)
    if not coin_key:
        await _cancel(update, context)
        return

    async with async_session() as session:
        try:
            invoice = await CryptoPaymentService.create_invoice(
                session, update.effective_user.id, coin_key, toman
            )
        except CryptoPaymentError as exc:
            if "Too many open invoices" in str(exc):
                message = (
                    "شما چند صورتحساب باز دارید. لطفا یکی از پرداخت‌های قبلی را کامل کنید "
                    "یا تا منقضی‌شدن آن صبر کنید، سپس دوباره تلاش کنید."
                )
            else:
                message = (
                    "متاسفانه ساخت صورتحساب ممکن نشد. لطفا بعدا دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
                )
            await update.message.reply_text(message)
            await _cancel(update, context)
            return

    context.user_data.pop(STEP_KEY, None)
    context.user_data.pop(COIN_KEY, None)
    await _send_invoice(update, invoice)


def _copy_button(label: str, value: str) -> InlineKeyboardButton:
    # Version-agnostic copy button (matches ShopCustomizationService usage).
    return InlineKeyboardButton(label, api_kwargs={"copy_text": {"text": value}})


async def _send_invoice(update: Update, invoice) -> None:
    from decimal import Decimal

    coin = invoice.coin
    try:
        unit_rate = int(Decimal(invoice.locked_rate))
    except Exception:  # noqa: BLE001
        unit_rate = 0
    source_label = "نرخ نوبیتکس" if invoice.rate_source == "online" else "نرخ دستی"
    ttl_min = (
        max(1, int((invoice.expires_at - invoice.created_at).total_seconds() // 60))
        if invoice.expires_at and invoice.created_at
        else None
    )

    lines = [
        f"💎 پرداخت {coin}",
        "",
        f"📊 مبلغ شبکه: {invoice.expected_crypto} {coin}",
        f"👛 معادل تومانی: {invoice.quoted_toman:,} تومان ({source_label})",
    ]
    if unit_rate:
        lines.append(f"🔎 تقریباً ۱ {coin} ≈ {unit_rate:,} تومان")
    if ttl_min:
        lines += ["", f"🕘 مهلت پرداخت: {ttl_min} دقیقه (قیمت {coin} مدام عوض می‌شود)."]

    detail_note = "📄 جزئیات برای کپی — مقادیر زیر را می‌توانید از دکمه‌های «کپی» بردارید"
    detail_note += "؛ کامنت باید عیناً در تراکنش باشد." if invoice.memo else "."
    lines += [
        "",
        detail_note,
        "",
        "مقصد (ولت دریافت):",
        f"`{invoice.deposit_address}`",
        "",
        f"مقدار واریز ({coin}):",
        f"`{invoice.expected_crypto}`",
    ]
    if invoice.memo:
        lines += [
            "",
            "کامنت تراکنش (عیناً همین - ممو تگ):",
            f"`{invoice.memo}`",
        ]

    buttons = [
        [_copy_button("📋 کپی آدرس مقصد", invoice.deposit_address)],
        [_copy_button(f"📋 کپی مقدار ({coin})", str(invoice.expected_crypto))],
    ]
    if invoice.memo:
        buttons.append([_copy_button("📋 کپی کامنت/ممو", invoice.memo)])

    if coin == "TON" and invoice.network == "TON":
        # Native-TON ton:// deep link with exact nanoton amount and memo comment.
        nano = int((Decimal(invoice.expected_crypto) * (Decimal(10) ** 9)).to_integral_value())
        ton_url = f"ton://transfer/{invoice.deposit_address}?amount={nano}"
        if invoice.memo:
            ton_url += f"&text={quote(invoice.memo)}"
        buttons.append([InlineKeyboardButton("🌐 باز کردن کیف TON", url=ton_url)])
        lines += ["", "🌐 دکمهٔ «باز کردن کیف TON» همان مقدار TON و کامنت را در کیف پر می‌کند."]

    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
