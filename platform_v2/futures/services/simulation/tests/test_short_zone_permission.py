from platform_v2.futures.domain.models.signal import GateSnapshot
from platform_v2.futures.services.simulation.entry_permission_context_service import FuturesEntryPermissionContextService


def _outside_zone():
    return {
        "allowed": False, "alignment": "OUTSIDE_ZONE", "bias": "MIXED",
        "nearest_zone": {"from": 77411.48, "entry_in_zone": False},
        "plan_location": {"distance_to_swing_low_atr": 1.5487, "short_entry_state": "CLEAN"},
    }


def _apply(service, permission, side="SHORT"):
    return service.apply_short_continuation_override(
        signal_side=side, market_plan_permission=permission, entry_price=77199.7,
        entry_quality={"allowed": True, "timing_type": "FRESH_REENTRY"},
        gates=GateSnapshot(mtf=True, regime=True, trend=True, structure=True), score=10.74,
    )


def test_fut_000067_outside_zone_entry_is_now_blocked():
    service = FuturesEntryPermissionContextService(runtime_store=None)
    permission = _outside_zone()
    result = _apply(service, permission)
    assert result["allowed"] is False
    assert result["alignment"] == "OUTSIDE_ZONE"
    assert "continuation_override" not in result


def test_legacy_research_control_reproduces_original_permission():
    service = FuturesEntryPermissionContextService(runtime_store=None, short_continuation_override_enabled=True)
    assert _apply(service, _outside_zone())["alignment"] == "OUTSIDE_ZONE_CONTINUATION_OVERRIDE"


def test_in_zone_and_long_permissions_remain_allowed():
    service = FuturesEntryPermissionContextService(runtime_store=None)
    for side, alignment in [("SHORT", "IN_ZONE"), ("LONG", "NOT_SHORT")]:
        permission = {"allowed": True, "alignment": alignment}
        assert _apply(service, permission, side) == permission
