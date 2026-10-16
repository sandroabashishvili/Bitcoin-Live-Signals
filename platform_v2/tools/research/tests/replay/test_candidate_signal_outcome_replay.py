from __future__ import annotations

from platform_v2.tools.research.replay.candidate_signal_outcome_replay import _outcome


def test_long_outcome_uses_conservative_stop_when_both_levels_hit() -> None:
    candles = [
        {"timestamp_ms": 1_000, "high": 100.0, "low": 100.0, "close": 100.0},
        {"timestamp_ms": 2_000, "high": 110.0, "low": 90.0, "close": 105.0},
    ]

    result = _outcome(
        candles=candles,
        candle_timestamps=[1_000, 2_000],
        entry_timestamp_ms=1_000,
        side="LONG",
        entry=100.0,
        stop_loss=95.0,
        take_profit=105.0,
        notional=100.0,
        entry_fee_rate=0.0,
        exit_fee_rate=0.0,
    )

    assert result is not None
    assert result["resolution"] == "SL_AMBIGUOUS_CANDLE"
    assert result["net_pnl"] == -5.0


def test_short_outcome_resolves_take_profit() -> None:
    candles = [
        {"timestamp_ms": 1_000, "high": 100.0, "low": 100.0, "close": 100.0},
        {"timestamp_ms": 2_000, "high": 101.0, "low": 94.0, "close": 96.0},
    ]

    result = _outcome(
        candles=candles,
        candle_timestamps=[1_000, 2_000],
        entry_timestamp_ms=1_000,
        side="SHORT",
        entry=100.0,
        stop_loss=105.0,
        take_profit=95.0,
        notional=100.0,
        entry_fee_rate=0.0,
        exit_fee_rate=0.0,
    )

    assert result is not None
    assert result["resolution"] == "TP"
    assert result["net_pnl"] == 5.0
