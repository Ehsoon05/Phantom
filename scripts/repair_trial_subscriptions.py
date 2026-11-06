from __future__ import annotations

import asyncio

from sqlalchemy import select

from bot_package.database import async_session
from bot_package.models import Config, Purchase, User
from bot_package.services.marzban_trial_service import MarzbanTrialService
from bot_package.services.settings_service import SettingsService
from bot_package.services.subscription_link_service import SubscriptionLinkService


async def repair_trial_subscriptions() -> None:
    repaired: list[tuple[Config, str]] = []
    async with async_session() as session:
        volume_mb = await SettingsService.get_trial_volume_mb(session)
        duration_hours = await SettingsService.get_trial_duration_hours(session)
        result = await session.execute(
            select(User).where(User.trial_panel_username.is_not(None))
        )

        for user in result.scalars():
            trial = await MarzbanTrialService.create_or_get(
                user.telegram_id,
                volume_mb,
                duration_hours,
            )
            config_result = await session.execute(
                select(Config).where(
                    Config.category_key == "trial",
                    Config.sold_to_user_id == user.telegram_id,
                )
            )
            config = config_result.scalar_one_or_none()
            if config is None:
                continue

            purchase_result = await session.execute(
                select(Purchase).where(Purchase.config_id == config.id)
            )
            purchase = purchase_result.scalar_one_or_none()
            config.sub_link = trial.subscription_url
            await SubscriptionLinkService.public_link_for_config(session, config)
            repaired.append((config, purchase.service_name if purchase else "تست رایگان"))

        await session.commit()

    for config, service_name in repaired:
        await SubscriptionLinkService.sync_to_panel(config, service_name)
        print(f"repaired trial config {config.id} for user {config.sold_to_user_id}")


if __name__ == "__main__":
    asyncio.run(repair_trial_subscriptions())
