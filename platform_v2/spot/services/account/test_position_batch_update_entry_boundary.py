from platform_v2.shared.backend.market.candle import Candle
from platform_v2.spot.domain.models.position import ExecutionSetup, PositionRecord, PositionStatus
from platform_v2.spot.domain.models.signal import SignalSide
from platform_v2.spot.services.account.position_batch_update_service import PositionBatchUpdateService


def test_exit_filter_skips_candle_that_started_before_position_open() -> None:
    position = PositionRecord(
        position_id="SPOT-TEST",
        symbol="BTCUSDT",
        timeframe="15m",
        side=SignalSide.BUY,
        status=PositionStatus.OPEN,
        execution=ExecutionSetup(100.0, 90.0, 120.0, 2.0, 100.0),
        opened_at="1970-01-01 00:01:31",
        opened_at_ms=91_000,
    )
    candles = [
        Candle("BTCUSDT", "5m", 90_000, 94_999, 100, 101, 99, 100, 1),
        Candle("BTCUSDT", "5m", 95_000, 99_999, 100, 101, 99, 100, 1),
    ]

    assert PositionBatchUpdateService()._candles_after_position_open(position, candles) == [
        candles[1]
    ]
