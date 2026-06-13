from __future__ import annotations

import re
from urllib.parse import quote

from sqlalchemy import select
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.ext import ContextTypes

from ..config_loader import BotConfig
from ..database import async_session
from ..models import User
from ..services.phone_verification_service import PhoneVerificationService
from ..services.rial_payment_service import RialPaymentService
from ..services.settings_service import SettingsService
from ..services.shop_customization_service import ShopCustomizationService
from ..utils.keyboards import BACK_TO_MAIN


STEP_KEY = "rial_step"
AMOUNT_KEY = "rial_amount"
PHONE_KEY = "rial_phone"
VERIFY_PHONE_KEY = "verify_phone_for_webapp"


def _back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[KeyboardButton(BACK_TO_MAIN)]], resize_keyboard=True)


def _contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📱 اشتراک شماره تماس", request_contact=True)],
            [KeyboardButton(BACK_TO_MAIN)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _normalize_digits(value: str) -> str:
    return value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def _parse_toman(value: str) -> int | None:
    digits = re.sub(r"[\s,،]", "", _normalize_digits(value))
    return int(digits) if digits.isdigit() else None


def _normalize_iran_phone(value: str) -> str | None:
    return PhoneVerificationService.normalize_iran_phone(value)


def _normalize_card(value: str) -> str | None:
    digits = re.sub(r"\D", "", _normalize_digits(value))
    if len(digits) != 16 or len(set(digits)) == 1:
        return None
    checksum = 0
    for index, digit in enumerate(digits):
        value = int(digit) * (2 if index % 2 == 0 else 1)
        checksum += value - 9 if value > 9 else value
    return digits if checksum % 10 == 0 else None


def clear_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(STEP_KEY, None)
    context.user_data.pop(AMOUNT_KEY, None)
    context.user_data.pop(PHONE_KEY, None)
    context.user_data.pop(VERIFY_PHONE_KEY, None)


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_state(context)
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "main_menu")
        keyboard = await ShopCustomizationService.main_menu_keyboard(session)
    await update.effective_message.reply_text(text, reply_markup=keyboard, parse_mode=getattr(text, "parse_mode", None))


async def charge_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_state(context)
    context.user_data[STEP_KEY] = "amount"
    async with async_session() as session:
        minimum = await SettingsService.get_rial_min_amount(session)
        text = await ShopCustomizationService.get_message(
            session,
            "rial_amount_prompt",
            minimum=f"{minimum:,}",
        )
    await update.effective_message.reply_text(
        text,
        reply_markup=_back_keyboard(),
        parse_mode=getattr(text, "parse_mode", None),
    )


async def verify_phone_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_state(context)
    context.user_data[VERIFY_PHONE_KEY] = True
    async with async_session() as session:
        user = (
            await session.execute(
                select(User).where(User.telegram_id == update.effective_user.id)
            )
        ).scalar_one_or_none()
        if user is None:
            session.add(
                User(
                    telegram_id=update.effective_user.id,
                    first_name=update.effective_user.first_name or "",
                    username=update.effective_user.username,
                )
            )
            await session.commit()
    await update.effective_message.reply_text(
        "**تایید شماره برای پرداخت کارت‌به‌کارت**\n\n"
        "شماره متعلق به همین اکانت تلگرام را با دکمه زیر ارسال کنید.\n"
        "فقط شماره موبایل ایران پذیرفته می‌شود.",
        reply_markup=_contact_keyboard(),
        parse_mode="Markdown",
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    if text == BACK_TO_MAIN:
        await _cancel(update, context)
        return

    step = context.user_data.get(STEP_KEY)
    if step == "amount":
        await _handle_amount(update, context, text)
    elif step == "card":
        await _handle_card(update, context, text)
    elif step == "phone":
        await update.message.reply_text(
            "برای تایید مالکیت شماره، فقط از دکمه «اشتراک شماره تماس» استفاده کنید.",
            reply_markup=_contact_keyboard(),
        )


async def _handle_amount(update: Update, context: ContextTypes.DEFAULT_TYPE, value: str) -> None:
    amount = _parse_toman(value)
    async with async_session() as session:
        minimum = await SettingsService.get_rial_min_amount(session)
        require_phone = await SettingsService.rial_phone_required(session)
        user = (
            await session.execute(
                select(User).where(User.telegram_id == update.effective_user.id)
            )
        ).scalar_one_or_none()
        if amount is None or amount < minimum:
            text = await ShopCustomizationService.get_message(
                session,
                "rial_amount_invalid",
                minimum=f"{minimum:,}",
            )
            await update.message.reply_text(
                text,
                reply_markup=_back_keyboard(),
                parse_mode=getattr(text, "parse_mode", None),
            )
            return
        context.user_data[AMOUNT_KEY] = amount
        if require_phone and not (user and user.verified_phone_number):
            context.user_data[STEP_KEY] = "phone"
            text = await ShopCustomizationService.get_message(session, "rial_phone_prompt")
            keyboard = _contact_keyboard()
        else:
            if user and user.verified_phone_number:
                context.user_data[PHONE_KEY] = user.verified_phone_number
            context.user_data[STEP_KEY] = "card"
            text = await ShopCustomizationService.get_message(session, "rial_card_prompt")
            keyboard = _back_keyboard()
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=getattr(text, "parse_mode", None))


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    standalone_verification = bool(context.user_data.get(VERIFY_PHONE_KEY))
    if context.user_data.get(STEP_KEY) != "phone" and not standalone_verification:
        return
    contact = update.message.contact
    valid_owner = contact and contact.user_id == update.effective_user.id
    phone = _normalize_iran_phone(contact.phone_number) if contact and valid_owner else None
    if not phone:
        async with async_session() as session:
            support_handle = await SettingsService.get_rial_support_handle(session)
            text = await ShopCustomizationService.get_message(
                session,
                "rial_phone_invalid",
                support_handle=support_handle,
            )
            keyboard = await ShopCustomizationService.wallet_keyboard(session)
        clear_state(context)
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode=getattr(text, "parse_mode", None))
        return

    async with async_session() as session:
        await PhoneVerificationService.verify(session, update.effective_user.id, phone)

    if standalone_verification:
        clear_state(context)
        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("🛍 بازگشت به مینی‌اپ", web_app=WebAppInfo(url=BotConfig.WEBAPP_URL))]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await update.message.reply_text(
            "✅ شماره ایران شما با موفقیت تایید شد.\n"
            "اکنون می‌توانید پرداخت کارت‌به‌کارت را در مینی‌اپ انجام دهید.",
            reply_markup=keyboard,
        )
        return

    context.user_data[PHONE_KEY] = phone
    context.user_data[STEP_KEY] = "card"
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "rial_card_prompt")
    await update.message.reply_text(text, reply_markup=_back_keyboard(), parse_mode=getattr(text, "parse_mode", None))


async def _handle_card(update: Update, context: ContextTypes.DEFAULT_TYPE, value: str) -> None:
    source_card = _normalize_card(value)
    if not source_card:
        async with async_session() as session:
            text = await ShopCustomizationService.get_message(session, "rial_card_invalid")
        await update.message.reply_text(text, reply_markup=_back_keyboard(), parse_mode=getattr(text, "parse_mode", None))
        return

    amount = context.user_data.get(AMOUNT_KEY)
    if not isinstance(amount, int):
        await charge_start(update, context)
        return

    async with async_session() as session:
        user = (
            await session.execute(
                select(User).where(User.telegram_id == update.effective_user.id)
            )
        ).scalar_one_or_none()
        phone = context.user_data.get(PHONE_KEY) or (
            user.verified_phone_number if user else None
        )
        support_handle = await SettingsService.get_rial_support_handle(session)
        request = await RialPaymentService.create_request(
            session,
            user_id=update.effective_user.id,
            amount_toman=amount,
            phone_number=phone,
            source_card=source_card,
            support_handle=support_handle,
            request_text="",
        )
        copy_text = (
            "سلام،\n\n"
            f"درخواست شارژ حساب به مبلغ {amount:,} تومان را دارم\n"
            f"شماره کارت مبدا: {source_card}\n"
            "تشکر 🙏"
        )
        direct_text = (
            f"{copy_text}\n"
            f"کد پیگیری: {request.tracking_code}\n"
            f"آیدی عددی تلگرام: {update.effective_user.id}"
        )
        if phone:
            direct_text += f"\nشماره تماس: {phone}"
        message = await ShopCustomizationService.get_message(
            session,
            "rial_payment_request",
            support_handle=support_handle,
            amount=f"{amount:,}",
            source_card=source_card,
            tracking_code=request.tracking_code,
            phone_number=phone or "دریافت نشد",
            copy_text=copy_text,
        )
        await RialPaymentService.update_request_text(session, request, direct_text)

    username = support_handle.lstrip("@")
    send_url = f"https://t.me/{username}?text={quote(direct_text, safe='')}"
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 کپی متن پرداخت", api_kwargs={"copy_text": {"text": copy_text}})],
            [InlineKeyboardButton("📩 ارسال به ادمین", url=send_url)],
        ]
    )
    clear_state(context)
    await update.message.reply_text(
        message,
        reply_markup=keyboard,
        parse_mode=getattr(message, "parse_mode", None),
    )
