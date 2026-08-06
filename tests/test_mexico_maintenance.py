import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from bot_package.services.mexico_panel_maintenance_service import (
    _cached_metadata,
    _dominant_group_ids,
    _desired_device_limit,
    _is_synced_namahdod_item,
    _remaining_hajmi_bytes,
    _recovery_username,
    _restored_expire,
    _stored_recovery_metadata,
    _subscription_needs_sync,
    _should_reset_unlimited,
    _synced_device_limit,
    _user_rows,
)
from bot_package.services.subscription_link_service import SubscriptionLinkService


def test_device_limit_prefers_config_then_synced_panel_then_plan():
    plan = SimpleNamespace(subscription_device_limit=1)
    config = SimpleNamespace(subscription_device_limit=2)
    assert _desired_device_limit(config, plan, {"device_limit": 1}) == 2

    config.subscription_device_limit = None
    assert _desired_device_limit(config, plan, {"device_limit": 2}) == 2
    assert _desired_device_limit(config, plan, None) == 1

    config.subscription_device_limit = 0
    plan.subscription_device_limit = 0
    assert _desired_device_limit(config, plan, {"device_limit": 2}) == 2
    assert _desired_device_limit(config, plan, None) == 1


def test_hajmi_restore_uses_only_remaining_volume():
    config = SimpleNamespace(volume_gb=20)
    total, used, remaining = _remaining_hajmi_bytes(
        config,
        {"total": 20 * 1024**3, "used": 7 * 1024**3},
    )

    assert total == 20 * 1024**3
    assert used == 7 * 1024**3
    assert remaining == 13 * 1024**3


def test_panel_user_listing_accepts_pasarguard_shape():
    assert _user_rows({"users": [{"username": "one"}]}) == [{"username": "one"}]
    assert _user_rows([{"username": "two"}]) == [{"username": "two"}]


def test_dominant_group_ids_follow_the_live_panel_users():
    users = {
        "one": {"group_ids": [7]},
        "two": {"group_ids": [7]},
        "legacy": {"group_ids": [1]},
    }

    assert _dominant_group_ids(users) == [7]


def test_cached_subscription_metadata_is_used_when_live_upstream_is_gone():
    assert _cached_metadata(
        {
            "cache_available": True,
            "upstream_status": "active",
            "upstream_total_bytes": 20 * 1024**3,
            "upstream_used_bytes": 7 * 1024**3,
            "upstream_expire": 1_900_000_000,
        }
    ) == {
        "status": "active",
        "total": 20 * 1024**3,
        "used": 7 * 1024**3,
        "expire": 1_900_000_000,
    }


def test_stored_hajmi_state_recovers_remaining_volume_without_upstream_cache():
    config = SimpleNamespace(
        display_total_bytes=20 * 1024**3,
        usage_offset_bytes=7 * 1024**3,
        volume_gb=20,
    )

    assert _stored_recovery_metadata(config, "mexico_hajmi") == {
        "status": "active",
        "total": 20 * 1024**3,
        "used": 7 * 1024**3,
        "expire": 0,
    }


def test_namahdod_can_be_recovered_without_old_upstream_metadata():
    config = SimpleNamespace(display_total_bytes=0, usage_offset_bytes=0, volume_gb=0)

    assert _stored_recovery_metadata(config, "mexico_namahdod") == {
        "status": "active",
        "total": 0,
        "used": 0,
        "expire": 0,
    }


def test_subscription_sync_runs_only_for_changed_or_stale_panel_identity():
    current = {"source_panel_key": "mexico_namahdod"}

    assert _subscription_needs_sync("mexico_namahdod", current, False) is False
    assert _subscription_needs_sync("mexico_namahdod", current, True) is True
    assert _subscription_needs_sync("mexico_namahdod", None, False) is True
    assert (
        _subscription_needs_sync(
            "mexico_namahdod",
            {"source_panel_key": "mexico_hajmi"},
            False,
        )
        is True
    )


def test_manual_subscription_is_detected_from_source_or_live_panel_owner():
    assert _is_synced_namahdod_item(
        {"source_panel_key": "mexico_namahdod"},
        {},
    ) is True
    assert _is_synced_namahdod_item(
        {"upstream_panel_username": "manual-user"},
        {"manual-user": {}},
    ) is True
    assert _is_synced_namahdod_item(
        {
            "upstream_status": "active",
            "upstream_total_bytes": 300 * 1024**3,
            "service_name": "VIP Unlimited",
        },
        {},
    ) is True
    assert _is_synced_namahdod_item(
        {"source_panel_key": "mexico_hajmi", "service_name": "Unlimited"},
        {},
    ) is False


def test_manual_device_limit_defaults_to_one_and_keeps_explicit_limit():
    assert _synced_device_limit({"device_limit": None}) == 1
    assert _synced_device_limit({"device_limit": 2}) == 2


def test_unlimited_reset_is_not_limited_to_bot_purchases():
    assert _should_reset_unlimited({"used_traffic": 300 * 1024**3, "status": "limited"}) is True
    assert _should_reset_unlimited({"used_traffic": 299 * 1024**3, "status": "active"}) is False
    assert _should_reset_unlimited({"used_traffic": 300 * 1024**3, "status": "expired"}) is False


def test_manual_subscription_sync_preserves_token_and_sets_unlimited_metadata():
    captured = {}

    async def fake_sync(payload, identity):
        captured.update(payload)
        return True

    with patch.object(SubscriptionLinkService, "_sync_payload", side_effect=fake_sync):
        result = asyncio.run(
            SubscriptionLinkService.sync_external_to_panel(
                {
                    "token": "public-token",
                    "upstream_url": "https://old.example/sub/token",
                    "category_key": "manual",
                    "service_name": "Manual VIP",
                    "device_limit": 2,
                },
                upstream_url="https://provider.example/sub/new-token",
                panel_username="ManualVIP",
                panel_key="mexico_namahdod",
                device_limit=2,
                display_total_bytes=0,
            )
        )

    assert result is True
    assert captured["token"] == "public-token"
    assert captured["upstream_url"] == "https://provider.example/sub/new-token"
    assert captured["source_panel_key"] == "mexico_namahdod"
    assert captured["display_total_bytes"] == 0
    assert captured["device_limit"] == 2


def test_missing_expiry_is_bounded_to_pasarguard_maximum():
    plan = SimpleNamespace(provision_duration_days=0, duration_days=90)
    remaining = _restored_expire({"expire": 0}, plan)

    from datetime import datetime, timezone

    seconds = remaining - int(datetime.now(timezone.utc).timestamp())
    assert 29 * 86400 < seconds < 30 * 86400


def test_recovery_username_cleans_legacy_names_and_adds_stable_collision_suffix():
    assert _recovery_username("SinaJay namhadood", 847) == "SinaJay_namhadood"
    assert _recovery_username("Khodam", 820, force_suffix=True) == "Khodam_r820"
    assert _recovery_username("نام قدیمی", 850, force_suffix=True) == "PhantomHubs_r850"
