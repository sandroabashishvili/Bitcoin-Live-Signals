from platform_v2.futures.services.simulation.position_exit_resolver import (
    LONG_PROFIT_LOCK_70_25,
    build_position_management,
    resolve_position_exit,
)
from platform_v2.futures.services.simulation.position_service import FuturesPositionService
from platform_v2.futures.services.analytics.futures_strategy_effectiveness import (
    StrategyEffectivenessService,
)


def _candle(timestamp: int, *, high: float, low: float, close: float = 105.0) -> dict:
    return {
        "close_time": timestamp,
        "timestamp": timestamp,
        "time_readable": str(timestamp),
        "high": high,
        "low": low,
        "close": close,
    }


def _long_position(*, managed: bool = True) -> dict:
    position = {
        "position_id": "FUT-TEST",
        "side": "LONG",
        "entry_price": 100.0,
        "tp_price": 120.0,
        "sl_price": 90.0,
        "notional_usdt": 500.0,
        "margin_usdt": 100.0,
        "opened_at_ms": 1,
        "opened_at": "test",
    }
    if managed:
        position["position_management"] = build_position_management(
            side="LONG", entry=100.0, take_profit=120.0
        )
    return position


def test_new_long_position_gets_declared_profit_lock_levels() -> None:
    management = build_position_management(side="LONG", entry=100.0, take_profit=120.0)

    assert management == {
        "policy": LONG_PROFIT_LOCK_70_25,
        "activation_fraction": 0.7,
        "lock_fraction": 0.25,
        "activation_price": 114.0,
        "protected_stop": 105.0,
        "effective_from": "next_closed_1m_candle",
    }
    assert build_position_management(side="SHORT", entry=100.0, take_profit=80.0) is None


def test_profit_lock_activates_only_from_next_closed_candle() -> None:
    trigger = resolve_position_exit(
        position=_long_position(),
        candles=[
            _candle(10, high=115.0, low=103.0),
            _candle(20, high=110.0, low=104.0),
        ],
    )

    assert trigger is not None
    assert trigger.outcome == "PROFIT_LOCK_HIT"
    assert trigger.exit_price == 105.0
    assert trigger.candle["close_time"] == 20


def test_existing_position_without_policy_keeps_original_fixed_stop() -> None:
    trigger = resolve_position_exit(
        position=_long_position(managed=False),
        candles=[
            _candle(10, high=115.0, low=103.0),
            _candle(20, high=110.0, low=104.0),
        ],
    )

    assert trigger is None


def test_close_event_and_stats_record_profit_lock_separately() -> None:
    service = FuturesPositionService()
    event = service.try_close_position_from_candles(
        position=_long_position(),
        candles=[
            _candle(10, high=115.0, low=103.0),
            _candle(20, high=110.0, low=104.0),
        ],
        leverage=5,
    )
    state = {"stats": {}}

    assert event is not None
    assert event["outcome"] == "PROFIT_LOCK_HIT"
    assert event["exit_reason"] == "profit_lock_hit"
    assert event["management_policy_applied"] == LONG_PROFIT_LOCK_70_25
    assert event["net_pnl"] > 0

    service.apply_close_stats(state, event)
    assert state["stats"]["closed_positions"] == 1
    assert state["stats"]["profit_lock_hits"] == 1
    assert state["stats"].get("tp_hits", 0) == 0
    assert state["stats"].get("sl_hits", 0) == 0


def test_trade_analytics_preserve_profit_lock_as_its_own_outcome() -> None:
    signal = {
        "timestamp_ms": 1,
        "side": "LONG",
        "gates": {name: True for name in ("mtf", "regime", "momentum", "trend", "orderbook", "structure")},
    }
    events = [
        {"event": "OPENED", "position_id": "FUT-TEST", "timestamp_ms": 1, "side": "LONG"},
        {
            "event": "CLOSED",
            "position_id": "FUT-TEST",
            "timestamp_ms": 2,
            "side": "LONG",
            "outcome": "PROFIT_LOCK_HIT",
            "net_pnl": 1.0,
        },
    ]

    payload = StrategyEffectivenessService().build_closed_trade_logic_evaluation_from_events(
        signal_rows=[signal],
        position_rows=events,
    )

    assert payload["closed_trade_summary"]["profit_lock_hits"] == 1
    assert payload["closed_trade_summary"]["win_rate"] == 100.0
    assert payload["long_primary_totals"]["profit_lock"] == 3
