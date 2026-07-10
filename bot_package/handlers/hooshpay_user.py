from __future__ import annotations

import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..database import async_session
from ..services.hooshpay_service import HooshPayError, HooshPayService
from ..services.settings_service import SettingsService
from ..services.shop_customization_service import ShopCustomizationService
from ..utils.keyboards import BACK_TO_MAIN


STEP_KEY = "hooshpay_step"


def _back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[KeyboardButton(BACK_TO_MAIN)]], resize_keyboard=True)


def clear_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(STEP_KEY, None)


def _normalize_digits(value: str) -> str:
    return value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def _parse_toman(value: str) -> int | None:
    digits = re.sub(r"[\s,،]", "", _normalize_digits(value))
    return int(digits) if digits.isdigit() else None


async def charge_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_state(context)
    context.user_data[STEP_KEY] = "amount"
    async with async_session() as session:
        minimum = await SettingsService.get_hooshpay_min_amount(session)
        text = await ShopCustomizationService.get_message(
            session,
            "hooshpay_amount_prompt",
            minimum=f"{minimum:,}",
        )
    await update.effective_message.reply_text(
        text,
        reply_markup=_back_keyboard(),
        parse_mode=getattr(text, "parse_mode", None),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    if text == BACK_TO_MAIN:
        clear_state(context)
        async with async_session() as session:
            message = await ShopCustomizationService.get_message(session, "main_menu")
            keyboard = await ShopCustomizationService.main_menu_keyboard(session)
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode=getattr(message, "parse_mode", None),
        )
        return
    if context.user_data.get(STEP_KEY) == "amount":
        await _handle_amount(update, context, text)


async def _handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE, value: str) -> None:
    amount = _parse_toman(value)
    async with async_session() as session:
        minimum = await SettingsService.get_hooshpay_min_amount(session)
        if amount is None or amount < minimum:
            text = await ShopCustomizationService.get_message(
                session,
                "hooshpay_amount_invalid",
                minimum=f"{minimum:,}",
            )
            await update.message.reply_text(
                text,
                reply_markup=_back_keyboard(),
                parse_mode=getattr(text, "parse_mode", None),
            )
            return
        try:
            invoice = await HooshPayService.create_invoice(
                session,
                user_id=update.effective_user.id,
                amount_toman=amount,
            )
        except HooshPayError as exc:
            text = await ShopCustomizationService.get_message(
                session,
                "hooshpay_unavailable",
                error=str(exc),
            )
            await update.message.reply_text(
                text,
                reply_markup=_back_keyboard(),
                parse_mode=getattr(text, "parse_mode", None),
            )
            return
        text = await ShopCustomizationService.get_message(
            session,
            "hooshpay_invoice_created",
            amount=f"{invoice.amount_toman:,}",
            payable_amount=f"{(invoice.payable_amount or invoice.amount_toman):,}",
            fee_amount=f"{(invoice.fee_amount or 0):,}",
            fee_mode=invoice.fee_mode,
            tracking_code=invoice.order_id,
        )
        pay_button_text = await SettingsService.get_hooshpay_pay_button(session)
    clear_state(context)
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton(pay_button_text, url=invoice.payment_url)]]
    )
    await update.message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=getattr(text, "parse_mode", None),
    )
