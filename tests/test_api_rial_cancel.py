"""Rial pending list + cancel, and admin config name parsing/search."""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
import pytest_asyncio

from tests import _api_test_env  # noqa: F401  (must precede api/bot imports)

import httpx  # noqa: E402

from bot_package.config_loader import BotConfig  # noqa: E402
from bot_package.database import async_session  # noqa: E402
from bot_package.services.settings_service import SettingsService  # noqa: E402
from webapi.main import app  # noqa: E402
from webapi.routers.admin_catalog import _config_name  # noqa: E402


def make_init_data(telegram_id: int) -> str:
    payload = {
        "user": json.dumps({"id": telegram_id, "first_name": f"u{telegram_id}", "username": None}),
        "auth_date": str(int(time.time())),
        "query_id": f"AAE-{telegram_id}",
    }
    dcs = "\n".join(f"{k}={payload[k]}" for k in sorted(payload))
    secret = hmac.new(b"WebAppData", BotConfig.MAIN_BOT_TOKEN.encode(), hashlib.sha256).digest()
    payload["hash"] = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    return urlencode(payload)


@pytest_asyncio.fixture()
async def client():
    async with app.router.lifespan_context(app):
        async with async_session() as session:
            await SettingsService.set_rial_phone_required(session, False)
            await session.commit()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


def test_config_name_parses_fragment():
    assert _config_name("https://panel.example.com/sub/tok123#My%20Service") == "My Service"
    assert _config_name("https://panel.example.com/sub/tok123") == ""


@pytest.mark.asyncio
async def test_rial_list_and_cancel(client):
    res = await client.post("/api/v1/auth/telegram", json={"init_data": make_init_data(7300)})
    h = {"Authorization": f"Bearer {res.json()['access_token']}"}
    body = {"amount_toman": 200000, "source_card": "6037991234567893"}

    created = await client.post("/api/v1/wallet/rial/requests", json=body, headers=h)
    assert created.status_code == 200, created.text
    req_id = created.json()["id"]

    listed = await client.get("/api/v1/wallet/rial/requests", headers=h)
    assert listed.status_code == 200
    assert any(r["id"] == req_id and r["status"] == "pending" for r in listed.json())

    # A second one is blocked while the first is pending...
    assert (await client.post("/api/v1/wallet/rial/requests", json=body, headers=h)).status_code == 409

    # ...cancel frees the slot.
    cancelled = await client.post(f"/api/v1/wallet/rial/requests/{req_id}/cancel", headers=h)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    again = await client.post("/api/v1/wallet/rial/requests", json=body, headers=h)
    assert again.status_code == 200

    # Cancelling someone else's / non-pending request is rejected.
    recancel = await client.post(f"/api/v1/wallet/rial/requests/{req_id}/cancel", headers=h)
    assert recancel.status_code == 409
