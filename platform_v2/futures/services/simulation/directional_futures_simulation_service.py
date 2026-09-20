"""File: directional_futures_simulation_service.py
Folder: platform_v2/futures/services/simulation
Created date: 2026-03-25
Last updated date: 2026-06-02
Author: Codex
Purpose: Run the directional Futures simulation loop with permission checks.
"""

from __future__ import annotations

from typing import Any

from platform_v2.futures.domain.models.signal import GateSnapshot, SignalDecision, SignalSide
from platform_v2.futures.domain.models.market_context import MarketContext
from platform_v2.futures.domain.models.position import ExecutionSetup
from platform_v2.futures.config import ExecutionProfile
from platform_v2.futures.config import settings
from platform_v2.futures.services.permission import (
    FuturesPermissionDecision,
    FuturesPermissionDecisionService,
)
from platform_v2.futures.services.signal import FuturesMarketContextService, SignalDecisionService
from platform_v2.futures.services.trading.futures_sl_tp_service import StopLossTakeProfitService
from platform_v2.shared.backend.market import BinanceQuoteService, MarketQuote
from platform_v2.shared.backend.time import utc_now_ms
from platform_v2.shared.runtime_warnings import warn_runtime_fallback

from .common import as_optional_float, ms_to_text
from .cycle_summary_builder import FuturesCycleSummaryBuilder
from .entry_event_writer_service import FuturesEntryEventWriterService
from .entry_quality_service import FuturesEntryQualityService
from .entry_permission_context_service import FuturesEntryPermissionContextService
from .metrics_service import FuturesMetricsService
from .models import FuturesCycleSummary
from .position_lifecycle_service import FuturesPositionLifecycleService
from .position_service import FuturesPositionService
from .runtime_store import FuturesSimulationRuntimeStore
from .state_store import FuturesSimulationStateStore


class DirectionalFuturesSimulationService:
    def __init__(self, *, quote_service: BinanceQuoteService | None = None) -> None:
        self._permission_service = FuturesPermissionDecisionService()
        self._market_context_service = FuturesMarketContextService()
        self._signal_decision_service = SignalDecisionService()
        self._runtime_store = FuturesSimulationRuntimeStore()
        self._state_store = FuturesSimulationStateStore()
        self._position_service = FuturesPositionService()
        self._quote_service = quote_service or BinanceQuoteService()
        self._sl_tp_service = StopLossTakeProfitService()
        self._metrics_service = FuturesMetricsService(runtime_store=self._runtime_store)
        self._entry_quality_service = FuturesEntryQualityService()
        self._entry_permission_context_service = FuturesEntryPermissionContextService(
            runtime_store=self._runtime_store,
        )
        self._position_lifecycle_service = FuturesPositionLifecycleService(
            runtime_store=self._runtime_store,
            state_store=self._state_store,
            position_service=self._position_service,
        )
        self._entry_event_writer_service = FuturesEntryEventWriterService(
            runtime_store=self._runtime_store,
            state_store=self._state_store,
            position_service=self._position_service,
        )

    def run(self, *, profile: ExecutionProfile, date_iso: str) -> FuturesCycleSummary:
        candles = self._runtime_store.load_candles(symbol=profile.symbol, timeframe=profile.timeframe)
        exit_candles = self._runtime_store.load_candles(
            symbol=profile.symbol,
            timeframe=settings.EXIT_MONITORING_TIMEFRAME,
        )
        if not exit_candles:
            exit_candles = candles

        if len(candles) < 25:
            metrics = self._metrics_service.build_minimal(profile=profile)
            metrics_path = self._runtime_store.store_metrics(metrics=metrics, date_iso=date_iso)
            return FuturesCycleSummary(
                signal="NO_SIGNAL",
                position_event="NO_DATA",
                open_positions=int(metrics.get("open_positions", 0)),
                equity=float(metrics.get("equity", profile.starting_balance)),
                total_net_pnl=float(metrics.get("total_net_pnl", 0.0)),
                total_gross_pnl=float(metrics.get("total_gross_pnl", 0.0)),
                total_fees_paid=float(metrics.get("total_fees_paid", 0.0)),
                unrealized_pnl=float(metrics.get("unrealized_pnl", 0.0)),
                net_return_pct=float(metrics.get("net_return_pct", 0.0)),
                peak_capital=float(metrics.get("peak_capital", profile.starting_balance)),
                lowest_capital=float(metrics.get("lowest_capital", profile.starting_balance)),
                signal_to_trade_conversion=float(metrics.get("signal_to_trade_conversion", 0.0)),
                force_closes_by_reason=dict(metrics.get("force_closes_by_reason") or {}),
                score=0.0,
                threshold=0.0,
                direction_scores={"long": 0.0, "short": 0.0},
                mtf_direction="NO_DATA",
                gates=FuturesCycleSummaryBuilder.serialize_gates(GateSnapshot()),
                permission_status="DENIED",
                permission_reason="no_data",
                permission_text="No data yet. Waiting for enough candles to evaluate a setup.",
                metrics_path=metrics_path,
            )

        state = self._state_store.load()
        latest = candles[-1]
        latest_close = float(latest.get("close") or 0.0)
        latest_ts = int(latest.get("close_time") or latest.get("timestamp") or 0)
        latest_time = ms_to_text(latest_ts) if latest_ts > 0 else str(latest.get("time_readable") or "")
        latest_candle_open_time = str(latest.get("time_readable") or "")
        latest_candle_close_time = latest_time
        latest_decision_time = latest_time

        latest_exit = exit_candles[-1]
        latest_exit_close = float(latest_exit.get("close") or latest_close)
        latest_exit_ts = int(latest_exit.get("close_time") or latest_exit.get("timestamp") or latest_ts)
        latest_exit_time = ms_to_text(latest_exit_ts) if latest_exit_ts > 0 else str(latest_exit.get("time_readable") or latest_time)

        position_event = self._position_lifecycle_service.process_existing_positions(
            state=state,
            profile=profile,
            date_iso=date_iso,
            exit_candles=exit_candles,
        )

        market_context = self._market_context_service.build_context(
            symbol=profile.symbol,
            timeframe=profile.timeframe,
        )
        decision = self._build_signal_decision(
            symbol=profile.symbol,
            timeframe=profile.timeframe,
            latest_ts=latest_ts,
            latest_close=latest_close,
            context=market_context,
        )
        signal_side = str(decision.selected_direction or decision.side.value)
        execution_quote, quote_error = self._execution_quote(
            symbol=profile.symbol,
            signal_side=signal_side,
        )
        execution_price = execution_quote.price if execution_quote is not None else latest_close
        decision_ts = (
            execution_quote.observed_at_ms if execution_quote is not None else utc_now_ms()
        )
        latest_decision_time = ms_to_text(decision_ts)
        execution_setup = self._build_execution_setup(
            decision=decision,
            context=market_context,
            execution_price=execution_price,
            position_size=profile.order_size_usdt,
        )

        open_positions_after_exit = self._state_store.open_positions(state)
        same_direction_positions = self._positions_for_direction(open_positions_after_exit, signal_side)
        # Spot-parity exposure model: permission exposure is capital allocated (margin), not leveraged notional.
        current_open_exposure = sum(
            float(position.get("margin_usdt", 0.0) or 0.0) for position in open_positions_after_exit
        )
        reserved_capital = sum(
            float(position.get("margin_usdt", 0.0) or 0.0) for position in open_positions_after_exit
        )
        open_entry_fee = sum(
            float(position.get("entry_fee_paid", 0.0) or 0.0) for position in open_positions_after_exit
        )
        total_net_pnl_now = float(state.get("stats", {}).get("total_net_pnl", 0.0))
        available_balance = profile.starting_balance + total_net_pnl_now - reserved_capital - open_entry_fee
        latest_opened_at_ms = max(
            (
                int(position.get("opened_at_ms") or 0)
                for position in same_direction_positions
                if int(position.get("opened_at_ms") or 0) > 0
            ),
            default=0,
        )
        cooldown_active = (
            latest_opened_at_ms > 0
            and decision_ts < (latest_opened_at_ms + settings.DEFAULT_COOLDOWN_SECONDS * 1000)
        )

        order_exposure_usdt = float(profile.order_size_usdt)
        duplicate_active = any(
            abs(float(position.get("entry_price") or 0.0) - execution_price) < 0.0001
            for position in same_direction_positions
        )
        last_same_direction_entry_price = self._latest_entry_price(same_direction_positions)
        prior_signal_rows = self._runtime_store.load_family_rows_all(family_name="futures_signals")
        market_plan_permission = self._entry_permission_context_service.market_plan_permission(
            signal_side=signal_side,
            entry_price=execution_price,
            timestamp_ms=latest_ts,
        )
        entry_quality = self._entry_quality_service.evaluate(
            signal_side=signal_side,
            timestamp_ms=latest_ts,
            prior_signals=prior_signal_rows,
            market_plan_permission=market_plan_permission,
        )
        entry_quality_permission = self._entry_permission_context_service.apply_entry_quality_override(
            signal_side=signal_side,
            entry_quality={
                "allowed": entry_quality.allowed,
                "timing_type": entry_quality.timing_type,
                "direction_signal_age": entry_quality.direction_signal_age,
                "prior_actionable_side": entry_quality.prior_actionable_side,
                "flip_confirmation_status": entry_quality.flip_confirmation_status,
                "reason": entry_quality.reason,
            },
            gates=decision.gates,
            score=float(decision.score),
        )
        market_plan_permission = self._entry_permission_context_service.apply_short_continuation_override(
            signal_side=signal_side,
            market_plan_permission=market_plan_permission,
            entry_price=execution_price,
            entry_quality=entry_quality_permission,
            gates=decision.gates,
            score=float(decision.score),
        )
        entry_location_permission = self._entry_permission_context_service.entry_location_permission(
            signal_side=signal_side,
            symbol=profile.symbol,
            timeframe=profile.timeframe,
            entry_price=execution_price,
        )
        permission = self._permission_service.evaluate(
            signal_side=signal_side,
            entry_price=execution_price,
            stop_loss=(execution_setup.stop_loss if execution_setup is not None else None),
            leverage=profile.leverage,
            order_notional_usdt=order_exposure_usdt,
            available_balance=available_balance,
            current_open_exposure=current_open_exposure,
            last_entry_price=last_same_direction_entry_price,
            manual_block=bool(state.get("manual_entry_block", False)),
            cooldown_active=cooldown_active,
            duplicate_active=duplicate_active,
            entry_quality_ok=bool(entry_quality_permission.get("allowed", entry_quality.allowed)),
            entry_quality_reason=str(
                entry_quality_permission.get("reason") or entry_quality.reason
            ),
            long_entry_location_ok=bool(entry_location_permission.get("allowed", True)),
            short_market_plan_ok=bool(market_plan_permission.get("allowed", True)),
            current_open_positions=len(open_positions_after_exit),
            current_direction_open_positions=len(same_direction_positions),
        )
        if signal_side in {"LONG", "SHORT"} and execution_quote is None:
            permission = FuturesPermissionDecision(
                allowed=False,
                reason="execution_quote_unavailable",
                checks={**permission.checks, "execution_quote": False},
            )
        elif execution_quote is not None:
            permission = FuturesPermissionDecision(
                allowed=permission.allowed,
                reason=permission.reason,
                checks={**permission.checks, "execution_quote": True},
            )

        entry_quality_payload = self._entry_event_writer_service.entry_quality_payload(
            entry_quality=entry_quality,
            entry_quality_permission=entry_quality_permission,
        )
        self._entry_event_writer_service.store_signal_row(
            profile=profile,
            date_iso=date_iso,
            decision=decision,
            signal_side=signal_side,
            permission=permission,
            entry_quality_payload=entry_quality_payload,
            market_plan_permission=market_plan_permission,
            entry_location_permission=entry_location_permission,
            latest_ts=latest_ts,
            latest_time=latest_time,
            latest_candle_open_time=latest_candle_open_time,
            latest_candle_close_time=latest_candle_close_time,
            latest_decision_time=latest_decision_time,
            signal_reference_price=latest_close,
            execution_quote=execution_quote,
            quote_error=quote_error,
        )

        if signal_side in {"LONG", "SHORT"} and not permission.allowed:
            self._entry_event_writer_service.append_denied_entry(
                profile=profile,
                date_iso=date_iso,
                decision=decision,
                signal_side=signal_side,
                permission=permission,
                entry_quality_payload=entry_quality_payload,
                market_plan_permission=market_plan_permission,
                entry_location_permission=entry_location_permission,
                latest_ts=latest_ts,
                latest_time=latest_time,
                latest_candle_open_time=latest_candle_open_time,
                latest_candle_close_time=latest_candle_close_time,
                latest_decision_time=latest_decision_time,
                latest_close=execution_price,
                signal_reference_price=latest_close,
                execution_quote=execution_quote,
                execution_setup=execution_setup,
                quote_error=quote_error,
                available_balance=available_balance,
                current_open_exposure=current_open_exposure,
                order_exposure_usdt=order_exposure_usdt,
            )
            position_event = f"ENTRY_DENIED:{permission.reason.upper()}"
            state["last_position_event"] = position_event

        if signal_side in {"LONG", "SHORT"} and permission.allowed:
            self._entry_event_writer_service.open_position(
                state=state,
                profile=profile,
                date_iso=date_iso,
                decision=decision,
                signal_side=signal_side,
                latest_close=execution_price,
                latest_ts=decision_ts,
                latest_time=latest_decision_time,
                latest_candle_open_time=latest_candle_open_time,
                latest_candle_close_time=latest_candle_close_time,
                latest_decision_time=latest_decision_time,
                signal_reference_price=latest_close,
                execution_quote=execution_quote,
                execution_setup=execution_setup,
            )
            position_event = "OPENED"
            state["last_position_event"] = position_event

        metrics = self._metrics_service.build(
            state=state,
            profile=profile,
            date_iso=date_iso,
            latest_close=latest_exit_close,
            latest_time=latest_exit_time,
            signal_side=signal_side,
            open_positions_payload=self._state_store.open_positions(state),
        )
        metrics_path = self._runtime_store.store_metrics(metrics=metrics, date_iso=date_iso)
        self._position_lifecycle_service.write_open_position_state_updates(
            date_iso=date_iso,
            open_positions=self._state_store.open_positions(state),
            latest_close=latest_exit_close,
            ts_ms=latest_exit_ts,
            time_text=latest_exit_time,
        )
        self._state_store.save(state)

        return FuturesCycleSummaryBuilder.build(
            metrics=metrics,
            profile=profile,
            decision=decision,
            signal_side=signal_side,
            position_event=position_event,
            permission=permission,
            metrics_path=metrics_path,
        )

    def _execution_quote(
        self,
        *,
        symbol: str,
        signal_side: str,
    ) -> tuple[MarketQuote | None, str | None]:
        if signal_side not in {"LONG", "SHORT"}:
            return None, None
        try:
            return self._quote_service.fetch(symbol=symbol, market_type="futures"), None
        except Exception as exc:
            warn_runtime_fallback(
                scope="directional_futures_simulation_service",
                operation="fetch_execution_quote",
                error=exc,
                fallback="deny_new_entry",
                extra={"symbol": symbol, "signal_side": signal_side},
            )
            return None, str(exc)

    def _build_execution_setup(
        self,
        *,
        decision: SignalDecision,
        context: MarketContext | None,
        execution_price: float,
        position_size: float,
    ) -> ExecutionSetup | None:
        if context is None or decision.side == SignalSide.NO_SIGNAL:
            return None
        confidence = min(1.0, max(0.0, float(decision.score) / 14.6))
        return self._sl_tp_service.build_execution_setup(
            side=decision.side,
            live_entry_price=execution_price,
            snapshot=context.latest_snapshot,
            position_size=position_size,
            confidence=confidence,
        )

    def _build_signal_decision(
        self,
        *,
        symbol: str,
        timeframe: str,
        latest_ts: int,
        latest_close: float,
        context: MarketContext | None,
    ) -> SignalDecision:
        if context is not None:
            try:
                return self._signal_decision_service.build_signal(context=context, timestamp_ms=latest_ts)
            except Exception as exc:
                warn_runtime_fallback(
                    scope="directional_futures_simulation_service",
                    operation="build_signal_decision",
                    error=exc,
                    fallback="return_no_signal",
                    extra={"symbol": symbol, "timeframe": timeframe, "latest_ts": latest_ts},
                )
        fallback_reasons: tuple[str, ...] = ("Futures fallback: no context",)
        fallback_mtf_signals: dict[str, str] = {}
        return SignalDecision(
            timestamp_ms=latest_ts,
            symbol=symbol,
            timeframe=timeframe,
            side=SignalSide.NO_SIGNAL,
            snapshot_price=latest_close,
            score=0.0,
            threshold=0.0,
            gates=GateSnapshot(),
            reasons=fallback_reasons,
            mtf_signals=fallback_mtf_signals,
            mtf_direction="NO_SIGNAL",
            theoretical_setup=None,
            selected_direction="NO_SIGNAL",
            direction_scores={"long": 0.0, "short": 0.0},
            direction_gates={"long": GateSnapshot(), "short": GateSnapshot()},
            direction_reasons={"long": fallback_reasons, "short": fallback_reasons},
        )

    @classmethod
    def _positions_for_direction(
        cls,
        open_positions: list[dict[str, Any]],
        direction: str,
    ) -> list[dict[str, Any]]:
        normalized_direction = cls._normalize_direction(direction)
        if normalized_direction not in {"LONG", "SHORT"}:
            return []
        return [
            position
            for position in open_positions
            if cls._position_side(position) == normalized_direction
        ]

    @classmethod
    def _latest_entry_price(cls, positions: list[dict[str, Any]]) -> float | None:
        latest_position = max(
            positions,
            key=lambda position: int(position.get("opened_at_ms") or 0),
            default=None,
        )
        if latest_position is None:
            return None
        return as_optional_float(latest_position.get("entry_price"))

    @classmethod
    def _position_side(cls, position: dict[str, Any]) -> str:
        return cls._normalize_direction(str(position.get("side") or "LONG"))

    @staticmethod
    def _normalize_direction(direction: str) -> str:
        normalized = str(direction or "").upper()
        if normalized == "BUY":
            return "LONG"
        if normalized == "SELL":
            return "SHORT"
        return normalized
