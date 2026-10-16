from __future__ import annotations

from platform_v2.tools.research.replay.tp_touch_fidelity_audit import _audit_position, _first_touch
from platform_v2.futures.services.simulation.position_service import FuturesPositionService
from platform_v2.shared.backend.market.candle import Candle
from platform_v2.spot.domain.models.position import ExecutionSetup, ExitReason, PositionRecord, PositionStatus
from platform_v2.spot.domain.models.signal import SignalSide
from platform_v2.spot.services.account.position_update_service import PositionUpdateService


def _candle(*, close_time: int, high: float, low: float) -> dict[str, float | int]:
    return {
        "timestamp": close_time - 299_999,
        "close_time": close_time,
        "high": high,
        "low": low,
        "close": (high + low) / 2,
    }


def test_long_wick_touch_is_detected_from_high() -> None:
    touch = _first_touch(
        side="BUY",
        opened_at_ms=1_000,
        closed_at_ms=2_000,
        take_profit=110.0,
        stop_loss=90.0,
        candles=[_candle(close_time=2_000, high=110.0, low=100.0)],
    )

    assert touch is not None
    assert touch["expected"] == "TP"


def test_short_wick_touch_is_detected_from_low() -> None:
    touch = _first_touch(
        side="SHORT",
        opened_at_ms=1_000,
        closed_at_ms=2_000,
        take_profit=90.0,
        stop_loss=110.0,
        candles=[_candle(close_time=2_000, high=100.0, low=90.0)],
    )

    assert touch is not None
    assert touch["expected"] == "TP"


def test_same_candle_tp_and_sl_is_reported_as_ambiguous() -> None:
    touch = _first_touch(
        side="BUY",
        opened_at_ms=1_000,
        closed_at_ms=2_000,
        take_profit=110.0,
        stop_loss=90.0,
        candles=[_candle(close_time=2_000, high=111.0, low=89.0)],
    )

    assert touch is not None
    assert touch["expected"] == "BOTH"


def test_tp_recorded_on_second_touch_is_reported_as_delayed() -> None:
    audit = _audit_position(
        market="FUTURES",
        opened={
            "position_id": "FUT-TEST",
            "event": "OPENED",
            "side": "LONG",
            "timestamp_ms": 1_000,
            "execution": {
                "entry_price": 100.0,
                "take_profit": 110.0,
                "stop_loss": 90.0,
            },
        },
        latest={
            "position_id": "FUT-TEST",
            "event": "CLOSED",
            "timestamp_ms": 3_000,
            "exit_reason": "TP_HIT",
        },
        candles=[
            _candle(close_time=2_000, high=111.0, low=100.0),
            _candle(close_time=3_000, high=112.0, low=101.0),
        ],
    )

    assert audit["issue"] == "delayed_recorded_tp_after_first_touch"
    assert audit["recording_delay_ms"] == 1_000


def test_spot_runtime_closes_on_first_wick_even_when_close_is_below_tp() -> None:
    position = PositionRecord(
        position_id="SPOT-TEST",
        symbol="BTCUSDT",
        timeframe="15m",
        side=SignalSide.BUY,
        status=PositionStatus.OPEN,
        execution=ExecutionSetup(
            entry_price=100.0,
            stop_loss=90.0,
            take_profit=110.0,
            rr_ratio=1.0,
            position_size=100.0,
        ),
        opened_at="1000",
    )
    first_wick = Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time_ms=1_001,
        close_time_ms=2_000,
        open_price=105.0,
        high_price=111.0,
        low_price=100.0,
        close_price=104.0,
        volume=1.0,
    )
    later_wick = Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time_ms=2_001,
        close_time_ms=3_000,
        open_price=105.0,
        high_price=112.0,
        low_price=101.0,
        close_price=111.0,
        volume=1.0,
    )

    closed = PositionUpdateService().update_from_candles(position, [first_wick, later_wick])

    assert closed.exit_reason == ExitReason.TP_HIT
    assert closed.exit_trigger_candle_close_ms == 2_000


def test_futures_runtime_closes_on_first_wick_even_when_close_is_below_tp() -> None:
    closed = FuturesPositionService().try_close_position_from_candles(
        position={
            "position_id": "FUT-TEST",
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "side": "LONG",
            "entry_price": 100.0,
            "tp_price": 110.0,
            "sl_price": 90.0,
            "opened_at": "1970-01-01 00:00:01Z",
            "opened_at_ms": 1_000,
            "notional_usdt": 500.0,
            "margin_usdt": 100.0,
        },
        candles=[
            _candle(close_time=2_000, high=111.0, low=100.0),
            _candle(close_time=3_000, high=112.0, low=101.0),
        ],
        leverage=5,
    )

    assert closed is not None
    assert closed["outcome"] == "TP_HIT"
    assert closed["exit_trigger_candle_close_ms"] == 2_000
