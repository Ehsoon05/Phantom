from types import SimpleNamespace

from bot_package.services.mexico_panel_maintenance_service import (
    _cached_metadata,
    _dominant_group_ids,
    _desired_device_limit,
    _remaining_hajmi_bytes,
    _recovery_username,
    _restored_expire,
    _user_rows,
)


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
