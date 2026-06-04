from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from string import Formatter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import KeyboardButton, ReplyKeyboardMarkup

from ..models import Price, ShopButton, ShopMessage, ShopPlan
from ..utils import messages as default_messages
from ..utils.keyboards import (
    ACCOUNT_INFO,
    APPLY_COUPON,
    BACK_TO_MAIN,
    BUY_SUBSCRIPTION,
    HELP,
    PURCHASE_HISTORY,
    REFERRALS,
    SUPPORT,
    WALLET,
    STYLE_DANGER,
    STYLE_PRIMARY,
    STYLE_SUCCESS,
    SHOP_BUTTON_CUSTOM_EMOJI_ID,
)


PARSE_MODE_MARKDOWN = "Markdown"


@dataclass(frozen=True)
class ButtonDefinition:
    action: str
    menu: str
    text: str
    emoji: str | None
    style: str | None
    row: int
    col: int
    premium_emoji_id: str | None = None


@dataclass(frozen=True)
class PlanDefinition:
    volume_gb: int
    title: str
    emoji: str | None
    style: str | None
    display_order: int
    premium_emoji_id: str | None = None


def _split_label(label: str) -> tuple[str | None, str]:
    parts = label.split(" ", 1)
    if len(parts) == 2 and len(parts[0]) <= 4:
        return parts[0], parts[1]
    return None, label


def _button_default(action: str, menu: str, label: str, style: str, row: int, col: int) -> ButtonDefinition:
    emoji, text = _split_label(label)
    return ButtonDefinition(
        action=action,
        menu=menu,
        text=text,
        emoji=emoji,
        style=style,
        row=row,
        col=col,
        premium_emoji_id=SHOP_BUTTON_CUSTOM_EMOJI_ID if menu.startswith("shop") else None,
    )


DEFAULT_BUTTONS: tuple[ButtonDefinition, ...] = (
    _button_default("buy_subscription", "shop_main", BUY_SUBSCRIPTION, STYLE_SUCCESS, 0, 0),
    _button_default("wallet", "shop_main", WALLET, STYLE_PRIMARY, 1, 0),
    _button_default("purchase_history", "shop_main", PURCHASE_HISTORY, STYLE_PRIMARY, 1, 1),
    _button_default("referrals", "shop_main", REFERRALS, STYLE_SUCCESS, 2, 0),
    _button_default("account_info", "shop_main", ACCOUNT_INFO, STYLE_PRIMARY, 2, 1),
    _button_default("support", "shop_main", SUPPORT, STYLE_PRIMARY, 3, 0),
    _button_default("help", "shop_main", HELP, STYLE_PRIMARY, 3, 1),
    _button_default("apply_coupon", "shop_wallet", APPLY_COUPON, STYLE_SUCCESS, 0, 0),
    _button_default("referrals", "shop_wallet", REFERRALS, STYLE_PRIMARY, 0, 1),
    _button_default("support", "shop_wallet", SUPPORT, STYLE_SUCCESS, 1, 0),
    _button_default("back_to_main", "shop_wallet", BACK_TO_MAIN, STYLE_DANGER, 2, 0),
    _button_default("back_to_main", "shop_back", BACK_TO_MAIN, STYLE_DANGER, 0, 0),
    _button_default("back_to_main", "shop_buy", BACK_TO_MAIN, STYLE_DANGER, 99, 0),
)


DEFAULT_MESSAGES: dict[str, str] = {
    "main_menu": default_messages.MAIN_MENU_TEXT,
    "buy_menu": default_messages.BUY_MENU_TEXT,
    "wallet": (
        "**کیف پول شما**\n\n"
        "موجودی فعلی: **{wallet_balance} تومان**\n\n"
        "برای شارژ کیف پول، به پشتیبانی پیام بدهید:\n"
        "{support_handle}"
    ),
    "purchase_success": (
        "**خرید با موفقیت انجام شد**\n\n"
        "حجم سرویس: **{volume} گیگ**\n"
        "مبلغ پرداختی: **{price} تومان**\n\n"
        "لینک اشتراک شما:\n"
        "`{sub_link}`\n\n"
        "لطفا این لینک را فقط برای خودتان نگه دارید."
    ),
    "support": default_messages.SUPPORT_TEXT,
    "help": default_messages.HELP_TEXT,
    "no_purchase": default_messages.NO_PURCHASE,
    "purchase_history_header": "**آخرین خریدهای شما**\n\n",
    "invalid_plan": "پلن انتخاب‌شده معتبر نیست. لطفا دوباره از منوی خرید انتخاب کنید.",
    "blocked_user": "حساب شما مسدود شده است.",
    "inactive_plan": "این پلن در حال حاضر فعال نیست.",
    "insufficient_balance": "موجودی کیف پول کافی نیست.\nمبلغ موردنیاز: {required_price} تومان",
    "plan_unavailable": "پلن {volume} گیگ فعلا ناموجود است.",
    "plan_sold_out": "پلن {volume} گیگ همین الان ناموجود شد. لطفا دوباره تلاش کنید.",
    "coupon_prompt": "کد تخفیف را ارسال کنید.",
    "coupon_invalid": "این کد تخفیف معتبر نیست یا برای حساب شما فعال نشده است.",
    "coupon_applied": (
        "کد تخفیف **{code}** با مقدار **{discount_text}** فعال شد.\n"
        "قیمت‌ها در منوی خرید با تخفیف نمایش داده می‌شوند."
    ),
    "coupon_cancelled": "عملیات لغو شد.",
    "referral_followup": "از منوی پایین می‌توانید به بخش‌های دیگر بروید.",
    "referral": (
        "**دعوت دوستان**\n\n"
        "لینک اختصاصی شما آماده است. هر کسی با این لینک وارد ربات شود به عنوان دعوت‌شده شما ثبت می‌شود.\n\n"
        "لینک قابل کلیک:\n[دعوت به فانتوم VPN]({link})\n\n"
        "لینک مستقیم:\n`{link}`\n\n"
        "تعداد ثبت‌نام با لینک شما: **{count} نفر**"
    ),
    "account_info": (
        "**اطلاعات حساب**\n\n"
        "آیدی عددی: `{telegram_id}`\n"
        "نام: {first_name}\n"
        "یوزرنیم: {username}\n"
        "موجودی کیف پول: **{wallet_balance} تومان**\n\n"
        "تعداد خریدها: **{total_count}**\n"
        "حجم خریداری‌شده: **{total_gb} گیگ**\n"
        "مبلغ کل خریدها: **{total_spent} تومان**\n"
        "ثبت‌نام با لینک دعوت شما: **{referral_count} نفر**"
    ),
    "purchase_history_item": (
        "حجم: {volume} گیگ | مبلغ: {price} تومان{discount}{coupon}\n"
        "زمان: {purchased_at}\n"
        "`{sub_link}`\n\n"
    ),
}


DEFAULT_PLANS: tuple[PlanDefinition, ...] = (
    PlanDefinition(1, "1 گیگ", "📦", STYLE_SUCCESS, 0, SHOP_BUTTON_CUSTOM_EMOJI_ID),
    PlanDefinition(2, "2 گیگ", "📦", STYLE_SUCCESS, 1, SHOP_BUTTON_CUSTOM_EMOJI_ID),
    PlanDefinition(3, "3 گیگ", "📦", STYLE_SUCCESS, 2, SHOP_BUTTON_CUSTOM_EMOJI_ID),
    PlanDefinition(5, "5 گیگ", "📦", STYLE_SUCCESS, 3, SHOP_BUTTON_CUSTOM_EMOJI_ID),
    PlanDefinition(10, "10 گیگ", "📦", STYLE_SUCCESS, 4, SHOP_BUTTON_CUSTOM_EMOJI_ID),
    PlanDefinition(20, "20 گیگ", "📦", STYLE_SUCCESS, 5, SHOP_BUTTON_CUSTOM_EMOJI_ID),
)


class ShopCustomizationService:
    @staticmethod
    async def init_defaults(session: AsyncSession) -> None:
        for key, text in DEFAULT_MESSAGES.items():
            result = await session.execute(select(ShopMessage).where(ShopMessage.key == key))
            if result.scalar_one_or_none() is None:
                session.add(ShopMessage(key=key, text=text, parse_mode=PARSE_MODE_MARKDOWN))

        for definition in DEFAULT_BUTTONS:
            result = await session.execute(select(ShopButton).where(ShopButton.action == definition.action, ShopButton.menu == definition.menu))
            if result.scalar_one_or_none() is None:
                session.add(
                    ShopButton(
                        action=definition.action,
                        menu=definition.menu,
                        text=definition.text,
                        emoji=definition.emoji,
                        premium_emoji_id=definition.premium_emoji_id,
                        style=definition.style,
                        row=definition.row,
                        col=definition.col,
                    )
                )

        for definition in DEFAULT_PLANS:
            result = await session.execute(select(ShopPlan).where(ShopPlan.volume_gb == definition.volume_gb))
            if result.scalar_one_or_none() is None:
                session.add(
                    ShopPlan(
                        volume_gb=definition.volume_gb,
                        title=definition.title,
                        emoji=definition.emoji,
                        premium_emoji_id=definition.premium_emoji_id,
                        style=definition.style,
                        display_order=definition.display_order,
                    )
                )
        await session.commit()

    @staticmethod
    async def reset_defaults(session: AsyncSession) -> None:
        messages = await session.execute(select(ShopMessage))
        for message in messages.scalars().all():
            await session.delete(message)

        buttons = await session.execute(select(ShopButton))
        for button in buttons.scalars().all():
            await session.delete(button)

        plans = await session.execute(select(ShopPlan))
        for plan in plans.scalars().all():
            await session.delete(plan)

        await session.flush()
        await ShopCustomizationService.init_defaults(session)

    @staticmethod
    async def list_messages(session: AsyncSession) -> list[ShopMessage]:
        result = await session.execute(select(ShopMessage).order_by(ShopMessage.key))
        return list(result.scalars().all())

    @staticmethod
    async def get_message_row(session: AsyncSession, key: str) -> ShopMessage | None:
        result = await session.execute(select(ShopMessage).where(ShopMessage.key == key))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_message(session: AsyncSession, key: str, text: str) -> ShopMessage | None:
        message = await ShopCustomizationService.get_message_row(session, key)
        if not message:
            return None
        message.text = text
        message.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return message

    @staticmethod
    async def list_buttons(session: AsyncSession, menu: str | None = None) -> list[ShopButton]:
        stmt = select(ShopButton)
        if menu:
            stmt = stmt.where(ShopButton.menu == menu)
        result = await session.execute(stmt.order_by(ShopButton.menu, ShopButton.row, ShopButton.col, ShopButton.id))
        return list(result.scalars().all())

    @staticmethod
    async def get_button(session: AsyncSession, button_id: int) -> ShopButton | None:
        result = await session.execute(select(ShopButton).where(ShopButton.id == button_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_button(session: AsyncSession, button_id: int, **values) -> ShopButton | None:
        button = await ShopCustomizationService.get_button(session, button_id)
        if not button:
            return None

        allowed = {"text", "emoji", "premium_emoji_id", "style", "row", "col", "is_enabled"}
        for key, value in values.items():
            if key in allowed:
                setattr(button, key, value)
        button.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return button

    @staticmethod
    async def create_custom_button(session: AsyncSession, menu: str, text: str, message_text: str) -> ShopButton:
        buttons = await ShopCustomizationService.list_buttons(session, menu)
        row = max((button.row for button in buttons), default=-1) + 1
        action = f"custom_message:{menu}:{int(datetime.now(timezone.utc).timestamp())}"
        message = ShopMessage(key=action, text=message_text, parse_mode=PARSE_MODE_MARKDOWN)
        button = ShopButton(
            action=action,
            menu=menu,
            text=text,
            emoji="✨",
            premium_emoji_id=SHOP_BUTTON_CUSTOM_EMOJI_ID,
            style=STYLE_PRIMARY,
            row=row,
            col=0,
            is_enabled=True,
        )
        session.add(message)
        session.add(button)
        await session.commit()
        return button

    @staticmethod
    async def list_plans(session: AsyncSession) -> list[ShopPlan]:
        result = await session.execute(select(ShopPlan).order_by(ShopPlan.display_order, ShopPlan.volume_gb))
        return list(result.scalars().all())

    @staticmethod
    async def get_plan(session: AsyncSession, volume_gb: int) -> ShopPlan | None:
        result = await session.execute(select(ShopPlan).where(ShopPlan.volume_gb == volume_gb))
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert_plan(
        session: AsyncSession,
        *,
        volume_gb: int,
        title: str,
        price: int | None = None,
        emoji: str | None = "📦",
        style: str | None = STYLE_SUCCESS,
    ) -> ShopPlan:
        plan = await ShopCustomizationService.get_plan(session, volume_gb)
        if not plan:
            current = await ShopCustomizationService.list_plans(session)
            plan = ShopPlan(
                volume_gb=volume_gb,
                title=title,
                emoji=emoji,
                premium_emoji_id=SHOP_BUTTON_CUSTOM_EMOJI_ID,
                style=style,
                display_order=len(current),
                is_active=True,
            )
            session.add(plan)
        else:
            plan.title = title
            plan.emoji = emoji
            plan.style = style
            plan.is_active = True
            plan.updated_at = datetime.now(timezone.utc)

        if price is not None:
            price_result = await session.execute(select(Price).where(Price.volume_gb == volume_gb))
            price_row = price_result.scalar_one_or_none()
            if price_row:
                price_row.price = price
                price_row.updated_at = datetime.now(timezone.utc)
            else:
                session.add(Price(volume_gb=volume_gb, price=price))

        await session.commit()
        return plan

    @staticmethod
    async def update_plan(session: AsyncSession, volume_gb: int, **values) -> ShopPlan | None:
        plan = await ShopCustomizationService.get_plan(session, volume_gb)
        if not plan:
            return None

        allowed = {"title", "emoji", "premium_emoji_id", "style", "display_order", "is_active"}
        for key, value in values.items():
            if key in allowed:
                setattr(plan, key, value)
        plan.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return plan

    @staticmethod
    async def get_message(session: AsyncSession, key: str, **values) -> str:
        result = await session.execute(
            select(ShopMessage).where(ShopMessage.key == key, ShopMessage.is_active == True)
        )
        message = result.scalar_one_or_none()
        template = message.text if message else DEFAULT_MESSAGES[key]
        if not values:
            return template
        return _safe_format(template, values)

    @staticmethod
    async def main_menu_keyboard(session: AsyncSession) -> ReplyKeyboardMarkup:
        return await ShopCustomizationService._menu_keyboard(session, "shop_main")

    @staticmethod
    async def wallet_keyboard(session: AsyncSession) -> ReplyKeyboardMarkup:
        return await ShopCustomizationService._menu_keyboard(session, "shop_wallet")

    @staticmethod
    async def back_keyboard(session: AsyncSession) -> ReplyKeyboardMarkup:
        return await ShopCustomizationService._menu_keyboard(session, "shop_back")

    @staticmethod
    async def buy_volume_keyboard(session: AsyncSession, prices: dict | None = None) -> ReplyKeyboardMarkup:
        if not prices:
            prices = {1: 15000, 2: 28000, 3: 40000, 5: 65000, 10: 120000, 20: 220000}

        plans = await ShopCustomizationService.get_active_plans(session)
        rows: dict[int, list[KeyboardButton]] = {}
        for index, plan in enumerate(plans):
            if plan.volume_gb not in prices:
                continue
            row = index // 2
            rows.setdefault(row, []).append(ShopCustomizationService._keyboard_button(
                ShopCustomizationService.plan_label(plan, prices[plan.volume_gb]),
                style=plan.style,
                premium_emoji_id=plan.premium_emoji_id,
            ))

        back_buttons = await ShopCustomizationService._buttons_for_menu(session, "shop_buy")
        if back_buttons:
            rows[max(rows.keys(), default=-1) + 1] = [ShopCustomizationService._button_from_model(button) for button in back_buttons]

        return _reply_keyboard([rows[key] for key in sorted(rows)])

    @staticmethod
    async def action_for_text(session: AsyncSession, text: str) -> str | None:
        result = await session.execute(
            select(ShopButton).where(ShopButton.is_enabled == True)
        )
        for button in result.scalars().all():
            if ShopCustomizationService.button_label(button) == text:
                return button.action

        for definition in DEFAULT_BUTTONS:
            label = ShopCustomizationService.definition_label(definition)
            if label == text:
                return definition.action
        return None

    @staticmethod
    async def volume_for_text(session: AsyncSession, text: str, prices: dict) -> int | None:
        plans = await ShopCustomizationService.get_active_plans(session)
        for plan in plans:
            price = prices.get(plan.volume_gb)
            if price is None:
                continue
            if ShopCustomizationService.plan_label(plan, price) == text:
                return plan.volume_gb
        return None

    @staticmethod
    async def get_active_plans(session: AsyncSession) -> list[ShopPlan]:
        result = await session.execute(
            select(ShopPlan).where(ShopPlan.is_active == True).order_by(ShopPlan.display_order, ShopPlan.volume_gb)
        )
        plans = list(result.scalars().all())
        if plans:
            return plans

        prices_result = await session.execute(select(Price).order_by(Price.volume_gb))
        volumes = [price.volume_gb for price in prices_result.scalars().all()]
        if not volumes:
            volumes = [definition.volume_gb for definition in DEFAULT_PLANS]

        defaults = {definition.volume_gb: definition for definition in DEFAULT_PLANS}
        return [
            ShopPlan(
                volume_gb=volume,
                title=defaults.get(volume, PlanDefinition(volume, f"{volume} گیگ", "📦", STYLE_SUCCESS, volume)).title,
                emoji=defaults.get(volume, PlanDefinition(volume, f"{volume} گیگ", "📦", STYLE_SUCCESS, volume)).emoji,
                premium_emoji_id=SHOP_BUTTON_CUSTOM_EMOJI_ID,
                style=STYLE_SUCCESS,
                display_order=index,
            )
            for index, volume in enumerate(volumes)
        ]

    @staticmethod
    async def _menu_keyboard(session: AsyncSession, menu: str) -> ReplyKeyboardMarkup:
        buttons = await ShopCustomizationService._buttons_for_menu(session, menu)
        if not buttons:
            buttons = ShopCustomizationService._default_buttons_for_menu(menu)

        rows: dict[int, list[ShopButton | ButtonDefinition]] = {}
        for button in buttons:
            rows.setdefault(button.row, []).append(button)

        keyboard_rows = []
        for row_index in sorted(rows):
            keyboard_rows.append([
                ShopCustomizationService._button_from_any(button)
                for button in sorted(rows[row_index], key=lambda item: item.col)
            ])
        return _reply_keyboard(keyboard_rows)

    @staticmethod
    async def _buttons_for_menu(session: AsyncSession, menu: str) -> list[ShopButton]:
        result = await session.execute(
            select(ShopButton)
            .where(ShopButton.menu == menu, ShopButton.is_enabled == True)
            .order_by(ShopButton.row, ShopButton.col)
        )
        return list(result.scalars().all())

    @staticmethod
    def _default_buttons_for_menu(menu: str) -> list[ButtonDefinition]:
        return [definition for definition in DEFAULT_BUTTONS if definition.menu == menu]

    @staticmethod
    def _button_from_any(button: ShopButton | ButtonDefinition) -> KeyboardButton:
        if isinstance(button, ShopButton):
            return ShopCustomizationService._button_from_model(button)
        return ShopCustomizationService._keyboard_button(
            ShopCustomizationService.definition_label(button),
            style=button.style,
            premium_emoji_id=button.premium_emoji_id,
        )

    @staticmethod
    def _button_from_model(button: ShopButton) -> KeyboardButton:
        return ShopCustomizationService._keyboard_button(
            ShopCustomizationService.button_label(button),
            style=button.style,
            premium_emoji_id=button.premium_emoji_id,
        )

    @staticmethod
    def _keyboard_button(text: str, *, style: str | None = None, premium_emoji_id: str | None = None) -> KeyboardButton:
        api_kwargs = {}
        if style:
            api_kwargs["style"] = style
        if _is_valid_custom_emoji_id(premium_emoji_id):
            api_kwargs["icon_custom_emoji_id"] = str(premium_emoji_id).strip()
        try:
            return KeyboardButton(text=text, api_kwargs=api_kwargs or None)
        except TypeError:
            return KeyboardButton(text=text)

    @staticmethod
    def button_label(button: ShopButton) -> str:
        return _join_emoji(button.emoji, button.text)

    @staticmethod
    def definition_label(definition: ButtonDefinition) -> str:
        return _join_emoji(definition.emoji, definition.text)

    @staticmethod
    def plan_label(plan: ShopPlan, price_value) -> str:
        if isinstance(price_value, tuple):
            final_price, discount = price_value
            label = f"{_join_emoji(plan.emoji, plan.title)} | {final_price:,} تومان"
            if discount:
                label += f" | تخفیف {discount:,}"
            return label
        return f"{_join_emoji(plan.emoji, plan.title)} | {price_value:,} تومان"


def _reply_keyboard(rows: list[list[KeyboardButton]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        input_field_placeholder="یکی از گزینه‌ها را انتخاب کنید",
    )


def _join_emoji(emoji: str | None, text: str) -> str:
    if emoji:
        return f"{emoji} {text}"
    return text


def _is_valid_custom_emoji_id(value: str | None) -> bool:
    if value is None:
        return False
    value = str(value).strip()
    return bool(value and value.isdigit())


def _safe_format(template: str, values: dict) -> str:
    allowed_keys = {field_name for _, field_name, _, _ in Formatter().parse(template) if field_name}
    safe_values = {key: values.get(key, "{" + key + "}") for key in allowed_keys}
    return template.format(**safe_values)
