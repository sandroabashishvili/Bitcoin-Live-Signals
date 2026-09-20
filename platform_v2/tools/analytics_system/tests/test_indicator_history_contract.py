from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from platform_v2.shared.backend.market.candle import Candle as SpotCandle
from platform_v2.shared.backend.market.candle import Candle as FuturesCandle
from platform_v2.spot.services.analytics.indicator_builder_service import IndicatorBuilderService
from platform_v2.futures.services.analytics.indicator_pipeline.builder_service import (
    FuturesIndicatorBuilderService,
)


def _candles(candle_type):
    return [
        candle_type(
            symbol="BTCUSDT",
            timeframe="15m",
            open_time_ms=index * 900_000,
            close_time_ms=(index + 1) * 900_000 - 1,
            open_price=100.0 + index,
            high_price=101.0 + index,
            low_price=99.0 + index,
            close_price=100.5 + index,
            volume=10.0 + index,
        )
        for index in range(45)
    ]


class _SpotReader:
    def __init__(self) -> None:
        self.limit = 1

    def read_candles(self, *, symbol, timeframe, limit):
        self.limit = limit
        return _candles(SpotCandle)


class _FuturesRepository:
    def __init__(self) -> None:
        self.limit = 1

    def get_closed_candles(self, *, symbol, timeframe, limit):
        self.limit = limit
        return _candles(FuturesCandle)


class IndicatorHistoryContractTests(unittest.TestCase):
    def test_spot_builder_reads_all_candles_and_writes_ema9(self) -> None:
        reader = _SpotReader()
        captured: dict[str, object] = {}
        with tempfile.TemporaryDirectory() as folder, patch(
            "platform_v2.spot.services.analytics.indicator_builder_service.indicator_snapshot_file_path",
            return_value=Path(folder) / "15m.json",
        ), patch(
            "platform_v2.spot.services.analytics.indicator_builder_service.replace_market_series",
            side_effect=lambda **kwargs: captured.update(kwargs),
        ):
            path = IndicatorBuilderService(reader).build_and_store(symbol="BTCUSDT", timeframe="15m")
            rows = captured["rows"]
        self.assertIsNone(reader.limit)
        self.assertIn("ema9", rows[-1])

    def test_futures_builder_reads_all_candles(self) -> None:
        repository = _FuturesRepository()
        captured: dict[str, object] = {}
        with tempfile.TemporaryDirectory() as folder, patch(
            "platform_v2.futures.services.analytics.indicator_pipeline.builder_service.indicator_snapshot_file_path",
            return_value=Path(folder) / "15m.json",
        ), patch(
            "platform_v2.futures.services.analytics.indicator_pipeline.builder_service.replace_market_series",
            side_effect=lambda **kwargs: captured.update(kwargs),
        ):
            path = FuturesIndicatorBuilderService(repository).build_and_store(
                symbol="BTCUSDT",
                timeframe="15m",
            )
            rows = captured["rows"]
        self.assertIsNone(repository.limit)
        self.assertIn("ema9", rows[-1])


if __name__ == "__main__":
    unittest.main()
