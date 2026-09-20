"""File: entry_event_writer_service.py
Folder: platform_v2/futures/services/simulation
Created date: 2026-06-01
Last updated date: 2026-06-02
Author: Codex
Purpose: Persist Futures entry signal, denial, and open-position event rows.
"""

from __future__ import annotations

from typing import Any

from platform_v2.futures.config import ExecutionProfile
from platform_v2.futures.domain.models.signal import GateSnapshot, SignalDecision
from platform_v2.futures.domain.models.position import ExecutionSetup
from platform_v2.shared.backend.market import MarketQuote
from platform_v2.shared.backend.runtime_store.futures import POSITION_EVENTS_FAMILY

from .permission_text import human_permission_text
from .position_service import FuturesPositionService
from .runtime_store import FuturesSimulationRuntimeStore
from .state_store import FuturesSimulationStateStore


class FuturesEntryEventWriterService:
    """Write signal, denied-entry, and opened-position rows for one cycle."""

    def __init__(
        self,
        *,
        runtime_store: FuturesSimulationRuntimeStore,
        state_store: FuturesSimulationStateStore,
        position_service: FuturesPositionService,
    ) -> None:
        self._runtime_store = runtime_store
        self._state_store = state_store
        self._position_service = position_service

    def store_signal_row(
        self,
        *,
        profile: ExecutionProfile,
        date_iso: str,
        decision: SignalDecision,
        signal_side: str,
        permission: Any,
        entry_quality_payload: dict[str, Any],
        market_plan_permission: dict[str, Any],
        entry_location_permission: dict[str, Any],
        latest_ts: int,
        latest_time: str,
        latest_candle_open_time: str,
        latest_candle_close_time: str,
        latest_decision_time: str,
        signal_reference_price: float = 0.0,
        execution_quote: MarketQuote | None = None,
        quote_error: str | None = None,
    ) -> None:
        self._runtime_store.upsert_daily_row(
            family_name="futures_signals",
            date_iso=date_iso,
            row={
                "timestamp_ms": latest_ts,
                "signal_timestamp_ms": self._signal_timestamp_ms(
                    latest_candle_close_time
                ),
                "time_readable": latest_time,
                "candle_open_time": latest_candle_open_time,
                "candle_close_time": latest_candle_close_time,
                "decision_time": latest_decision_time,
                "signal_reference_price": round(signal_reference_price, 2),
                "execution_quote_price": (
                    round(execution_quote.price, 2) if execution_quote is not None else None
                ),
                "execution_quote_time_ms": (
                    execution_quote.observed_at_ms if execution_quote is not None else None
                ),
                "execution_quote_source": (
                    execution_quote.source if execution_quote is not None else None
                ),
                "execution_quote_error": quote_error,
                "symbol": profile.symbol,
                "timeframe": profile.timeframe,
                "side": signal_side,
                "score": round(float(decision.score), 2),
                "threshold": round(float(decision.threshold), 2),
                "selected_direction": signal_side,
                "direction_scores": self._direction_scores(decision),
                "direction_gates": self._serialize_direction_gates(decision.direction_gates),
                "direction_component_scores": self._direction_component_scores(decision),
                "strategy_version": str(decision.strategy_version),
                "direction_thresholds": {
                    direction: round(float(value), 4)
                    for direction, value in decision.direction_thresholds.items()
                },
                "direction_component_weights": {
                    direction: {
                        key: round(float(value), 4)
                        for key, value in weights.items()
                    }
                    for direction, weights in decision.direction_component_weights.items()
                },
                "mtf_signals": dict(decision.mtf_signals),
                "mtf_direction": str(decision.mtf_direction),
                "gates": self._serialize_gates(decision.gates),
                "permission_status": "ALLOWED" if permission.allowed else "DENIED",
                "permission_reason": permission.reason,
                "permission_checks": permission.checks,
                "entry_quality": entry_quality_payload,
                "market_plan_permission": market_plan_permission,
                "entry_location_permission": entry_location_permission,
                "permission_text": human_permission_text(
                    reason=permission.reason,
                    checks=permission.checks,
                ),
                "theoretical_setup": self._theoretical_setup(decision),
                "market": "futures",
                "mode": profile.mode,
                "leverage": profile.leverage,
            },
            match_keys=("timestamp_ms", "symbol", "timeframe"),
        )

    def append_denied_entry(
        self,
        *,
        profile: ExecutionProfile,
        date_iso: str,
        decision: SignalDecision,
        signal_side: str,
        permission: Any,
        entry_quality_payload: dict[str, Any],
        market_plan_permission: dict[str, Any],
        entry_location_permission: dict[str, Any],
        latest_ts: int,
        latest_time: str,
        latest_candle_open_time: str,
        latest_candle_close_time: str,
        latest_decision_time: str,
        latest_close: float,
        signal_reference_price: float,
        execution_quote: MarketQuote | None,
        execution_setup: ExecutionSetup | None,
        quote_error: str | None,
        available_balance: float,
        current_open_exposure: float,
        order_exposure_usdt: float,
    ) -> None:
        self._runtime_store.append_daily_row(
            family_name="futures_denied_entries",
            date_iso=date_iso,
            row={
                "timestamp_ms": latest_ts,
                "time_readable": latest_time,
                "candle_open_time": latest_candle_open_time,
                "candle_close_time": latest_candle_close_time,
                "signal_timestamp_ms": self._signal_timestamp_ms(
                    latest_candle_close_time
                ),
                "decision_time": latest_decision_time,
                "signal_reference_price": round(signal_reference_price, 2),
                "execution_quote_price": (
                    round(execution_quote.price, 2) if execution_quote is not None else None
                ),
                "execution_quote_time_ms": (
                    execution_quote.observed_at_ms if execution_quote is not None else None
                ),
                "execution_quote_source": (
                    execution_quote.source if execution_quote is not None else None
                ),
                "execution_quote_error": quote_error,
                "execution_setup": self._execution_setup_payload(execution_setup),
                "symbol": profile.symbol,
                "timeframe": profile.timeframe,
                "reason": permission.reason,
                "checks": permission.checks,
                "permission_text": human_permission_text(
                    reason=permission.reason,
                    checks=permission.checks,
                ),
                "entry_quality": entry_quality_payload,
                "market_plan_permission": market_plan_permission,
                "entry_location_permission": entry_location_permission,
                "entry_price": latest_close,
                "signal_side": signal_side,
                "signal_score": round(float(decision.score), 2),
                "selected_direction": signal_side,
                "direction_scores": self._direction_scores(decision),
                "available_balance": round(available_balance, 2),
                "current_open_exposure": round(current_open_exposure, 2),
                "order_exposure_usdt": round(order_exposure_usdt, 2),
                "order_notional_usdt": round(float(profile.order_size_usdt * profile.leverage), 2),
            },
        )

    def open_position(
        self,
        *,
        state: dict[str, Any],
        profile: ExecutionProfile,
        date_iso: str,
        decision: SignalDecision,
        signal_side: str,
        latest_close: float,
        latest_ts: int,
        latest_time: str,
        latest_candle_open_time: str,
        latest_candle_close_time: str,
        latest_decision_time: str,
        signal_reference_price: float,
        execution_quote: MarketQuote,
        execution_setup: ExecutionSetup | None,
    ) -> dict[str, Any]:
        new_position = self._position_service.build_open_position(
            state=state,
            profile=profile,
            decision=decision,
            entry_price=latest_close,
            ts_ms=latest_ts,
            time_text=latest_time,
            candle_open_time=latest_candle_open_time,
            candle_close_time=latest_candle_close_time,
            decision_time=latest_decision_time,
            signal_reference_price=signal_reference_price,
            execution_quote_source=execution_quote.source,
            execution_setup=execution_setup,
        )
        positions_now = self._state_store.open_positions(state)
        positions_now.append(new_position)
        self._state_store.set_open_positions(state, positions_now)
        state["last_entry_price"] = new_position["entry_price"]
        state["last_entry_ts_ms"] = latest_ts
        direction_key = str(new_position.get("side") or signal_side).lower()
        state[f"last_{direction_key}_entry_price"] = new_position["entry_price"]
        state[f"last_{direction_key}_entry_ts_ms"] = latest_ts
        state["stats"]["total_positions"] = int(state["stats"].get("total_positions", 0)) + 1

        open_row = self._open_position_row(
            profile=profile,
            new_position=new_position,
            latest_ts=latest_ts,
            latest_time=latest_time,
            latest_candle_open_time=latest_candle_open_time,
            latest_candle_close_time=latest_candle_close_time,
            latest_decision_time=latest_decision_time,
            signal_reference_price=signal_reference_price,
            execution_quote=execution_quote,
        )
        self._runtime_store.append_daily_row(
            family_name=POSITION_EVENTS_FAMILY,
            date_iso=date_iso,
            row=open_row,
        )
        self._runtime_store.upsert_daily_row(
            family_name="futures_orders",
            date_iso=date_iso,
            row={
                "timestamp_ms": latest_ts,
                "signal_timestamp_ms": self._signal_timestamp_ms(
                    latest_candle_close_time
                ),
                "time_readable": latest_time,
                "candle_open_time": latest_candle_open_time,
                "candle_close_time": latest_candle_close_time,
                "decision_time": latest_decision_time,
                "signal_reference_price": round(signal_reference_price, 2),
                "execution_quote_time_ms": execution_quote.observed_at_ms,
                "execution_quote_source": execution_quote.source,
                "symbol": profile.symbol,
                "timeframe": profile.timeframe,
                "status": "FILLED",
                "side": "BUY" if signal_side == "LONG" else "SELL",
                "position_side": signal_side,
                "event": "OPENED",
                "position_id": new_position["position_id"],
                "entry_price": new_position["entry_price"],
                "stop_loss": new_position["sl_price"],
                "take_profit": new_position["tp_price"],
                "margin_usdt": profile.order_size_usdt,
                "notional_usdt": new_position["notional_usdt"],
                "leverage": profile.leverage,
                "market": "futures",
                "mode": profile.mode,
            },
            match_keys=("position_id", "event", "timestamp_ms"),
        )
        return new_position

    @staticmethod
    def entry_quality_payload(
        *,
        entry_quality: Any,
        entry_quality_permission: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "allowed": bool(entry_quality_permission.get("allowed", entry_quality.allowed)),
            "timing_type": entry_quality.timing_type,
            "direction_signal_age": entry_quality.direction_signal_age,
            "prior_actionable_side": entry_quality.prior_actionable_side,
            "flip_confirmation_status": entry_quality.flip_confirmation_status,
            "reason": str(entry_quality_permission.get("reason") or entry_quality.reason),
            "original_allowed": entry_quality.allowed,
            "override": entry_quality_permission.get("override"),
        }

    @classmethod
    def _open_position_row(
        cls,
        *,
        profile: ExecutionProfile,
        new_position: dict[str, Any],
        latest_ts: int,
        latest_time: str,
        latest_candle_open_time: str,
        latest_candle_close_time: str,
        latest_decision_time: str,
        signal_reference_price: float,
        execution_quote: MarketQuote,
    ) -> dict[str, Any]:
        return {
            "event": "OPENED",
            "position_id": new_position["position_id"],
            "status": "OPEN",
            "timestamp_ms": latest_ts,
            "time_readable": latest_time,
            "candle_open_time": latest_candle_open_time,
            "candle_close_time": latest_candle_close_time,
            "decision_time": latest_decision_time,
            "signal_reference_price": round(signal_reference_price, 2),
            "execution_quote_time_ms": execution_quote.observed_at_ms,
            "execution_quote_source": execution_quote.source,
            "opened_at": latest_time,
            "opened_at_ms": latest_ts,
            "closed_at": None,
            "symbol": profile.symbol,
            "timeframe": profile.timeframe,
            "side": new_position.get("side") or "LONG",
            "entry_price": new_position["entry_price"],
            "exit_price": None,
            "exit_reason": None,
            "pnl": None,
            "net_pnl": None,
            "unrealized_pnl": 0.0,
            "was_force_closed": False,
            "force_close_reason": None,
            "tp_price": new_position["tp_price"],
            "sl_price": new_position["sl_price"],
            "execution": {
                "entry_price": new_position["entry_price"],
                "stop_loss": new_position["sl_price"],
                "take_profit": new_position["tp_price"],
                "rr_ratio": new_position.get("rr_ratio"),
                "position_size": profile.order_size_usdt,
                "mode": new_position.get("setup_mode") or "futures_simulation",
            },
            "leverage": profile.leverage,
            "margin_usdt": profile.order_size_usdt,
            "notional_usdt": new_position["notional_usdt"],
            "setup_mode": new_position.get("setup_mode"),
            "rr_ratio": new_position.get("rr_ratio"),
            "position_management": new_position.get("position_management"),
        }

    @staticmethod
    def _theoretical_setup(decision: SignalDecision) -> dict[str, Any] | None:
        if decision.theoretical_setup is None:
            return None
        return {
            "entry_price": round(float(decision.theoretical_setup.entry_price), 2),
            "stop_loss": round(float(decision.theoretical_setup.stop_loss), 2),
            "take_profit": round(float(decision.theoretical_setup.take_profit), 2),
            "rr_ratio": round(float(decision.theoretical_setup.rr_ratio), 2),
            "mode": str(decision.theoretical_setup.mode),
        }

    @staticmethod
    def _execution_setup_payload(setup: ExecutionSetup | None) -> dict[str, Any] | None:
        if setup is None:
            return None
        return {
            "entry_price": round(float(setup.entry_price), 2),
            "stop_loss": round(float(setup.stop_loss), 2),
            "take_profit": round(float(setup.take_profit), 2),
            "rr_ratio": round(float(setup.rr_ratio), 2),
            "position_size": round(float(setup.position_size), 2),
            "mode": str(setup.mode),
        }

    @staticmethod
    def _signal_timestamp_ms(value: str) -> int | None:
        from datetime import UTC, datetime

        try:
            parsed = datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        except ValueError:
            return None
        return int(parsed.timestamp() * 1000) + 999

    @staticmethod
    def _direction_scores(decision: SignalDecision) -> dict[str, float]:
        return {
            key: round(float(value), 2)
            for key, value in dict(decision.direction_scores).items()
        }

    @staticmethod
    def _direction_component_scores(decision: SignalDecision) -> dict[str, dict[str, float]]:
        return {
            str(direction): {
                str(key): round(float(value), 4)
                for key, value in scores.items()
            }
            for direction, scores in dict(decision.direction_component_scores).items()
            if isinstance(scores, dict)
        }

    @staticmethod
    def _serialize_gates(gates: GateSnapshot) -> dict[str, bool]:
        return {
            "mtf": bool(gates.mtf),
            "regime": bool(gates.regime),
            "momentum": bool(gates.momentum),
            "trend": bool(gates.trend),
            "orderbook": bool(gates.orderbook),
            "structure": bool(gates.structure),
        }

    @classmethod
    def _serialize_direction_gates(cls, direction_gates: dict[str, GateSnapshot]) -> dict[str, dict[str, bool]]:
        return {
            str(direction): cls._serialize_gates(gates)
            for direction, gates in dict(direction_gates).items()
            if isinstance(gates, GateSnapshot)
        }
