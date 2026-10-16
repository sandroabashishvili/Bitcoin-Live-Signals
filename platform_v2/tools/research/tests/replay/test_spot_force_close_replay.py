from platform_v2.tools.research.replay.portfolio_replay_state import OpenPosition
from platform_v2.tools.research.replay.spot_force_close_replay import (
    apply_minus_rule_force_closes,
)


def _position(*, entry_timestamp_ms: int, entry: float) -> OpenPosition:
    return OpenPosition(
        side="BUY",
        entry_timestamp_ms=entry_timestamp_ms,
        entry=entry,
        margin=100.0,
        entry_fee=0.05,
        outcome={
            "entry_timestamp_ms": entry_timestamp_ms,
            "exit_timestamp_ms": 9_999,
            "side": "BUY",
            "entry": entry,
            "stop_loss": entry - 2.0,
            "take_profit": entry + 4.0,
            "exit": entry + 4.0,
            "resolution": "TP",
            "gross_pnl": 4.0,
            "fees": 0.1,
            "net_pnl": 3.9,
        },
    )


def test_minus_rule_closes_only_profitable_peers() -> None:
    profitable_peer = _position(entry_timestamp_ms=1, entry=98.0)
    trigger = _position(entry_timestamp_ms=2, entry=100.0)
    losing_peer = _position(entry_timestamp_ms=3, entry=100.5)

    remaining, forced = apply_minus_rule_force_closes(
        open_positions=[profitable_peer, trigger, losing_peer],
        timestamp_ms=1_000,
        candles=[{"timestamp_ms": 1_000, "close": 99.6}],
        candle_timestamps=[1_000],
        weak_open_position_pct=-0.003,
        exit_fee_rate=0.0005,
    )

    assert remaining == [trigger, losing_peer]
    assert len(forced) == 1
    assert forced[0]["entry_timestamp_ms"] == 1
    assert forced[0]["resolution"] == "FORCE_CLOSE"
    assert forced[0]["force_close_reason"] == "minus_rule"
    assert forced[0]["force_close_trigger_entry_timestamp_ms"] == 2


def test_minus_rule_does_nothing_without_weak_position() -> None:
    position = _position(entry_timestamp_ms=1, entry=100.0)

    remaining, forced = apply_minus_rule_force_closes(
        open_positions=[position],
        timestamp_ms=1_000,
        candles=[{"timestamp_ms": 1_000, "close": 99.8}],
        candle_timestamps=[1_000],
        weak_open_position_pct=-0.003,
        exit_fee_rate=0.0005,
    )

    assert remaining == [position]
    assert forced == []
