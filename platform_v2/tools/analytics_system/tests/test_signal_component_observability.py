from __future__ import annotations

from dataclasses import asdict
from types import SimpleNamespace

from platform_v2.futures.config.profile import ExecutionProfile
from platform_v2.futures.services.simulation.entry_event_writer_service import (
    FuturesEntryEventWriterService,
)
from platform_v2.futures.services.signal.futures_signal_decision_service import (
    SignalDecisionService as FuturesSignalDecisionService,
)
from platform_v2.futures.config import settings as futures_settings
from platform_v2.spot.config import settings as spot_settings
from platform_v2.tools.research.replay.legacy_spot_signal import (
    SignalDecisionService as SpotSignalDecisionService,
)


COMPONENTS = {
    "mtf": 1.0,
    "regime": 0.5,
    "momentum": 0.25,
    "trend": 1.0,
    "orderbook": 0.5,
    "structure": 0.25,
}


def _context() -> SimpleNamespace:
    return SimpleNamespace(
        symbol="BTCUSDT",
        timeframe="15m",
        latest_candle=SimpleNamespace(close_time_ms=123_999),
        latest_snapshot=SimpleNamespace(
            timestamp_text="2026-07-31 12:00:00",
            price=65_000.0,
            atr_spike=False,
            atr_spike_threshold=None,
            atr=None,
        ),
        mtf_direction="NO_SIGNAL",
        mtf_signals={"5m": "NO_SIGNAL", "15m": "NO_SIGNAL", "4h": "NO_SIGNAL"},
    )


class _SpotProbe(SpotSignalDecisionService):
    @staticmethod
    def _build_buy_component_scores(context: object) -> dict[str, float]:
        return dict(COMPONENTS)


class _FuturesComponents:
    @staticmethod
    def atr_spike_block(snapshot: object) -> bool:
        return False

    @staticmethod
    def build_long_component_scores(context: object) -> dict[str, float]:
        return dict(COMPONENTS)

    @staticmethod
    def build_short_component_scores(context: object) -> dict[str, float]:
        return {key: value / 2 for key, value in COMPONENTS.items()}


def test_spot_decision_keeps_raw_component_scores() -> None:
    decision = _SpotProbe().build_signal(_context())

    assert decision.component_scores == COMPONENTS
    assert decision.strategy_version == "spot-legacy-score-baseline"
    assert decision.component_weights == spot_settings.SIGNAL_COMPONENT_WEIGHTS
    persisted = asdict(decision)
    assert persisted["strategy_version"] == "spot-legacy-score-baseline"
    assert persisted["component_weights"] == spot_settings.SIGNAL_COMPONENT_WEIGHTS


def test_futures_decision_keeps_both_direction_component_scores() -> None:
    decision = FuturesSignalDecisionService(
        component_score_service=_FuturesComponents()
    ).build_signal(_context())

    assert decision.direction_component_scores["long"] == COMPONENTS
    assert decision.direction_component_scores["short"] == {
        key: value / 2 for key, value in COMPONENTS.items()
    }
    assert decision.strategy_version == futures_settings.STRATEGY_VERSION
    assert decision.direction_thresholds == {
        "long": futures_settings.BUY_THRESHOLD,
        "short": futures_settings.BUY_THRESHOLD,
    }
    assert decision.direction_component_weights == {
        "long": futures_settings.SIGNAL_COMPONENT_WEIGHTS,
        "short": futures_settings.SIGNAL_COMPONENT_WEIGHTS,
    }


class _CaptureRuntimeStore:
    def __init__(self) -> None:
        self.row: dict[str, object] | None = None

    def upsert_daily_row(self, *, row: dict[str, object], **_: object) -> None:
        self.row = row


def test_futures_signal_writer_persists_strategy_lineage() -> None:
    decision = FuturesSignalDecisionService(
        component_score_service=_FuturesComponents()
    ).build_signal(_context())
    store = _CaptureRuntimeStore()
    writer = FuturesEntryEventWriterService(
        runtime_store=store,
        state_store=SimpleNamespace(),
        position_service=SimpleNamespace(),
    )
    profile = ExecutionProfile(
        market="futures",
        mode="simulation",
        symbol="BTCUSDT",
        timeframe="15m",
        leverage=5,
        margin_mode="isolated",
        order_size_usdt=100.0,
        starting_balance=3_000.0,
    )

    writer.store_signal_row(
        profile=profile,
        date_iso="2026-07-31",
        decision=decision,
        signal_side=decision.side.value,
        permission=SimpleNamespace(allowed=False, reason="signal_block", checks={}),
        entry_quality_payload={},
        market_plan_permission={},
        entry_location_permission={},
        latest_ts=123_999,
        latest_time="2026-07-31 12:00:00",
        latest_candle_open_time="2026-07-31 11:45:00",
        latest_candle_close_time="2026-07-31 11:59:59",
        latest_decision_time="2026-07-31 12:00:00",
    )

    assert store.row is not None
    assert store.row["strategy_version"] == futures_settings.STRATEGY_VERSION
    assert store.row["direction_thresholds"] == {
        "long": futures_settings.BUY_THRESHOLD,
        "short": futures_settings.BUY_THRESHOLD,
    }
    assert store.row["direction_component_weights"] == {
        "long": futures_settings.SIGNAL_COMPONENT_WEIGHTS,
        "short": futures_settings.SIGNAL_COMPONENT_WEIGHTS,
    }
