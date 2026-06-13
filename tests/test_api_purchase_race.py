"""Two buyers, one config: exactly one purchase must succeed."""

import asyncio
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
import pytest_asyncio

from tests import _api_test_env  # noqa: F401  (must precede api/bot imports)

import httpx  # noqa: E402
from sqlalchemy import select  # noqa: E402

from webapi.main import app  # noqa: E402
from bot_package.config_loader import BotConfig  # noqa: E402
from bot_package.database import async_session  # noqa: E402
from bot_package.models import Config, Purchase, ShopPlan, User  # noqa: E402


def make_init_data(telegram_id: int) -> str:
    payload = {
        "user": json.dumps({"id": telegram_id, "first_name": f"u{telegram_id}", "username": None}),
        "auth_date": str(int(time.time())),
        "query_id": f"AAE-{telegram_id}",
    }
    data_check_string = "\n".join(f"{k}={payload[k]}" for k in sorted(payload))
    secret_key = hmac.new(b"WebAppData", BotConfig.MAIN_BOT_TOKEN.encode(), hashlib.sha256).digest()
    payload["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(payload)


@pytest_asyncio.fixture()
async def client():
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest.mark.asyncio
async def test_concurrent_purchase_of_last_config(client):
    # Seed: one plan, ONE unsold config, two rich users.
    async with async_session() as session:
        plan = ShopPlan(volume_gb=10, category_key="default", title="ده گیگ", price=100_000)
        session.add(plan)
        session.add(
            Config(volume_gb=10, category_key="default", sub_link="https://x.example/only-one")
        )
        for telegram_id in (501, 502):
            session.add(
                User(telegram_id=telegram_id, first_name=f"u{telegram_id}", wallet_balance=1_000_000)
            )
        await session.flush()
        plan_id = plan.id
        await session.commit()

    tokens = {}
    for telegram_id in (501, 502):
        response = await client.post(
            "/api/v1/auth/telegram", json={"init_data": make_init_data(telegram_id)}
        )
        assert response.status_code == 200
        tokens[telegram_id] = response.json()["access_token"]

    async def buy(telegram_id: int):
        return await client.post(
            "/api/v1/shop/purchases",
            json={"plan_id": plan_id},
            headers={
                "Authorization": f"Bearer {tokens[telegram_id]}",
                "Idempotency-Key": f"race-{telegram_id}",
            },
        )

    results = await asyncio.gather(buy(501), buy(502))
    statuses = sorted(r.status_code for r in results)
    assert statuses == [200, 409], [r.text for r in results]

    async with async_session() as session:
        purchases = (await session.execute(select(Purchase))).scalars().all()
        assert len(purchases) == 1
        config = (await session.execute(select(Config))).scalar_one()
        assert config.is_sold is True
        assert config.sold_to_user_id == purchases[0].user_id
        # Loser keeps their money.
        loser_id = 501 if purchases[0].user_id == 502 else 502
        loser = (
            await session.execute(select(User).where(User.telegram_id == loser_id))
        ).scalar_one()
        assert loser.wallet_balance == 1_000_000


@pytest.mark.asyncio
async def test_idempotency_key_prevents_double_purchase(client):
    async with async_session() as session:
        plan = ShopPlan(volume_gb=5, category_key="default", title="پنج گیگ", price=50_000)
        session.add(plan)
        for i in range(2):
            session.add(
                Config(volume_gb=5, category_key="default", sub_link=f"https://x.example/idem-{i}")
            )
        session.add(User(telegram_id=601, first_name="u601", wallet_balance=1_000_000))
        await session.flush()
        plan_id = plan.id
        await session.commit()

    response = await client.post(
        "/api/v1/auth/telegram", json={"init_data": make_init_data(601)}
    )
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "same-key"}

    first = await client.post("/api/v1/shop/purchases", json={"plan_id": plan_id}, headers=headers)
    second = await client.post("/api/v1/shop/purchases", json={"plan_id": plan_id}, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    async with async_session() as session:
        user = (
            await session.execute(select(User).where(User.telegram_id == 601))
        ).scalar_one()
        assert user.wallet_balance == 950_000  # charged exactly once
