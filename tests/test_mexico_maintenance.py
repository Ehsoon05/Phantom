from types import SimpleNamespace

from bot_package.services.mexico_panel_maintenance_service import (
    _dominant_group_ids,
    _desired_device_limit,
    _remaining_hajmi_bytes,
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
