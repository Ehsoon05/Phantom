"""End-to-end smoke tests for the FastAPI layer (in-process, ASGI transport)."""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
import pytest_asyncio

from tests import _api_test_env  # noqa: F401  (must precede api/bot imports)

import httpx  # noqa: E402

from webapi.main import app  # noqa: E402
from bot_package.config_loader import BotConfig  # noqa: E402


def make_init_data(telegram_id: int = 777, first_name: str = "Tester") -> str:
    payload = {
        "user": json.dumps({"id": telegram_id, "first_name": first_name, "username": "tester"}),
        "auth_date": str(int(time.time())),
        "query_id": "AAE-test",
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
async def test_healthz(client):
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_auth_rejects_bad_signature(client):
    response = await client.post(
        "/api/v1/auth/telegram", json={"init_data": "user=x&auth_date=1&hash=deadbeef"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_and_shop_flow(client):
    response = await client.post("/api/v1/auth/telegram", json={"init_data": make_init_data()})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    body = me.json()
    assert body["telegram_id"] == 777
    assert body["wallet_balance"] == 0
    assert body["referral_code"]

    plans = await client.get("/api/v1/shop/plans", headers=headers)
    assert plans.status_code == 200
    assert isinstance(plans.json(), list)

    purchases = await client.get("/api/v1/shop/purchases", headers=headers)
    assert purchases.status_code == 200
    assert purchases.json() == []


@pytest.mark.asyncio
async def test_endpoints_require_auth(client):
    for path in ("/api/v1/auth/me", "/api/v1/shop/plans", "/api/v1/wallet/transactions"):
        response = await client.get(path)
        assert response.status_code == 401, path


@pytest.mark.asyncio
async def test_admin_login_rejects_wrong_password(client):
    response = await client.post(
        "/api/v1/admin/auth/login", json={"telegram_id": 1, "password": "wrong"}
    )
    assert response.status_code == 401
