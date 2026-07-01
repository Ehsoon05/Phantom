import io
import re
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.parse import quote

import qrcode
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
    constants,
)
from telegram.error import BadRequest
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
try:
    from telegram.helpers import escape_markdown
except ImportError:
    def escape_markdown(text: str, version: int = 1) -> str:
        del version
        return text.replace("\\", "\\\\").replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

from . import crypto_user, rial_user
from ..config_loader import BotConfig
from ..database import async_session
from ..models import Config, Purchase, User
from ..services.coupon_service import CouponError, CouponService
from ..services.settings_service import SettingsService
from ..services.marzban_trial_service import MarzbanTrialError, MarzbanTrialService
from ..services.price_service import PriceService
from ..services.purchase_service import (
    InsufficientBalance,
    PlanNotFound,
    PlanUnavailable,
    PurchaseError,
    purchase_plan,
    renew_purchase,
)
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
RENEW_PREMIUM_EMOJI_ID = "6030657343744644592"


async def open_webapp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    del context
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("🛍 ورود به فروشگاه", web_app=WebAppInfo(url=BotConfig.WEBAPP_URL))]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.effective_message.reply_text(
        "برای ورود به فروشگاه و مدیریت سرویس‌ها، دکمه زیر را بزنید.",
        reply_markup=keyboard,
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


async def _process_referral_rewards(context: ContextTypes.DEFAULT_TYPE, referred_user_id: int) -> None:
    async with async_session() as session:
        rewards = await ReferralService.evaluate_referred_user(session, referred_user_id)
        if not rewards:
            return
        referrer_id = (
            await session.execute(
                select(User.referred_by_user_id).where(User.telegram_id == referred_user_id)
            )
        ).scalar_one()
        await session.commit()

    for reward in rewards:
        if reward["config"] is not None:
            await SubscriptionLinkService.sync_to_panel(reward["config"], reward["service_name"])
    try:
        lines = ["🎁 **پاداش دعوت دوستان برای شما ثبت شد!**", ""]
        for reward in rewards:
            lines.append(
                f"• {reward['rule']}: **{reward['reward']}** "
                f"(تعداد معتبر: {reward['qualified_count']})"
            )
        await context.bot.send_message(
            chat_id=referrer_id,
            text="\n".join(lines),
            parse_mode=constants.ParseMode.MARKDOWN,
        )
    except Exception:
        pass


def _exact_filter(text: str):
    return filters.Regex(f"^{re.escape(text)}$")


def _extract_volume(text: str) -> int | None:
    match = re.search(r"(\d+)\s*گیگ", text)
    return int(match.group(1)) if match else None


def _parse_mode(text: str):
    return getattr(text, "parse_mode", constants.ParseMode.MARKDOWN)


async def _message_markup(session, key: str, fallback_markup=None, *, default_url: str | None = None, copy_text: str | None = None):
    return await ShopCustomizationService.message_reply_markup(
        session,
        key,
        fallback_markup=fallback_markup,
        default_url=default_url,
        copy_text=copy_text,
    )


async def _reply_shop_message(message, text, *, reply_markup=None) -> None:
    photo_file_id = getattr(text, "photo_file_id", None)
    parse_mode = _parse_mode(text)
    if not photo_file_id:
        await message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return

    if len(str(text)) <= 1024:
        await message.reply_photo(
            photo=photo_file_id,
            caption=str(text),
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        return

    await message.reply_photo(photo=photo_file_id)
    await message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)


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
    rial_user.clear_state(context)
    if not await ensure_required_membership(update, context):
        return
    db_user = await get_or_create_user(user.id, user.first_name, user.username, payload)
    if payload == "verify_phone":
        await rial_user.verify_phone_start(update, context)
        return
    if db_user.accepted_rules_at is None:
        await rules_menu(update, context)
        return
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "main_menu")
        fallback_keyboard = await ShopCustomizationService.main_menu_keyboard(session)
        keyboard = await _message_markup(session, "main_menu", fallback_keyboard, copy_text=text)
    await _reply_shop_message(update.message, text, reply_markup=keyboard)


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
    await _reply_shop_message(update.message, text, reply_markup=keyboard)


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

    await _reply_shop_message(update.message, text, reply_markup=keyboard)


async def buy_category_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, category_key: str):
    context.user_data["selected_plan_category"] = category_key
    context.user_data.pop("selected_plan_duration", None)
    if ShopCustomizationService.duration_options_for_category(category_key):
        async with async_session() as session:
            text = "لطفاً مدت زمان سرویس را مشخص کنید."
            keyboard = await ShopCustomizationService.buy_duration_keyboard(session, category_key)
        await update.message.reply_text(text, reply_markup=keyboard)
        return

    await buy_category_plans_menu(update, context, category_key)


async def buy_category_plans_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, category_key: str):
    async with async_session() as session:
        prices = await PriceService.get_all_prices(session)
        discounted_prices = await CouponService.prices_with_active_discount(session, update.effective_user.id, prices)
        text = await ShopCustomizationService.get_message(session, "buy_menu")
        fallback_keyboard = await ShopCustomizationService.buy_category_keyboard(session, category_key, discounted_prices)
        keyboard = await _message_markup(session, "buy_menu", fallback_keyboard, copy_text=text)

    await _reply_shop_message(update.message, text, reply_markup=keyboard)


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
    await _reply_shop_message(update.message, text, reply_markup=keyboard)


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
        rules = await ReferralService.list_rules(session, active_only=True)
        if rules:
            progress_lines = ["", "", "🎁 **جایزه‌های فعال و پیشرفت شما**"]
            for rule in rules:
                qualified = await ReferralService.count_qualified(
                    session, user.telegram_id, rule.qualification_type
                )
                target = (
                    ((qualified // rule.required_count) + 1) * rule.required_count
                    if rule.is_repeatable
                    else rule.required_count
                )
                reward = (
                    f"{rule.wallet_amount or 0:,} تومان"
                    if rule.reward_type == "wallet"
                    else "سرویس رایگان"
                )
                progress_lines.append(
                    f"• {escape_markdown(rule.title, version=1)}: "
                    f"**{qualified}/{target}** نفر معتبر ← {reward}"
                )
            text = text + "".join(line + "\n" for line in progress_lines).rstrip()
        share_text = await ShopCustomizationService.get_message(
            session,
            "referral_share_text",
            link=link,
        )
        followup = await ShopCustomizationService.get_message(session, "referral_followup")
        keyboard = await ShopCustomizationService.main_menu_keyboard(session)

    share_url = f"https://t.me/share/url?url={quote(link)}&text={quote(str(share_text))}"
    await _reply_shop_message(update.message, text, reply_markup=referral_share_keyboard(share_url))
    await _reply_shop_message(update.message, followup, reply_markup=keyboard)


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

    await _reply_shop_message(update.message, text, reply_markup=keyboard)


async def apply_coupon_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting_coupon_code"] = True
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "coupon_prompt")
        fallback_keyboard = await ShopCustomizationService.back_keyboard(session)
        keyboard = await _message_markup(session, "coupon_prompt", fallback_keyboard, copy_text=text)
    await _reply_shop_message(update.message, text, reply_markup=keyboard)


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
            await _reply_shop_message(update.message, text, reply_markup=keyboard)
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
    await _reply_shop_message(update.message, text, reply_markup=keyboard)


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
        await _reply_shop_message(update.message, text, reply_markup=keyboard)
        return

    await get_or_create_user(
        update.effective_user.id,
        update.effective_user.first_name,
        update.effective_user.username,
    )

    async with async_session() as session:
        try:
            # purchase_plan locks the wallet row with .with_for_update() before debiting.
            result = await purchase_plan(
                session,
                telegram_id=update.effective_user.id,
                plan_id=selected_plan_id,
                service_name=service_name,
                source_label="bot",
            )
        except InsufficientBalance:
            text = await ShopCustomizationService.get_message(session, "insufficient_balance", required_price="موردنیاز")
            fallback_keyboard = await ShopCustomizationService.wallet_keyboard(session)
            keyboard = await _message_markup(session, "insufficient_balance", fallback_keyboard, copy_text=text)
            await _reply_shop_message(update.message, text, reply_markup=keyboard)
            return
        except PlanNotFound:
            text = await ShopCustomizationService.get_message(session, "inactive_plan")
            fallback_keyboard = await ShopCustomizationService.main_menu_keyboard(session)
            keyboard = await _message_markup(session, "inactive_plan", fallback_keyboard, copy_text=text)
            await _reply_shop_message(update.message, text, reply_markup=keyboard)
            return
        except PlanUnavailable:
            text = await ShopCustomizationService.get_message(session, "plan_unavailable", volume=0)
            fallback_keyboard = await ShopCustomizationService.main_menu_keyboard(session)
            keyboard = await _message_markup(session, "plan_unavailable", fallback_keyboard, copy_text=text)
            await _reply_shop_message(update.message, text, reply_markup=keyboard)
            return
        except PurchaseError:
            text = await ShopCustomizationService.get_message(session, "plan_sold_out", volume=0)
            fallback_keyboard = await ShopCustomizationService.main_menu_keyboard(session)
            keyboard = await _message_markup(session, "plan_sold_out", fallback_keyboard, copy_text=text)
            await _reply_shop_message(update.message, text, reply_markup=keyboard)
            return

        await _process_referral_rewards(context, update.effective_user.id)

        text = await ShopCustomizationService.get_message(
            session,
            "purchase_success",
            service_name=escape_markdown(result.purchase.service_name or f"{result.purchase.volume_gb} گیگ", version=1),
            volume=result.purchase.volume_gb,
            price=f"{result.purchase.price:,}",
            sub_link=result.sub_link,
        )
        keyboard = await ShopCustomizationService.purchase_success_reply_markup(session, result.sub_link)
        if keyboard is None:
            keyboard = await ShopCustomizationService.back_keyboard(session)
        await _reply_shop_message(update.message, text, reply_markup=keyboard)


async def help_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "help")
        fallback_keyboard = await ShopCustomizationService.back_keyboard(session)
        keyboard = await _message_markup(session, "help", fallback_keyboard, copy_text=text)
    await _reply_shop_message(update.message, text, reply_markup=keyboard)


async def support_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "support")
        fallback_keyboard = await ShopCustomizationService.back_keyboard(session)
        keyboard = await _message_markup(session, "support", fallback_keyboard, copy_text=text)
    await _reply_shop_message(update.message, text, reply_markup=keyboard)


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
        await _reply_shop_message(update.message, text, reply_markup=keyboard)
        return

    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "purchase_history_header")
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(purchase.service_name or f"{purchase.volume_gb} گیگ", callback_data=f"service:{purchase.id}")]
            for purchase in purchases
        ]
    )
    await _reply_shop_message(update.effective_message, text, reply_markup=keyboard)


async def trial_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session() as session:
        if not await SettingsService.trial_enabled(session):
            text = await ShopCustomizationService.get_message(session, "trial_disabled")
            keyboard = await ShopCustomizationService.main_menu_keyboard(session)
            await _reply_shop_message(update.effective_message, text, reply_markup=keyboard)
            return

        result = await session.execute(
            select(User)
            .where(User.telegram_id == update.effective_user.id)
            .with_for_update()
        )
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                telegram_id=update.effective_user.id,
                first_name=update.effective_user.first_name,
                username=update.effective_user.username,
            )
            session.add(user)
            await session.flush()

        if user.trial_claimed_at or user.trial_panel_username:
            text = await ShopCustomizationService.get_message(session, "trial_already_claimed")
            keyboard = await ShopCustomizationService.main_menu_keyboard(session)
            await _reply_shop_message(update.effective_message, text, reply_markup=keyboard)
            return

        volume_mb = await SettingsService.get_trial_volume_mb(session)
        duration_hours = await SettingsService.get_trial_duration_hours(session)
        try:
            trial = await MarzbanTrialService.create_or_get(
                user.telegram_id,
                volume_mb,
                duration_hours,
            )
        except MarzbanTrialError:
            await session.rollback()
            async with async_session() as error_session:
                text = await ShopCustomizationService.get_message(error_session, "trial_unavailable")
                keyboard = await ShopCustomizationService.main_menu_keyboard(error_session)
            await _reply_shop_message(update.effective_message, text, reply_markup=keyboard)
            return

        config_result = await session.execute(select(Config).where(Config.sub_link == trial.subscription_url))
        config = config_result.scalar_one_or_none()
        if not config:
            config = Config(
                volume_gb=0,
                category_key="trial",
                sub_link=trial.subscription_url,
                is_sold=True,
                sold_to_user_id=user.telegram_id,
                sold_at=datetime.now(timezone.utc),
                panel_key="alien",
                panel_username=trial.username,
                provision_source="panel",
            )
            session.add(config)
            await session.flush()
        else:
            config.is_sold = True
            config.sold_to_user_id = config.sold_to_user_id or user.telegram_id
            config.sold_at = config.sold_at or datetime.now(timezone.utc)
            config.panel_key = config.panel_key or "alien"
            config.panel_username = config.panel_username or trial.username
            config.provision_source = config.provision_source or "panel"

        purchase = Purchase(
            user_id=user.telegram_id,
            config_id=config.id,
            volume_gb=0,
            category_key="trial",
            price=0,
            original_price=0,
            discount_amount=0,
            service_name="تست رایگان",
        )
        session.add(purchase)
        user.trial_claimed_at = datetime.now(timezone.utc)
        user.trial_panel_username = trial.username
        await session.flush()
        if await SettingsService.branded_links_enabled(session):
            await SubscriptionLinkService.public_link_for_config(session, config)
            await SubscriptionLinkService.sync_to_panel(
                config,
                purchase.service_name,
                telegram_user_id=user.telegram_id,
            )
        await session.commit()

        text = await ShopCustomizationService.get_message(
            session,
            "trial_success",
            volume_mb=volume_mb,
            duration_hours=duration_hours,
        )
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("مشاهده سرویس تست", callback_data=f"service:{purchase.id}")]]
        )
    await _reply_shop_message(update.effective_message, text, reply_markup=keyboard)


def _format_service_bytes(value: int | None) -> str:
    if value is None:
        return "نامشخص"
    units = ("بایت", "کیلوبایت", "مگابایت", "گیگابایت", "ترابایت")
    size = float(max(value, 0))
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f"{size:.1f} {units[index]}"


def _format_expiry(expire: int | None) -> tuple[str, str]:
    if not expire:
        return "نامحدود", "نامحدود"
    expiry = datetime.fromtimestamp(expire, timezone.utc)
    remaining = expiry - datetime.now(timezone.utc)
    if remaining.total_seconds() <= 0:
        return expiry.strftime("%Y-%m-%d %H:%M UTC"), "منقضی شده"
    days = remaining.days
    hours = remaining.seconds // 3600
    return expiry.strftime("%Y-%m-%d %H:%M UTC"), f"{days} روز و {hours} ساعت"


async def service_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == "services:list":
        await query.answer()
        async with async_session() as session:
            result = await session.execute(
                select(Purchase)
                .where(Purchase.user_id == update.effective_user.id, Purchase.kind == "purchase")
                .order_by(Purchase.purchased_at.desc())
                .limit(10)
            )
            purchases = result.scalars().all()
            text = await ShopCustomizationService.get_message(session, "purchase_history_header")
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(purchase.service_name or f"{purchase.volume_gb} گیگ", callback_data=f"service:{purchase.id}")]
                for purchase in purchases
            ]
        )
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode=_parse_mode(text))
        return

    try:
        action, raw_purchase_id = query.data.split(":", 1)
        purchase_id = int(raw_purchase_id)
    except (AttributeError, IndexError, ValueError):
        await query.answer("سرویس نامعتبر است.", show_alert=True)
        return
    await query.answer("در حال دریافت جزئیات...")

    async with async_session() as session:
        result = await session.execute(
            select(Purchase)
            .options(selectinload(Purchase.config))
            .where(Purchase.id == purchase_id, Purchase.user_id == update.effective_user.id)
        )
        purchase = result.scalar_one_or_none()
        if not purchase:
            await query.message.reply_text("این سرویس پیدا نشد.")
            return
        if await SettingsService.branded_links_enabled(session):
            sub_link = await SubscriptionLinkService.public_link_for_config(session, purchase.config)
            token = purchase.config.public_sub_token
        else:
            sub_link = purchase.config.sub_link
            token = None
        await session.commit()

    if action == "service_qr":
        image = qrcode.make(sub_link)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        buffer.name = f"service-{purchase.id}-qr.png"
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("باز کردن لینک اشتراک", url=sub_link)],
                [InlineKeyboardButton("کپی لینک", api_kwargs={"copy_text": {"text": sub_link}})],
            ]
        )
        await query.message.reply_photo(
            photo=buffer,
            caption=f"QR Code سرویس «{purchase.service_name or f'{purchase.volume_gb} گیگ'}»",
            reply_markup=keyboard,
        )
        return

    await query.answer()
    metadata = await SubscriptionLinkService.fetch_metadata(token) if token else None
    expiry_text, remaining_time = _format_expiry(metadata.get("expire") if metadata else None)
    original_title = metadata.get("title") if metadata else "نامشخص"
    remaining_volume = _format_service_bytes(metadata.get("remaining")) if metadata else "نامشخص"
    used_volume = _format_service_bytes(metadata.get("used")) if metadata else "نامشخص"
    total_volume = (
        _format_service_bytes(metadata.get("total"))
        if metadata
        else ("نامحدود" if purchase.volume_gb <= 0 else f"{purchase.volume_gb} گیگابایت")
    )
    config_count = metadata.get("config_count", "نامشخص") if metadata else "نامشخص"
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(
            session,
            "service_details",
            escape_markdown_values=True,
            service_name=purchase.service_name or f"{purchase.volume_gb} گیگ",
            original_title=original_title,
            category_key=purchase.category_key or "default",
            total_volume=total_volume,
            used_volume=used_volume,
            remaining_volume=remaining_volume,
            expiry_text=expiry_text,
            remaining_time=remaining_time,
            config_count=config_count,
            purchased_at=purchase.purchased_at.strftime("%Y-%m-%d %H:%M"),
            price=f"{purchase.price:,}",
        )
    rows = [
        [InlineKeyboardButton("باز کردن لینک اشتراک", url=sub_link)],
        [InlineKeyboardButton("کپی لینک", api_kwargs={"copy_text": {"text": sub_link}})],
        [InlineKeyboardButton("ساخت QR Code", callback_data=f"service_qr:{purchase.id}")],
    ]
    if purchase.config and purchase.config.shop_plan_id and not purchase.config.panel_deleted_at:
        rows.append([
            InlineKeyboardButton(
                "تمدید سرویس",
                callback_data=f"renew_confirm:{purchase.id}",
                api_kwargs={
                    "style": "primary",
                    "icon_custom_emoji_id": RENEW_PREMIUM_EMOJI_ID,
                },
            )
        ])
    rows.append([InlineKeyboardButton("بازگشت به سرویس‌ها", callback_data="services:list")])
    keyboard = InlineKeyboardMarkup(rows)
    try:
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode=_parse_mode(text))
    except BadRequest as exc:
        if "parse entities" not in str(exc).lower():
            raise
        await query.edit_message_text(str(text), reply_markup=keyboard, parse_mode=None)


async def renew_service_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        action, raw_purchase_id = query.data.split(":", 1)
        purchase_id = int(raw_purchase_id)
    except (AttributeError, IndexError, ValueError):
        await query.answer("درخواست تمدید معتبر نیست.", show_alert=True)
        return

    if action == "renew_confirm":
        async with async_session() as session:
            purchase = (
                await session.execute(
                    select(Purchase)
                    .options(selectinload(Purchase.config))
                    .where(
                        Purchase.id == purchase_id,
                        Purchase.user_id == update.effective_user.id,
                        Purchase.kind == "purchase",
                    )
                )
            ).scalar_one_or_none()
            user = (
                await session.execute(select(User).where(User.telegram_id == update.effective_user.id))
            ).scalar_one_or_none()
            if not purchase or not purchase.config or not purchase.config.shop_plan_id or not user:
                await query.answer("سرویس معتبر نیست.", show_alert=True)
                return
            plan = await ShopCustomizationService.get_plan(session, purchase.config.shop_plan_id)
            if not plan or not plan.is_active or not plan.renew_enabled:
                await query.answer("تمدید برای این سرویس فعال نیست.", show_alert=True)
                return
            renew_price = await PriceService.get_plan_price(session, plan)
            if not renew_price:
                await query.answer("قیمت تمدید برای این سرویس تنظیم نشده است.", show_alert=True)
                return
            wallet_balance = user.wallet_balance or 0

        if wallet_balance < renew_price:
            await query.answer("موجودی کیف پول کافی نیست.", show_alert=True)
            text = (
                "موجودی کیف پول برای تمدید این سرویس کافی نیست.\n\n"
                f"مبلغ تمدید: {renew_price:,} تومان\n"
                f"موجودی شما: {wallet_balance:,} تومان\n"
                f"مبلغ موردنیاز برای شارژ: {max(0, renew_price - wallet_balance):,} تومان"
            )
            async with async_session() as session:
                keyboard = await ShopCustomizationService.wallet_keyboard(session)
            await query.message.reply_text(text, reply_markup=keyboard)
            return

        await query.answer()
        text = (
            "تمدید این سرویس مثل خرید سرویس جدید از کیف پول شما پرداخت می‌شود.\n\n"
            "با تایید تمدید، حجم سرویس ریست می‌شود و تاریخ اعتبار از ابتدا طبق مدت همین سرویس محاسبه می‌شود.\n\n"
            f"مبلغ تمدید: {renew_price:,} تومان\n"
            f"موجودی شما: {wallet_balance:,} تومان\n\n"
            "آیا تمدید را تایید می‌کنید؟"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "تایید تمدید",
                        callback_data=f"renew_do:{purchase_id}",
                        api_kwargs={
                            "style": "primary",
                            "icon_custom_emoji_id": RENEW_PREMIUM_EMOJI_ID,
                        },
                    )
                ],
                [InlineKeyboardButton("انصراف", callback_data=f"service:{purchase_id}")],
            ]
        )
        await query.edit_message_text(text, reply_markup=keyboard)
        return

    await query.answer("در حال تمدید...")
    async with async_session() as session:
        try:
            result = await renew_purchase(
                session,
                telegram_id=update.effective_user.id,
                purchase_id=purchase_id,
                source_label="bot",
            )
        except InsufficientBalance:
            text = await ShopCustomizationService.get_message(session, "insufficient_balance", required_price="موردنیاز")
            keyboard = await ShopCustomizationService.wallet_keyboard(session)
            await _reply_shop_message(query.message, text, reply_markup=keyboard)
            return
        except PurchaseError as exc:
            await query.message.reply_text(f"تمدید انجام نشد:\n{exc}")
            return

    await query.message.reply_text(
        f"تمدید با موفقیت انجام شد.\n"
        f"مبلغ تمدید از کیف پول شما کسر شد.\n"
        f"حجم سرویس ریست شد و اعتبار آن دوباره از ابتدا محاسبه شد.\n\n{result.sub_link}"
    )


async def cancel_coupon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("awaiting_coupon_code", None)
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "coupon_cancelled")
        fallback_keyboard = await ShopCustomizationService.wallet_keyboard(session)
        keyboard = await _message_markup(session, "coupon_cancelled", fallback_keyboard, copy_text=text)
    await _reply_shop_message(update.message, text, reply_markup=keyboard)


async def ask_service_name(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_id: int):
    context.user_data["awaiting_service_name"] = True
    context.user_data["pending_purchase_plan_id"] = plan_id
    async with async_session() as session:
        text = await ShopCustomizationService.get_message(session, "service_name_prompt")
        fallback_keyboard = await ShopCustomizationService.back_keyboard(session)
        keyboard = await _message_markup(session, "service_name_prompt", fallback_keyboard, copy_text=text)
    await _reply_shop_message(update.message, text, reply_markup=keyboard)


async def receive_service_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service_name = update.message.text.strip()
    if not service_name or len(service_name) > 60:
        async with async_session() as session:
            text = await ShopCustomizationService.get_message(session, "service_name_invalid")
            fallback_keyboard = await ShopCustomizationService.back_keyboard(session)
            keyboard = await _message_markup(session, "service_name_invalid", fallback_keyboard, copy_text=text)
        await _reply_shop_message(update.message, text, reply_markup=keyboard)
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
    await _reply_shop_message(update.effective_message, text, reply_markup=keyboard)


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
    await _process_referral_rewards(context, update.effective_user.id)
    await _reply_shop_message(update.message, text)
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
        selected_duration = ShopCustomizationService.duration_key_for_text(selected_category, text)
        plan_id = await ShopCustomizationService.plan_for_text(session, text, discounted_prices, selected_category)

    if context.user_data.get(rial_user.STEP_KEY):
        await rial_user.handle_text(update, context)
        return

    if context.user_data.get(crypto_user.STEP_KEY):
        await crypto_user.handle_step(update, context)
        return

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

    if selected_duration:
        context.user_data["selected_plan_duration"] = selected_duration
        await buy_category_plans_menu(update, context, selected_category)
        return

    if plan_id is not None:
        await ask_service_name(update, context, plan_id)
        return

    await _dispatch_shop_action(update, context, action)


async def _dispatch_shop_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str | None):
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
    elif action == "charge_crypto":
        await crypto_user.charge_start(update, context)
    elif action == "charge_rial":
        await rial_user.charge_start(update, context)
    elif action == "trial_config":
        await trial_config(update, context)
    elif action and action.startswith("custom_message:"):
        async with async_session() as session:
            message = await ShopCustomizationService.get_message(session, action)
            fallback_keyboard = await ShopCustomizationService.main_menu_keyboard(session)
            keyboard = await _message_markup(session, action, fallback_keyboard, copy_text=message)
        await _reply_shop_message(update.message, message, reply_markup=keyboard)
    else:
        await main_menu(update, context)


async def response_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        message_id = int(query.data.split(":", 1)[1])
    except (AttributeError, IndexError, ValueError):
        await query.answer("دکمه معتبر نیست.", show_alert=True)
        return

    async with async_session() as session:
        action = await ShopCustomizationService.response_button_action(session, message_id)
    if not action:
        await query.answer("این دکمه غیرفعال یا حذف شده است.", show_alert=True)
        return

    await query.answer()
    callback_update = SimpleNamespace(
        message=query.message,
        effective_message=query.message,
        effective_user=query.from_user,
        callback_query=query,
    )
    await _dispatch_shop_action(callback_update, context, action)


user_handlers = [
    CommandHandler("start", start),
    CommandHandler("app", open_webapp),
    CommandHandler("verifyphone", rial_user.verify_phone_start),
    CommandHandler("buy", buy_menu),
    CommandHandler("wallet", wallet_menu),
    CommandHandler("charge", crypto_user.charge_start),
    CommandHandler("rial", rial_user.charge_start),
    CommandHandler("referrals", referral_menu),
    CommandHandler("account", account_info_menu),
    CommandHandler("help", help_menu),
    CommandHandler("support", support_menu),
    CommandHandler("cancel", cancel_coupon),
    CallbackQueryHandler(response_button_callback, pattern=r"^shop_response:\d+$"),
    CallbackQueryHandler(service_details_callback, pattern=r"^(service:\d+|service_qr:\d+|services:list)$"),
    CallbackQueryHandler(renew_service_callback, pattern=r"^renew_(confirm|do):\d+$"),
    MessageHandler(filters.CONTACT, rial_user.handle_contact),
    MessageHandler(filters.TEXT & ~filters.COMMAND, shop_text_router),
]
