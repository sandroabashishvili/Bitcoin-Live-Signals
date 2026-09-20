from __future__ import annotations

from platform_v2.shared.backend.market.candle import Candle as FuturesCandle
from platform_v2.futures.services.analytics.indicator_pipeline.snapshot_builder import (
    IndicatorSnapshotBuilder as FuturesSnapshotBuilder,
)
from platform_v2.shared.backend.market.candle import Candle as SpotCandle
from platform_v2.spot.services.analytics.indicator_snapshot_builder import (
    IndicatorSnapshotBuilder as SpotSnapshotBuilder,
)
from platform_v2.tools.research.replay.legacy_spot_signal import SignalDecisionService


def _candles(model: type[SpotCandle] | type[FuturesCandle]):
    result = []
    for index in range(120):
        close = 60_000.0 + (index * 12.0) + ((index % 7) * 4.0)
        result.append(
            model(
                symbol="BTCUSDT",
                timeframe="15m",
                open_time_ms=index * 900_000,
                close_time_ms=((index + 1) * 900_000) - 1,
                open_price=close - 5.0,
                high_price=close + 20.0,
                low_price=close - 20.0,
                close_price=close,
                volume=100.0 + index,
            )
        )
    return result


def test_spot_snapshot_persists_three_point_macd_histogram() -> None:
    rows = SpotSnapshotBuilder().build_rows(
        symbol="BTCUSDT",
        timeframe="15m",
        candles=_candles(SpotCandle),
    )

    assert len(rows[-1]["macd_histogram"]) == 3


def test_futures_snapshot_persists_three_point_macd_histogram() -> None:
    rows = FuturesSnapshotBuilder().build_rows(
        symbol="BTCUSDT",
        timeframe="15m",
        candles=_candles(FuturesCandle),
    )

    assert len(rows[-1]["macd_histogram"]) == 3


def test_repaired_histogram_is_not_live_rewarded_before_promotion() -> None:
    snapshot = type("Snapshot", (), {"extras": {"macd_histogram": [1.0, 2.0, 3.0]}})()

    assert SignalDecisionService._has_rising_macd_histogram(snapshot) is False
