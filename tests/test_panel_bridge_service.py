import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot_package.services.panel_bridge_service import (
    BridgeSkip,
    PanelBridgeService,
    _automatic_reconcile_candidate,
    _bridge_fallback_username,
    _external_source_payload,
    _external_panel_fragment,
    _metadata_source_payload,
    _remaining_data_limit,
    _rule_matches,
    _target_timing,
)


def test_bridge_fallback_username_is_stable_and_bounded():
    value = _bridge_fallback_username("khodam", 1, 796)

    assert value == "khodam_b1_796"
    assert len(_bridge_fallback_username("x" * 100, 12, 3456)) <= 32


def test_external_cached_metadata_builds_unlimited_source_payload():
    payload = _external_source_payload(
        {
            "cache_available": True,
            "upstream_status": "active",
            "upstream_total_bytes": 0,
            "upstream_used_bytes": 123,
            "upstream_expire": 1_900_000_000,
        }
    )

    assert payload == {
        "status": "active",
        "data_limit": 0,
        "used_traffic": 123,
        "expire": 1_900_000_000,
        "on_hold_expire_duration": None,
    }


def test_metadata_payload_preserves_usage_and_expiry():
    payload = _metadata_source_payload(
        {"status": "active", "total": 1000, "used": 400, "expire": 1_900_000_000}
    )

    assert payload["data_limit"] == 1000
    assert payload["used_traffic"] == 400
    assert payload["expire"] == 1_900_000_000


def test_external_panel_fragment_separates_unlimited_and_volume_accounts():
    assert _external_panel_fragment({"data_limit": 0}) == "namahdod"
    assert _external_panel_fragment({"data_limit": 10 * 1024**3}) == "hajmi"


def test_external_panel_resolution_prefers_the_account_that_owns_the_user():
    hajmi = SimpleNamespace(key="mexico_hajmi")
    namahdod = SimpleNamespace(key="mexico_namahdod")
    cached = {"status": "active", "data_limit": 0, "used_traffic": 10}

    async def fetch(panel, username):
        assert username == "TestKodam"
        if panel.key == "mexico_hajmi":
            return {"status": "active", "data_limit": 50 * 1024**3, "used_traffic": 10}
        raise BridgeSkip("not found")

    with patch.object(PanelBridgeService, "_fetch_panel_user", side_effect=fetch):
        panel, payload = asyncio.run(
            PanelBridgeService._resolve_external_panel(
                [namahdod, hajmi],
                requested_key="",
                username="TestKodam",
                cached_payload=cached,
                existing_panel_key="mexico_namahdod",
            )
        )

    assert panel.key == "mexico_hajmi"
    assert payload["data_limit"] == 50 * 1024**3


def test_external_panel_resolution_keeps_live_classification_during_api_outage():
    hajmi = SimpleNamespace(key="mexico_hajmi")
    namahdod = SimpleNamespace(key="mexico_namahdod")
    cached = {"status": "active", "data_limit": 0, "used_traffic": 10}

    with patch.object(
        PanelBridgeService,
        "_fetch_panel_user",
        new=AsyncMock(side_effect=RuntimeError("panel unavailable")),
    ):
        panel, payload = asyncio.run(
            PanelBridgeService._resolve_external_panel(
                [namahdod, hajmi],
                requested_key="",
                username="TestKodam",
                cached_payload=cached,
                existing_panel_key="mexico_hajmi",
            )
        )

    assert panel.key == "mexico_hajmi"
    assert payload is cached


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


def test_automatic_reconcile_retries_all_sold_config_sources():
    inventory = SimpleNamespace(is_sold=True, panel_deleted_at=None, provision_source="inventory")
    panel = SimpleNamespace(is_sold=True, panel_deleted_at=None, provision_source="panel")
    external = SimpleNamespace(
        is_sold=True,
        panel_deleted_at=None,
        provision_source="external_subscription",
    )
    unsold = SimpleNamespace(is_sold=False, panel_deleted_at=None, provision_source="inventory")
    deleted = SimpleNamespace(
        is_sold=True,
        panel_deleted_at=datetime.now(timezone.utc),
        provision_source="panel",
    )

    assert _automatic_reconcile_candidate(inventory) is True
    assert _automatic_reconcile_candidate(panel) is True
    assert _automatic_reconcile_candidate(external) is True
    assert _automatic_reconcile_candidate(unsold) is False
    assert _automatic_reconcile_candidate(deleted) is False


def test_remaining_limit_carries_only_unused_source_volume():
    assert _remaining_data_limit({"data_limit": 10_000, "used_traffic": 3_000}) == 7_000
    assert _remaining_data_limit({"data_limit": 0, "used_traffic": 123}) == 0
    assert _remaining_data_limit({"data_limit": 10_000, "used_traffic": 10_000}) == 0


def test_target_expiry_is_exactly_the_source_expiry():
    expire = int((datetime.now(timezone.utc) + timedelta(days=12)).timestamp())

    timing = _target_timing({"status": "active", "expire": expire})

    assert timing == {"status": "active", "expire": expire, "on_hold_expire_duration": None}


def test_target_expiry_accepts_pasarguard_iso_dates():
    timing = _target_timing({"status": "active", "expire": "2030-08-30T14:51:25Z"})

    assert timing["expire"] == 1914331885


def test_disabled_source_disables_the_equivalent_user():
    timing = _target_timing({"status": "disabled", "expire": 0})

    assert timing == {"status": "disabled", "expire": 0, "on_hold_expire_duration": None}
