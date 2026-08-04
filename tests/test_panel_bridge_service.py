import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from bot_package.services.panel_bridge_service import (
    BridgeSkip,
    _remaining_data_limit,
    _rule_matches,
    _target_timing,
)


def test_rule_matches_panel_category_and_plan_together():
    rule = SimpleNamespace(
        source_panel_keys_json=json.dumps(["mexico_hajmi", "mexico_namahdod"]),
        source_category_keys_json=json.dumps(["vip"]),
        source_plan_ids_json=json.dumps([24]),
    )
    matching = SimpleNamespace(panel_key="mexico_hajmi", category_key="vip", shop_plan_id=24)
    other_plan = SimpleNamespace(panel_key="mexico_hajmi", category_key="vip", shop_plan_id=25)

    assert _rule_matches(rule, matching) is True
    assert _rule_matches(rule, other_plan) is False


def test_remaining_limit_carries_only_unused_source_volume():
    assert _remaining_data_limit({"data_limit": 10_000, "used_traffic": 3_000}) == 7_000
    assert _remaining_data_limit({"data_limit": 0, "used_traffic": 123}) == 0
    with pytest.raises(BridgeSkip):
        _remaining_data_limit({"data_limit": 10_000, "used_traffic": 10_000})


def test_target_expiry_is_exactly_the_source_expiry():
    expire = int((datetime.now(timezone.utc) + timedelta(days=12)).timestamp())

    timing = _target_timing({"status": "active", "expire": expire})

    assert timing == {"status": "active", "expire": expire, "on_hold_expire_duration": None}
