from __future__ import annotations

from platform_v2.tools.research.replay.candidate_position_management import (
    LONG_PROFIT_LOCK_70_25,
    managed_outcome,
)


def _candle(timestamp_ms: int, *, high: float, low: float, close: float) -> dict[str, float | int]:
    return {"timestamp_ms": timestamp_ms, "high": high, "low": low, "close": close}


def _run(candles: list[dict[str, float | int]]):
    return managed_outcome(
        policy_ids=(LONG_PROFIT_LOCK_70_25,),
        candles=candles,
        candle_timestamps=[int(row["timestamp_ms"]) for row in candles],
        entry_timestamp_ms=1_000,
        side="LONG",
        entry=100.0,
        stop_loss=90.0,
        take_profit=120.0,
        notional=500.0,
        entry_fee_rate=0.0005,
        exit_fee_rate=0.0002,
    )


def test_profit_lock_activates_for_next_candle_and_protects_reward() -> None:
    outcome = _run(
        [
            _candle(2_000, high=114.0, low=99.0, close=110.0),
            _candle(3_000, high=112.0, low=104.0, close=105.0),
        ]
    )

    assert outcome is not None
    assert outcome["resolution"] == "PROFIT_LOCK"
    assert outcome["exit"] == 105.0
    assert outcome["protection_activated_at_ms"] == 2_000


def test_activation_candle_does_not_retroactively_use_protected_stop() -> None:
    outcome = _run(
        [
            _candle(2_000, high=114.0, low=94.0, close=110.0),
            _candle(3_000, high=120.0, low=106.0, close=119.0),
        ]
    )

    assert outcome is not None
    assert outcome["resolution"] == "TP"


def test_original_stop_still_applies_before_activation() -> None:
    outcome = _run([_candle(2_000, high=110.0, low=89.0, close=91.0)])

    assert outcome is not None
    assert outcome["resolution"] == "SL"
