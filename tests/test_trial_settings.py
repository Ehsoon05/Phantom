import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot_package.models import Base, BotSetting
from bot_package.services.settings_service import (
    TRIAL_PANEL_KEY,
    SettingsService,
)


async def _new_session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def test_trial_panel_defaults_to_phantom_tunnel():
    async def run():
        engine, sessions = await _new_session_factory()
        try:
            async with sessions() as session:
                await SettingsService.init_defaults(session)
                assert await SettingsService.get_trial_panel_key(session) == "phantom_tunnel"
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_trial_panel_migration_runs_only_once():
    async def run():
        engine, sessions = await _new_session_factory()
        try:
            async with sessions() as session:
                session.add(BotSetting(key=TRIAL_PANEL_KEY, value="easy"))
                await session.commit()
                await SettingsService.init_defaults(session)
                assert await SettingsService.get_trial_panel_key(session) == "phantom_tunnel"

                await SettingsService.set_trial_panel_key(session, "easy")
                await SettingsService.init_defaults(session)
                value = (
                    await session.execute(select(BotSetting.value).where(BotSetting.key == TRIAL_PANEL_KEY))
                ).scalar_one()
                assert value == "easy"
        finally:
            await engine.dispose()

    asyncio.run(run())
