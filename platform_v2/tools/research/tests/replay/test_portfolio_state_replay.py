from platform_v2.tools.research.replay.portfolio_replay_permissions import (
    short_market_plan_ok,
    timing_context,
)
from platform_v2.tools.research.replay.portfolio_replay_state import (
    OpenPosition,
    close_due_positions,
    portfolio_stats,
    validation,
)


def _position(*, exit_timestamp_ms: int, resolution: str = "TP") -> OpenPosition:
    return OpenPosition(
        side="LONG",
        entry_timestamp_ms=100,
        entry=100.0,
        margin=100.0,
        entry_fee=0.2,
        outcome={
            "entry_timestamp_ms": 100,
            "exit_timestamp_ms": exit_timestamp_ms,
            "resolution": resolution,
            "net_pnl": 1.0,
        },
    )


def test_close_due_positions_keeps_data_end_open() -> None:
    remaining, closed = close_due_positions(
        open_positions=[_position(exit_timestamp_ms=200), _position(exit_timestamp_ms=150, resolution="DATA_END")],
        timestamp_ms=200,
    )
    assert len(closed) == 1
    assert len(remaining) == 1
    assert remaining[0].outcome["resolution"] == "DATA_END"


def test_validation_reports_exact_timestamp_fidelity() -> None:
    result = validation([100, 200, 300], [100, 300, 400])
    assert result["exact_timestamp_matches"] == 2
    assert result["predicted_only"] == 1
    assert result["actual_only"] == 1


def test_portfolio_stats_split_closed_outcomes_chronologically() -> None:
    closed = [
        {"entry_timestamp_ms": 100, "exit_timestamp_ms": 150, "side": "LONG", "net_pnl": 2.0, "resolution": "TP"},
        {"entry_timestamp_ms": 300, "exit_timestamp_ms": 350, "side": "SHORT", "net_pnl": -1.0, "resolution": "SL"},
    ]
    result = portfolio_stats(
        opened=closed,
        closed=closed,
        open_positions=[],
        split_timestamp_ms=200,
        period_origin_timestamp_ms=100,
    )
    assert result["chronological_train"]["net_pnl"] == 2.0
    assert result["chronological_test"]["net_pnl"] == -1.0
    assert result["by_side"]["LONG"]["closed"]["net_pnl"] == 2.0
    assert result["by_side"]["SHORT"]["closed"]["net_pnl"] == -1.0
    assert result["rolling_7d"][0]["all"]["net_pnl"] == 1.0


def test_timing_bands_match_runtime_entry_quality() -> None:
    assert timing_context(side="SHORT", prior_sides=["LONG"]).timing_type == "FRESH_FLIP"
    assert timing_context(side="SHORT", prior_sides=[]).timing_type == "FRESH_SIGNAL"
    assert timing_context(side="SHORT", prior_sides=["SHORT", "NO_SIGNAL"]).timing_type == "FRESH_REENTRY"
    assert timing_context(side="SHORT", prior_sides=["SHORT"] * 5).timing_type == "EARLY_CONTINUATION"
    assert timing_context(side="SHORT", prior_sides=["SHORT"] * 11).timing_type == "LATE_EXTENSION"
    assert timing_context(side="SHORT", prior_sides=["SHORT"] * 12).timing_type == "EXHAUSTED_MOVE"


def test_short_plan_continuation_override_requires_support_room() -> None:
    plan = {
        "location": {"distance_to_swing_low_atr": 0.8},
        "short_plan": {"zones": [{"center": 105.0, "from": 104.0, "to": 106.0}]},
    }
    assert short_market_plan_ok(
        entry_price=100.0,
        plan=plan,
        timing_type_name="EARLY_CONTINUATION",
        passed_gate_count=3,
        score=9.0,
    )
    plan["location"]["distance_to_swing_low_atr"] = 0.2
    assert not short_market_plan_ok(
        entry_price=100.0,
        plan=plan,
        timing_type_name="EARLY_CONTINUATION",
        passed_gate_count=3,
        score=9.0,
    )
