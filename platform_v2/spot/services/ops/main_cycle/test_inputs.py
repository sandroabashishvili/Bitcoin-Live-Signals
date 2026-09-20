from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

from platform_v2.spot.config import settings
from platform_v2.spot.services.ops.main_cycle.inputs import MainCycleInputService


def test_cycle_key_uses_market_database_when_virtual_json_path_is_absent(tmp_path: Path) -> None:
    virtual_path = tmp_path / "15m.json"
    with patch(
        "platform_v2.spot.services.ops.main_cycle.inputs.read_market_series_safely",
        return_value=[{"close_time": 123456789}],
    ):
        result = MainCycleInputService()._build_cycle_key(
            (virtual_path,),
            symbol="BTCUSDT",
            timeframe="15m",
        )

    assert not virtual_path.exists()
    assert result.state == "ready"
    assert result.key == "BTCUSDT:15m:123456789"


def test_cycle_fetches_1m_execution_candles() -> None:
    fetcher = Mock()
    fetcher.fetch_many.return_value = [Path("/virtual/BTCUSDT/15m.json")]
    service = MainCycleInputService(candle_fetch_service=fetcher)

    with patch(
        "platform_v2.spot.services.ops.main_cycle.inputs.read_market_series_safely",
        return_value=[{"close_time": 123456789}],
    ):
        service.prepare_cycle_inputs(symbol="BTCUSDT", timeframe="15m", fetch_limit=500)

    fetcher.fetch_many.assert_called_once_with(
        symbol="BTCUSDT",
        timeframes=settings.DEFAULT_FETCH_TIMEFRAMES,
        limit=500,
    )
