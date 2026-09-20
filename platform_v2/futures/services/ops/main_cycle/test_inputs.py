from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from platform_v2.futures.services.ops.main_cycle.inputs import MainCycleInputService
from platform_v2.futures.config import settings
from platform_v2.futures.storage.paths import candle_file_path


def test_cycle_key_uses_repository_when_virtual_json_path_is_absent() -> None:
    repository = Mock()
    repository.get_closed_candles.return_value = [SimpleNamespace(close_time_ms=123456789)]
    service = MainCycleInputService(candle_repository=repository)
    virtual_path = candle_file_path("BTCUSDT", "15m")

    result = service._build_cycle_key(
        (virtual_path,),
        symbol="BTCUSDT",
        timeframe="15m",
    )

    assert not virtual_path.exists()
    assert result.state == "ready"
    assert result.key == "BTCUSDT:15m:123456789"


def test_cycle_fetches_1m_but_builds_only_strategy_indicators() -> None:
    fetcher = Mock()
    fetcher.fetch_many.return_value = [candle_file_path("BTCUSDT", "15m")]
    repository = Mock()
    repository.get_closed_candles.return_value = [SimpleNamespace(close_time_ms=123456789)]
    indicator_builder = Mock()
    service = MainCycleInputService(
        candle_fetch_service=fetcher,
        candle_repository=repository,
        indicator_builder_service=indicator_builder,
    )
    profile = SimpleNamespace(symbol="BTCUSDT", timeframe="15m")

    service.prepare_cycle_inputs(profile=profile, fetch_limit=500)

    fetcher.fetch_many.assert_called_once_with(
        symbol="BTCUSDT",
        timeframes=settings.DEFAULT_FETCH_TIMEFRAMES,
        limit=500,
    )
    indicator_builder.build_many.assert_called_once_with(
        symbol="BTCUSDT",
        timeframes=settings.DEFAULT_CANDLE_TIMEFRAMES,
    )
