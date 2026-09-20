from __future__ import annotations

import ast
import inspect
import textwrap

from platform_v2.futures.config.profile import ExecutionProfile
from platform_v2.futures.domain.models.signal import SignalDecision, SignalSide, TheoreticalSetup
from platform_v2.futures.domain.models.position import ExecutionSetup
from platform_v2.futures.services.simulation.position_service import FuturesPositionService
from platform_v2.futures.services.simulation.directional_futures_simulation_service import (
    DirectionalFuturesSimulationService,
)


def _profile() -> ExecutionProfile:
    return ExecutionProfile(
        market="futures",
        mode="simulation",
        symbol="BTCUSDT",
        timeframe="15m",
        leverage=5,
        margin_mode="isolated",
        order_size_usdt=100.0,
        starting_balance=3000.0,
    )


def test_open_position_uses_structure_aware_execution_setup_without_mechanical_rebase() -> None:
    decision = SignalDecision(
        timestamp_ms=1_000,
        symbol="BTCUSDT",
        timeframe="15m",
        side=SignalSide.SELL,
        selected_direction="SHORT",
        snapshot_price=100.0,
        score=10.0,
        threshold=8.5,
        theoretical_setup=TheoreticalSetup(
            entry_price=100.0,
            stop_loss=104.0,
            take_profit=92.0,
            rr_ratio=2.0,
            mode="adaptive_v2",
        ),
    )

    position = FuturesPositionService().build_open_position(
        state={"next_position_id": 1},
        profile=_profile(),
        decision=decision,
        entry_price=101.5,
        ts_ms=2_000,
        time_text="1970-01-01 00:00:02",
        candle_open_time="1970-01-01 00:00:00",
        candle_close_time="1970-01-01 00:00:01",
        decision_time="1970-01-01 00:00:02",
        signal_reference_price=100.0,
        execution_quote_source="binance_ticker_price",
        execution_setup=ExecutionSetup(
            entry_price=101.5,
            stop_loss=104.2,
            take_profit=94.4,
            rr_ratio=2.1,
            position_size=100.0,
            mode="adaptive_v2_structure_aware",
        ),
    )

    assert position["entry_price"] == 101.5
    assert position["sl_price"] == 104.2
    assert position["tp_price"] == 94.4
    assert position["setup_mode"] == "adaptive_v2_structure_aware"
    assert position["opened_at_ms"] == 2_000
    assert position["candle_close_time"] == "1970-01-01 00:00:01"
    assert position["decision_time"] == "1970-01-01 00:00:02"


def test_exit_filter_skips_candle_that_started_before_position_open() -> None:
    position = {"opened_at_ms": 91_000}
    candles = [
        {"timestamp": 90_000, "close_time": 94_999},
        {"timestamp": 95_000, "close_time": 99_999},
    ]

    assert FuturesPositionService.candles_after_position_open(
        position=position,
        candles=candles,
    ) == [candles[1]]


def test_runtime_open_call_forwards_structure_aware_execution_setup() -> None:
    tree = ast.parse(textwrap.dedent(inspect.getsource(DirectionalFuturesSimulationService.run)))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "open_position"
    ]

    assert len(calls) == 1
    assert "execution_setup" in {keyword.arg for keyword in calls[0].keywords}


def test_denied_entry_writer_accepts_structure_aware_execution_setup() -> None:
    import inspect

    from platform_v2.futures.services.simulation.entry_event_writer_service import (
        FuturesEntryEventWriterService,
    )

    parameters = inspect.signature(
        FuturesEntryEventWriterService.append_denied_entry
    ).parameters

    assert "execution_setup" in parameters
