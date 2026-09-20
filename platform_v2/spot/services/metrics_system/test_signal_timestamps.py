from datetime import UTC, datetime
from types import SimpleNamespace

from platform_v2.spot.services.metrics_system.strategy_content import StrategyPageContentService
from platform_v2.spot.services.analytics.strategy_effectiveness.gate_stats import closed_trade_gate_effectiveness
from platform_v2.spot.services.analytics.strategy_effectiveness.outcome import theoretical_outcome


def signal():
    stamp = int(datetime(2026, 9, 10, 18, 29, 59, 999000, tzinfo=UTC).timestamp() * 1000)
    return dict(timestamp_ms=stamp, symbol="BTCUSDT", timeframe="15m", side="BUY",
                gates={"trend": True}, theoretical_setup={"stop_loss": 90, "take_profit": 110})


def test_display_preserves_candle_close():
    assert StrategyPageContentService.format_signal_timestamp(signal()) == "10.09.2026, 18:29:59"


def test_denial_matching_does_not_merge_distinct_timestamps_in_same_window():
    row = signal()
    other = {**row, "timestamp_ms": row["timestamp_ms"] - 1000}
    assert StrategyPageContentService.matching_denied_row(row, [{"signal": other}]) is None
    denied = {"signal": row}
    assert StrategyPageContentService.matching_denied_row(row, [denied]) is denied


def test_closed_trade_uses_source_candle_despite_later_execution():
    position = SimpleNamespace(symbol="BTCUSDT", timeframe="15m",
        signal_candle_close_time="2026-09-10 18:29:59", opened_at="2026-09-10 18:32:10",
        exit_reason="tp_hit", net_pnl=3, was_force_closed=False)
    stats = closed_trade_gate_effectiveness(signal_rows=[signal()], closed_positions=[position], gate_names=("trend",))
    assert stats["trend"]["participated"] == 1
    assert stats["trend"]["tp"] == 1


def test_theoretical_outcome_excludes_prices_before_signal_close():
    row = signal()
    bars = [dict(timestamp=row["timestamp_ms"] - 60000, low=80, high=100),
            dict(timestamp=row["timestamp_ms"] + 1, low=95, high=111)]
    assert theoretical_outcome(row=row, candles=bars) == "tp"


def test_legacy_positions_keep_their_existing_bucket_attribution():
    row = {**signal(), "timestamp_ms": signal()["timestamp_ms"] + 120000}
    position = SimpleNamespace(symbol="BTCUSDT", timeframe="15m",
        opened_at="2026-09-10 18:32:10", exit_reason="tp_hit", net_pnl=3)
    stats = closed_trade_gate_effectiveness(signal_rows=[row], closed_positions=[position], gate_names=("trend",))
    assert stats["trend"]["participated"] == 1
