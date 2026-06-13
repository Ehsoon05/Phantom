"""Pending-top-up limits: 1 crypto invoice per coin, 1 pending rial request."""

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
from bot_package.models import CryptoInvoice, User  # noqa: E402
from bot_package.services import crypto_payment_service as cps  # noqa: E402
from bot_package.services.crypto_payment_service import (  # noqa: E402
    CryptoPaymentError,
    CryptoPaymentService,
)
from webapi.main import app  # noqa: E402


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


@pytest_asyncio.fixture(autouse=True)
async def _schema():
    from bot_package.database import engine
    from bot_package.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture()
async def client():
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest.mark.asyncio
async def test_crypto_one_pending_per_coin(monkeypatch):
    # Pretend every coin is configured so create_invoice reaches the limit check.
    monkeypatch.setattr(cps, "is_coin_available", lambda key: True)
    async with async_session() as session:
        session.add(User(telegram_id=7100, first_name="c"))
        session.add(
            CryptoInvoice(
                user_id=7100, coin="USDT", network="TRC20", deposit_address="x",
                expected_crypto="5", quoted_toman=100000, locked_rate="20000", status="pending",
            )
        )
        await session.commit()

        # A second USDT invoice (via the TON-USDT method) must be rejected.
        with pytest.raises(CryptoPaymentError, match="pending USDT"):
            await CryptoPaymentService.create_invoice(session, 7100, "USDT_TON", 100000)


@pytest.mark.asyncio
async def test_rial_single_pending(client):
    res = await client.post("/api/v1/auth/telegram", json={"init_data": make_init_data(7200)})
    token = res.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    body = {"amount_toman": 200000, "phone_number": "+989121234567", "source_card": "6037991234567890"}

    first = await client.post("/api/v1/wallet/rial/requests", json=body, headers=h)
    assert first.status_code == 200, first.text
    assert first.json()["copy_text"]  # template wiring produced a copy text

    second = await client.post("/api/v1/wallet/rial/requests", json=body, headers=h)
    assert second.status_code == 409
