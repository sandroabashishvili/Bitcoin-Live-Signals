"""File: position_service.py
Folder: platform_v2/futures/services/simulation
Created date: 2026-03-25
Last updated date: 2026-06-02
Author: Codex
Purpose: Position open/close logic for Futures simulation.
"""

from __future__ import annotations

from typing import Any

from platform_v2.futures.domain.models.signal import SignalDecision
from platform_v2.futures.domain.models.position import ExecutionSetup
from platform_v2.futures.config import ExecutionProfile
from platform_v2.futures.config import settings
from platform_v2.futures.services.account import FuturesFeeService

from .common import coerce_int, ms_to_text
from .position_exit_resolver import build_position_management, resolve_position_exit


class FuturesPositionService:
    def __init__(
        self,
        *,
        fallback_tp_pct: float = settings.FALLBACK_TP_PCT,
        fallback_sl_pct: float = settings.FALLBACK_SL_PCT,
    ) -> None:
        self._fallback_tp_pct = float(fallback_tp_pct)
        self._fallback_sl_pct = float(fallback_sl_pct)

    def try_close_position_from_candles(
        self,
        *,
        position: dict[str, Any],
        candles: list[dict[str, Any]],
        leverage: int,
    ) -> dict[str, Any] | None:
        if not candles:
            return None
        entry = float(position.get("entry_price") or 0.0)
        tp = float(position.get("tp_price") or 0.0)
        sl = float(position.get("sl_price") or 0.0)
        side = self._position_side(position)
        if entry <= 0:
            return None
        trigger = resolve_position_exit(position=position, candles=candles)
        if trigger is None:
            return None
        for candle in (trigger.candle,):
            ts_ms = coerce_int(candle.get("close_time"))
            if ts_ms <= 0:
                ts_ms = coerce_int(candle.get("timestamp"))
            time_text = ms_to_text(ts_ms) if ts_ms > 0 else str(candle.get("time_readable") or "")
            candle_open_time = str(candle.get("time_readable") or "")
            candle_close_time = time_text
            outcome = trigger.outcome
            exit_price = trigger.exit_price

            notional = float(position.get("notional_usdt") or 0.0)
            gross_pnl = self.unrealized_pct(position=position, latest_close=exit_price) * notional
            entry_fee_role = str(position.get("entry_fee_role") or FuturesFeeService.TAKER)
            entry_fee_rate = FuturesFeeService.fee_rate_for_role(entry_fee_role)
            entry_fee = FuturesFeeService.entry_fee_for_notional(notional)
            exit_fee_role = FuturesFeeService.exit_fee_role_for_reason(outcome)
            exit_fee_rate = FuturesFeeService.fee_rate_for_role(exit_fee_role)
            exit_fee = FuturesFeeService.exit_fee_for_notional_and_reason(
                notional=notional,
                exit_reason=outcome,
            )
            fees_paid = entry_fee + exit_fee
            net_pnl = gross_pnl - fees_paid
            opened_at_text = str(position.get("opened_at") or "")
            opened_at_ms = coerce_int(position.get("opened_at_ms"))
            duration_seconds = self._duration_seconds(opened_at_ms=opened_at_ms, closed_at_ms=ts_ms)
            exit_reason = self._normalize_exit_reason(outcome)
            return {
                "event": "CLOSED",
                "outcome": outcome,
                "position_id": position.get("position_id"),
                "symbol": str(position.get("symbol") or ""),
                "timeframe": str(position.get("timeframe") or ""),
                "side": side,
                "status": "CLOSED",
                "timestamp_ms": ts_ms,
                "time_readable": time_text,
                "candle_open_time": candle_open_time,
                "candle_close_time": candle_close_time,
                "decision_time": None,
                "opened_at": opened_at_text,
                "signal_candle_close_time": position.get("candle_close_time"),
                "entry_decision_time": position.get("decision_time"),
                "signal_reference_price": position.get("signal_reference_price"),
                "execution_quote_source": position.get("execution_quote_source"),
                "closed_at": ts_ms,
                "duration_seconds": duration_seconds,
                "duration_text": self._duration_text(duration_seconds),
                "entry_price": entry,
                "exit_price": round(exit_price, 2),
                "exit_reason": exit_reason,
                "gross_pnl": round(gross_pnl, 2),
                "net_pnl": round(net_pnl, 2),
                "pnl": round(net_pnl, 2),
                "fees_paid": round(fees_paid, 2),
                "entry_fee_paid": round(entry_fee, 2),
                "exit_fee_paid": round(exit_fee, 2),
                "entry_fee_role": entry_fee_role,
                "exit_fee_role": exit_fee_role,
                "entry_fee_rate": entry_fee_rate,
                "exit_fee_rate": exit_fee_rate,
                "unrealized_pnl": 0.0,
                "was_force_closed": False,
                "force_close_reason": None,
                "execution": {
                    "entry_price": round(entry, 2),
                    "stop_loss": round(sl, 2),
                    "take_profit": round(tp, 2),
                    "rr_ratio": round(float(position.get("rr_ratio") or 0.0), 2),
                    "position_size": round(float(position.get("margin_usdt") or 0.0), 2),
                    "mode": str(position.get("setup_mode") or "futures_simulation"),
                },
                "exit_check_timeframe": settings.EXIT_MONITORING_TIMEFRAME,
                "exit_trigger_candle_close_ms": ts_ms,
                "exit_trigger_price": round(exit_price, 2),
                "exit_trigger_type": exit_reason,
                "position_management": position.get("position_management"),
                "management_policy_applied": trigger.management_policy,
                "leverage": leverage,
                "market": "futures",
                "mode": "simulation",
                "opened_at_ms": opened_at_ms,
            }
        return None

    def build_open_position_state_row(
        self,
        *,
        position: dict[str, Any],
        latest_close: float,
        ts_ms: int,
        time_text: str,
        event: str = "POSITION_UPDATE",
        status: str = "OPEN",
    ) -> dict[str, Any]:
        entry = float(position.get("entry_price") or 0.0)
        margin = float(position.get("margin_usdt") or 0.0)
        notional = float(position.get("notional_usdt") or 0.0)
        unrealized_pct = self.unrealized_pct(position=position, latest_close=latest_close)
        unrealized_pnl = unrealized_pct * notional
        roe_pct = (unrealized_pnl / margin * 100.0) if margin > 0 else 0.0
        return {
            "event": event,
            "position_id": position.get("position_id"),
            "status": status,
            "timestamp_ms": ts_ms,
            "time_readable": time_text,
            "candle_close_time": time_text,
            "decision_time": None,
            "opened_at": position.get("opened_at"),
            "opened_at_ms": position.get("opened_at_ms"),
            "signal_candle_close_time": position.get("candle_close_time"),
            "entry_decision_time": position.get("decision_time"),
            "signal_reference_price": position.get("signal_reference_price"),
            "execution_quote_source": position.get("execution_quote_source"),
            "closed_at": None,
            "symbol": position.get("symbol"),
            "timeframe": position.get("timeframe"),
            "side": self._position_side(position),
            "entry_price": round(entry, 2),
            "mark_price": round(float(latest_close), 2),
            "exit_price": None,
            "exit_reason": None,
            "pnl": None,
            "net_pnl": None,
            "unrealized_pnl": round(unrealized_pnl, 2),
            "unrealized_pct": round(unrealized_pct * 100.0, 4),
            "roe_pct": round(roe_pct, 4),
            "was_force_closed": False,
            "force_close_reason": None,
            "tp_price": round(float(position.get("tp_price") or 0.0), 2),
            "sl_price": round(float(position.get("sl_price") or 0.0), 2),
            "execution": {
                "entry_price": round(entry, 2),
                "stop_loss": round(float(position.get("sl_price") or 0.0), 2),
                "take_profit": round(float(position.get("tp_price") or 0.0), 2),
                "rr_ratio": round(float(position.get("rr_ratio") or 0.0), 2),
                "position_size": round(notional, 2),
                "margin_usdt": round(margin, 2),
                "mode": str(position.get("setup_mode") or "futures_simulation"),
            },
            "leverage": int(position.get("leverage") or 0),
            "margin_usdt": round(margin, 2),
            "notional_usdt": round(notional, 2),
            "setup_mode": position.get("setup_mode"),
            "rr_ratio": position.get("rr_ratio"),
            "position_management": position.get("position_management"),
            "market": "futures",
            "mode": "simulation",
        }

    def build_open_position(
        self,
        *,
        state: dict[str, Any],
        profile: ExecutionProfile,
        decision: SignalDecision,
        entry_price: float,
        ts_ms: int,
        time_text: str,
        candle_open_time: str,
        candle_close_time: str,
        decision_time: str,
        signal_reference_price: float,
        execution_quote_source: str,
        execution_setup: ExecutionSetup | None = None,
    ) -> dict[str, Any]:
        next_id = coerce_int(state.get("next_position_id"))
        if next_id <= 0:
            next_id = 1
        position_id = f"FUT-{next_id:06d}"
        state["next_position_id"] = next_id + 1

        direction = str(decision.selected_direction or decision.side.value or "LONG").upper()
        if direction == "BUY":
            direction = "LONG"
        elif direction == "SELL":
            direction = "SHORT"
        if direction not in {"LONG", "SHORT"}:
            direction = "LONG"

        if direction == "SHORT":
            tp_price = round(entry_price * (1.0 - self._fallback_tp_pct), 2)
            sl_price = round(entry_price * (1.0 + self._fallback_sl_pct), 2)
        else:
            tp_price = round(entry_price * (1.0 + self._fallback_tp_pct), 2)
            sl_price = round(entry_price * (1.0 - self._fallback_sl_pct), 2)
        rr_ratio = round(self._fallback_tp_pct / self._fallback_sl_pct, 2) if self._fallback_sl_pct > 0 else 0.0
        setup_mode = "futures_fallback_fixed"
        if execution_setup is not None:
            candidate_tp = float(execution_setup.take_profit or 0.0)
            candidate_sl = float(execution_setup.stop_loss or 0.0)
            valid_long_setup = (
                direction == "LONG"
                and candidate_tp > entry_price
                and 0.0 < candidate_sl < entry_price
            )
            valid_short_setup = (
                direction == "SHORT"
                and 0.0 < candidate_tp < entry_price
                and candidate_sl > entry_price
            )
            if valid_long_setup or valid_short_setup:
                tp_price = round(candidate_tp, 2)
                sl_price = round(candidate_sl, 2)
                rr_ratio = round(float(execution_setup.rr_ratio or rr_ratio), 2)
                setup_mode = str(execution_setup.mode or "adaptive_v2_execution")

        notional = round(profile.order_size_usdt * profile.leverage, 2)
        entry_fee = FuturesFeeService.entry_fee_for_notional(notional)
        position_management = build_position_management(
            side=direction,
            entry=entry_price,
            take_profit=tp_price,
        )
        return {
            "position_id": position_id,
            "opened_at_ms": ts_ms,
            "opened_at": time_text,
            "candle_open_time": candle_open_time,
            "candle_close_time": candle_close_time,
            "decision_time": decision_time,
            "signal_reference_price": round(signal_reference_price, 2),
            "execution_quote_source": execution_quote_source,
            "symbol": profile.symbol,
            "timeframe": profile.timeframe,
            "side": direction,
            "entry_price": round(entry_price, 2),
            "tp_price": tp_price,
            "sl_price": sl_price,
            "leverage": profile.leverage,
            "margin_usdt": profile.order_size_usdt,
            "notional_usdt": notional,
            "entry_fee_paid": round(entry_fee, 2),
            "entry_fee_role": FuturesFeeService.TAKER,
            "entry_fee_rate": FuturesFeeService.fee_rate_for_role(FuturesFeeService.TAKER),
            "rr_ratio": rr_ratio,
            "setup_mode": setup_mode,
            "position_management": position_management,
        }

    @staticmethod
    def apply_close_stats(state: dict[str, Any], close_event: dict[str, Any]) -> None:
        stats = state["stats"]
        stats["closed_positions"] = int(stats.get("closed_positions", 0)) + 1
        outcome = str(close_event.get("outcome") or "")
        if outcome == "TP_HIT":
            stats["tp_hits"] = int(stats.get("tp_hits", 0)) + 1
        elif outcome == "SL_HIT":
            stats["sl_hits"] = int(stats.get("sl_hits", 0)) + 1
        elif outcome == "PROFIT_LOCK_HIT":
            stats["profit_lock_hits"] = int(stats.get("profit_lock_hits", 0)) + 1
        elif outcome == "FORCE_CLOSED":
            stats["force_close_events"] = int(stats.get("force_close_events", 0)) + 1
            reason = str(close_event.get("force_close_reason") or "unspecified")
            by_reason = stats.get("force_closes_by_reason")
            if not isinstance(by_reason, dict):
                by_reason = {}
                stats["force_closes_by_reason"] = by_reason
            by_reason[reason] = int(by_reason.get(reason, 0)) + 1
        stats["total_gross_pnl"] = round(
            float(stats.get("total_gross_pnl", 0.0)) + float(close_event.get("gross_pnl") or 0.0),
            2,
        )
        stats["total_fees_paid"] = round(
            float(stats.get("total_fees_paid", 0.0)) + float(close_event.get("fees_paid") or 0.0),
            2,
        )
        stats["total_net_pnl"] = round(
            float(stats.get("total_net_pnl", 0.0)) + float(close_event.get("net_pnl") or 0.0),
            2,
        )

    @classmethod
    def unrealized_pct(cls, *, position: dict[str, Any], latest_close: float) -> float:
        entry = float(position.get("entry_price") or 0.0)
        if entry <= 0 or latest_close <= 0:
            return 0.0
        if cls._position_side(position) == "SHORT":
            return (entry - latest_close) / entry
        return (latest_close - entry) / entry

    @staticmethod
    def _position_side(position: dict[str, Any]) -> str:
        side = str(position.get("side") or "LONG").upper()
        if side == "BUY":
            return "LONG"
        if side == "SELL":
            return "SHORT"
        if side in {"LONG", "SHORT"}:
            return side
        return "LONG"

    @staticmethod
    def candles_after_position_open(
        *,
        position: dict[str, Any],
        candles: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        opened_at_ms = coerce_int(position.get("opened_at_ms"))
        if opened_at_ms <= 0:
            return candles
        # A candle that opened before the position contains an unknown pre-entry
        # high/low range. Skipping that overlapping candle prevents false exits.
        return [candle for candle in candles if coerce_int(candle.get("timestamp")) >= opened_at_ms]

    @staticmethod
    def _normalize_exit_reason(outcome: str) -> str:
        normalized = str(outcome or "").upper()
        if normalized == "TP_HIT":
            return "tp_hit"
        if normalized == "SL_HIT":
            return "sl_hit"
        if normalized == "PROFIT_LOCK_HIT":
            return "profit_lock_hit"
        if normalized == "FORCE_CLOSED":
            return "force_closed"
        return "closed"

    @staticmethod
    def _duration_seconds(*, opened_at_ms: int, closed_at_ms: int) -> int | None:
        if opened_at_ms <= 0 or closed_at_ms <= 0 or closed_at_ms < opened_at_ms:
            return None
        return int((closed_at_ms - opened_at_ms) / 1000)

    @staticmethod
    def _duration_text(duration_seconds: int | None) -> str | None:
        if duration_seconds is None:
            return None
        hours = duration_seconds // 3600
        minutes = (duration_seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
