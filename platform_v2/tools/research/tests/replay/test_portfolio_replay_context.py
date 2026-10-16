from types import SimpleNamespace

from platform_v2.tools.research.replay.portfolio_replay_context import build_market_context_7d


class _Index:
    def __init__(self, values):
        self.values = values

    def at(self, timestamp_ms):
        return self.values.get(timestamp_ms)


def test_market_context_groups_snapshots_into_fixed_seven_day_periods() -> None:
    day_ms = 24 * 60 * 60 * 1000
    values = {
        0: SimpleNamespace(price=100, rsi=40, adx=20, atr_growth_20=0.1, atr=5),
        day_ms: SimpleNamespace(price=110, rsi=60, adx=30, atr_growth_20=0.2, atr=7),
        8 * day_ms: SimpleNamespace(price=90, rsi=30, adx=25, atr_growth_20=0.0, atr=6),
    }
    rows = build_market_context_7d(
        snapshots=_Index(values),
        timestamps=values,
        origin_timestamp_ms=0,
    )
    assert len(rows) == 2
    assert rows[0]["price_return_pct"] == 10.0
    assert rows[0]["avg_rsi"] == 50.0
    assert rows[1]["snapshot_count"] == 1
