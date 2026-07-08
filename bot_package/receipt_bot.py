import logging

from sqlalchemy import select
from telegram import Bot, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update, constants
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from .config_loader import BotConfig
from .database import async_session
from .models import RialPaymentRequest, User
from .services.rial_payment_service import RialPaymentService
from .services.settings_service import SettingsService
from .services.shop_customization_service import ShopCustomizationService
from .utils.datetime_format import format_tehran_datetime

logger = logging.getLogger(__name__)

RECEIPT_DECISION_PREFIX = "rial_receipt"
REJECT_STATE_KEY = "rial_reject_request_id"
SKIP_RECEIPT_MESSAGE_KEY = "skip_receipt_message_id"


def _decision_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ تایید و شارژ", callback_data=f"{RECEIPT_DECISION_PREFIX}:approve:{request_id}"),
                InlineKeyboardButton("❌ رد رسید", callback_data=f"{RECEIPT_DECISION_PREFIX}:reject:{request_id}"),
            ]
        ]
    )


def _admin_allowed(admin_id: int, allowed_ids: list[int]) -> bool:
    return admin_id in allowed_ids or admin_id in BotConfig.OWNER_USER_IDS or admin_id in BotConfig.ADMIN_USER_IDS


async def _request_values(session, request: RialPaymentRequest, user: User | None) -> dict:
    username = user.username if user and user.username else ""
    return {
        "user_name": user.first_name if user and user.first_name else "",
        "username": f"@{username.lstrip('@')}" if username else "",
        "telegram_id": str(request.user_id),
        "phone_number": request.phone_number or "دریافت نشده",
        "amount": f"{request.amount_toman:,}",
        "source_card": request.source_card,
        "tracking_code": request.tracking_code,
        "created_at": format_tehran_datetime(request.created_at),
    }


async def send_receipt_to_admins(
    *,
    request_id: int,
    source_chat_id: int,
    source_message_id: int,
    receipt_text: str | None,
    source_bot: Bot,
    source_message: Message | None = None,
) -> tuple[bool, object | None]:
    async with async_session() as session:
        request = await RialPaymentService.get_request(session, request_id)
        if not request:
            return False, "درخواست پرداخت فعالی پیدا نشد."
        if RialPaymentService.is_expired(request):
            await RialPaymentService.mark_expired(session, request)
            text = await ShopCustomizationService.get_message(session, "rial_receipt_expired")
            return False, text
        user = (
            await session.execute(select(User).where(User.telegram_id == request.user_id))
        ).scalar_one_or_none()
        await RialPaymentService.record_receipt(
            session,
            request,
            chat_id=source_chat_id,
            message_id=source_message_id,
            receipt_text=receipt_text,
        )
        values = await _request_values(session, request, user)
        admin_text = await ShopCustomizationService.get_message(
            session,
            "rial_receipt_admin_request",
            escape_markdown_values=True,
            **values,
        )
        admins = await SettingsService.get_rial_receipt_admin_ids(session)
        user_text = await ShopCustomizationService.get_message(
            session,
            "rial_receipt_received",
            tracking_code=request.tracking_code,
            amount=f"{request.amount_toman:,}",
        )

    admin_bot = BotConfig.RIAL_RECEIPT_BOT_TOKEN and Bot(BotConfig.RIAL_RECEIPT_BOT_TOKEN)
    if admin_bot is None:
        return False, "بات تایید واریز فعال نیست. لطفاً به پشتیبانی پیام بدهید."

    sent_admin_messages: list[dict] = []
    for admin_id in admins:
        try:
            header = await admin_bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                parse_mode=getattr(admin_text, "parse_mode", None),
                reply_markup=_decision_keyboard(request_id),
                disable_web_page_preview=True,
            )
            copied = await _send_receipt_copy(
                admin_bot=admin_bot,
                source_bot=source_bot,
                admin_id=admin_id,
                source_chat_id=source_chat_id,
                source_message_id=source_message_id,
                source_message=source_message,
                receipt_text=receipt_text,
            )
            sent_admin_messages.append(
                {
                    "chat_id": admin_id,
                    "header_message_id": header.message_id,
                    "receipt_message_id": copied.message_id,
                }
            )
        except Exception as exc:
            logger.info("Could not forward rial receipt %s to admin %s: %s", request_id, admin_id, exc)

    async with async_session() as session:
        refreshed = await RialPaymentService.get_request(session, request_id)
        if refreshed:
            await RialPaymentService.set_admin_messages(session, refreshed, sent_admin_messages)
    return True, user_text


async def _send_receipt_copy(
    *,
    admin_bot: Bot,
    source_bot: Bot,
    admin_id: int,
    source_chat_id: int,
    source_message_id: int,
    source_message: Message | None,
    receipt_text: str | None,
) -> Message:
    if source_message and source_message.photo:
        file = await source_bot.get_file(source_message.photo[-1].file_id)
        payload = bytes(await file.download_as_bytearray())
        return await admin_bot.send_photo(
            chat_id=admin_id,
            photo=payload,
            caption=source_message.caption,
        )
    if source_message and source_message.document:
        file = await source_bot.get_file(source_message.document.file_id)
        payload = bytes(await file.download_as_bytearray())
        return await admin_bot.send_document(
            chat_id=admin_id,
            document=payload,
            filename=source_message.document.file_name,
            caption=source_message.caption,
        )
    if receipt_text:
        return await admin_bot.send_message(chat_id=admin_id, text=receipt_text)
    return await source_bot.copy_message(
        chat_id=admin_id,
        from_chat_id=source_chat_id,
        message_id=source_message_id,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = context.args[0] if context.args else ""
    request_id = None
    if payload.startswith("r_"):
        try:
            request_id = int(payload.removeprefix("r_"))
        except ValueError:
            request_id = None
    await update.effective_message.reply_text(
        "رسید پرداخت را داخل بات اصلی PhantomHubs ارسال کنید. این بات فقط برای تایید ادمین‌ها استفاده می‌شود."
    )


async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.effective_message:
        return
    if context.user_data.pop(SKIP_RECEIPT_MESSAGE_KEY, None) == update.effective_message.message_id:
        return
    request_id = context.user_data.get("rial_receipt_request_id")
    async with async_session() as session:
        request = await RialPaymentService.get_request(session, request_id) if request_id else None
        if not request or request.user_id != update.effective_user.id:
            request = await RialPaymentService.latest_receipt_waiting_request(session, update.effective_user.id)
        if not request:
            await update.effective_message.reply_text("درخواست پرداخت فعالی پیدا نشد. ابتدا از ربات اصلی یا مینی‌اپ درخواست پرداخت ثبت کنید.")
            return
        if RialPaymentService.is_expired(request):
            await RialPaymentService.mark_expired(session, request)
            text = await ShopCustomizationService.get_message(session, "rial_receipt_expired")
            await update.effective_message.reply_text(text, parse_mode=getattr(text, "parse_mode", None))
            return
    ok, user_text = await send_receipt_to_admins(
        request_id=request.id,
        source_chat_id=update.effective_chat.id,
        source_message_id=update.effective_message.message_id,
        receipt_text=update.effective_message.text or update.effective_message.caption,
        source_bot=context.bot,
        source_message=update.effective_message,
    )
    await update.effective_message.reply_text(
        user_text or "رسید دریافت شد.",
        parse_mode=getattr(user_text, "parse_mode", None),
    )


async def decision_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = (query.data or "").split(":")
    if len(parts) != 3:
        return
    _, action, raw_id = parts
    try:
        request_id = int(raw_id)
    except ValueError:
        return
    async with async_session() as session:
        admins = await SettingsService.get_rial_receipt_admin_ids(session)
    if not _admin_allowed(query.from_user.id, admins):
        await query.answer("دسترسی ندارید.", show_alert=True)
        return
    if action == "reject":
        context.user_data[REJECT_STATE_KEY] = request_id
        await query.message.reply_text("دلیل رد رسید را بفرستید. اگر دلیل نمی‌خواهید، فقط `-` ارسال کنید.", parse_mode=constants.ParseMode.MARKDOWN)
        return
    await _decide(update, context, request_id=request_id, approve=True, reason=None)


async def reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request_id = context.user_data.pop(REJECT_STATE_KEY, None)
    if not request_id:
        return
    context.user_data[SKIP_RECEIPT_MESSAGE_KEY] = update.message.message_id
    reason = (update.message.text or "").strip()
    if reason in {"", "-", "ندارد"}:
        reason = None
    await _decide(update, context, request_id=int(request_id), approve=False, reason=reason)


async def _decide(update: Update, context: ContextTypes.DEFAULT_TYPE, *, request_id: int, approve: bool, reason: str | None):
    actor_id = update.effective_user.id
    async with async_session() as session:
        admins = await SettingsService.get_rial_receipt_admin_ids(session)
        if not _admin_allowed(actor_id, admins):
            await update.effective_message.reply_text("دسترسی ندارید.")
            return
        request, wallet_balance = await RialPaymentService.decide_request(
            session,
            request_id=request_id,
            approve=approve,
            admin_id=actor_id,
            rejection_reason=reason,
        )
        if not request:
            await update.effective_message.reply_text("درخواست پیدا نشد.")
            return
        if approve and wallet_balance is not None:
            user_text = await ShopCustomizationService.get_message(
                session,
                "rial_receipt_approved",
                amount=f"{request.amount_toman:,}",
                wallet_balance=f"{wallet_balance:,}",
                tracking_code=request.tracking_code,
            )
        else:
            reason_text = f"\nدلیل رد: {reason}" if reason else ""
            user_text = await ShopCustomizationService.get_message(
                session,
                "rial_receipt_rejected",
                amount=f"{request.amount_toman:,}",
                tracking_code=request.tracking_code,
                reason_text=reason_text,
            )
    try:
        await context.bot.send_message(
            chat_id=request.user_id,
            text=user_text,
            parse_mode=getattr(user_text, "parse_mode", None),
        )
    except Exception:
        pass
    await update.effective_message.reply_text("✅ تایید شد و کیف پول شارژ شد." if approve else "❌ رسید رد شد.")


async def setup_receipt_bot():
    if not BotConfig.RIAL_RECEIPT_BOT_TOKEN:
        logger.info("RIAL_RECEIPT_BOT_TOKEN is empty; receipt bot is disabled")
        return None
    app = Application.builder().token(BotConfig.RIAL_RECEIPT_BOT_TOKEN).build()
    await app.bot.set_my_commands(
        [
            BotCommand("start", "ارسال رسید پرداخت"),
        ]
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(decision_callback, pattern=f"^{RECEIPT_DECISION_PREFIX}:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reject_reason), group=0)
    return app
