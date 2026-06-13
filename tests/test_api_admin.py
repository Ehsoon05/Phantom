"""Smoke tests for the admin parity endpoints (auth, permissions, CRUD)."""

import pytest
import pytest_asyncio

from tests import _api_test_env  # noqa: F401  (must precede api/bot imports)

import httpx  # noqa: E402
from sqlalchemy import select  # noqa: E402

from bot_package.config_loader import BotConfig  # noqa: E402
from bot_package.database import async_session  # noqa: E402
from bot_package.models import Admin, ShopPlan  # noqa: E402
from webapi.main import app  # noqa: E402


@pytest_asyncio.fixture()
async def client():
    async with app.router.lifespan_context(app):
        # An owner admin + a limited admin to exercise permission gating.
        async with async_session() as session:
            for tid in (9001, 9002):
                existing = (
                    await session.execute(select(Admin).where(Admin.telegram_id == tid))
                ).scalar_one_or_none()
                if existing is None:
                    session.add(
                        Admin(
                            telegram_id=tid,
                            permissions="all" if tid == 9001 else "reports",
                            is_owner=(tid == 9001),
                            is_active=True,
                        )
                    )
            await session.commit()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


async def _login(client, telegram_id):
    res = await client.post(
        "/api/v1/admin/auth/login",
        json={"telegram_id": telegram_id, "password": BotConfig.ADMIN_PASSWORD or "x"},
    )
    return res


@pytest.mark.asyncio
async def test_owner_can_crud_plans_and_categories(client, monkeypatch):
    monkeypatch.setattr(BotConfig, "ADMIN_PASSWORD", "testpass", raising=False)
    res = await _login(client, 9001)
    assert res.status_code == 200, res.text
    h = {"Authorization": f"Bearer {res.json()['access_token']}"}

    # Create a plan
    created = await client.post(
        "/api/v1/admin/plans",
        json={"volume_gb": 7, "title": "هفت گیگ", "price": 99000, "category_key": "default"},
        headers=h,
    )
    assert created.status_code == 200, created.text
    plan_id = created.json()["id"]

    # It shows up in the list
    listed = await client.get("/api/v1/admin/plans", headers=h)
    assert listed.status_code == 200
    assert any(p["id"] == plan_id for p in listed.json())

    # Update price
    priced = await client.post(
        f"/api/v1/admin/plans/{plan_id}/price", json={"price": 123000}, headers=h
    )
    assert priced.status_code == 200
    assert priced.json()["price"] == 123000

    # Categories list works
    cats = await client.get("/api/v1/admin/categories", headers=h)
    assert cats.status_code == 200

    # Delete the plan
    deleted = await client.delete(f"/api/v1/admin/plans/{plan_id}", headers=h)
    assert deleted.status_code == 200


@pytest.mark.asyncio
async def test_settings_roundtrip(client, monkeypatch):
    monkeypatch.setattr(BotConfig, "ADMIN_PASSWORD", "testpass", raising=False)
    res = await _login(client, 9001)
    h = {"Authorization": f"Bearer {res.json()['access_token']}"}

    set_res = await client.put(
        "/api/v1/admin/settings/trial",
        json={"enabled": True, "volume_mb": 500, "duration_hours": 24},
        headers=h,
    )
    assert set_res.status_code == 200
    got = await client.get("/api/v1/admin/settings/trial", headers=h)
    assert got.json()["volume_mb"] == 500
    assert got.json()["enabled"] is True


@pytest.mark.asyncio
async def test_permission_gating(client, monkeypatch):
    monkeypatch.setattr(BotConfig, "ADMIN_PASSWORD", "testpass", raising=False)
    # Limited admin (reports only) cannot manage plans or admins.
    res = await _login(client, 9002)
    h = {"Authorization": f"Bearer {res.json()['access_token']}"}

    plans = await client.get("/api/v1/admin/plans", headers=h)  # needs 'prices'
    assert plans.status_code == 403

    admins = await client.get("/api/v1/admin/admins", headers=h)  # owner only
    assert admins.status_code == 403

    # But reports-scoped referral report is allowed
    report = await client.get("/api/v1/admin/referrals/report", headers=h)
    assert report.status_code == 200


@pytest.mark.asyncio
async def test_owner_only_admin_management(client, monkeypatch):
    monkeypatch.setattr(BotConfig, "ADMIN_PASSWORD", "testpass", raising=False)
    res = await _login(client, 9001)
    h = {"Authorization": f"Bearer {res.json()['access_token']}"}

    listed = await client.get("/api/v1/admin/admins", headers=h)
    assert listed.status_code == 200
    assert any(a["telegram_id"] == 9001 for a in listed.json())

    added = await client.post(
        "/api/v1/admin/admins",
        json={"telegram_id": 9003, "permissions": "users,reports"},
        headers=h,
    )
    assert added.status_code == 200
    assert added.json()["permissions"] == "users,reports"
