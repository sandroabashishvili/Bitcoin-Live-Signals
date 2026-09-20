"""File: service.py
Folder: platform_v2/futures/services/analytics/futures_strategy_effectiveness
Created date: 2026-05-01
Last updated date: 2026-05-01
Author: Codex
Purpose: Public facade for Futures strategy effectiveness analytics.
"""

from __future__ import annotations

from typing import Any

from .gate_stats import (
    build_closed_trade_group_rows,
    build_group_rows,
    closed_trade_gate_effectiveness,
    gate_effectiveness,
)
from .outcome import net_pnl_value
from .outcome import load_candle_rows, signal_direction, theoretical_outcome
from .signal_activity import build_signal_activity_summary
from .types import (
    ClosedTradeLogicEvaluationPayload,
    ClosedTradeLogicEvaluationRow,
    ClosedTradeLogicEvaluationTotals,
    ClosedTradeSummary,
    GateEffectivenessStat,
    LogicEvaluationPayload,
    SignalActivitySummary,
)


class StrategyEffectivenessService:
    """Aggregate per-gate effectiveness for directional futures signals."""

    _GATE_NAMES = ("mtf", "regime", "momentum", "trend", "orderbook", "structure")
    _PRIMARY_GATES = ("mtf", "regime", "trend")
    _CONFIRMATION_GATES = ("momentum", "orderbook", "structure")

    def build_logic_evaluation(self, signal_rows: list[dict[str, Any]]) -> LogicEvaluationPayload:
        long_stats = self._empty_signal_gate_stats()
        short_stats = self._empty_signal_gate_stats()
        candle_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}

        for row in signal_rows:
            direction = signal_direction(row)
            if direction not in {"LONG", "SHORT"}:
                continue
            stats = short_stats if direction == "SHORT" else long_stats
            outcome = self._theoretical_signal_outcome(row=row, candle_cache=candle_cache)
            gates = row.get("gates")
            if not isinstance(gates, dict):
                continue
            for gate_name in stats:
                if not bool(gates.get(gate_name)):
                    continue
                gate_stats = stats[gate_name]
                gate_stats["participated"] = int(gate_stats["participated"]) + 1
                if outcome == "tp":
                    gate_stats["tp"] = int(gate_stats["tp"]) + 1
                elif outcome == "sl":
                    gate_stats["sl"] = int(gate_stats["sl"]) + 1
                else:
                    gate_stats["open"] = int(gate_stats["open"]) + 1

        long_primary_rows, long_primary_totals = build_group_rows(self._PRIMARY_GATES, long_stats)
        long_confirmation_rows, long_confirmation_totals = build_group_rows(
            self._CONFIRMATION_GATES,
            long_stats,
        )
        short_primary_rows, short_primary_totals = build_group_rows(self._PRIMARY_GATES, short_stats)
        short_confirmation_rows, short_confirmation_totals = build_group_rows(
            self._CONFIRMATION_GATES,
            short_stats,
        )
        return {
            "primary_rows": long_primary_rows,
            "confirmation_rows": long_confirmation_rows,
            "primary_totals": long_primary_totals,
            "confirmation_totals": long_confirmation_totals,
            "long_primary_rows": long_primary_rows,
            "long_confirmation_rows": long_confirmation_rows,
            "long_primary_totals": long_primary_totals,
            "long_confirmation_totals": long_confirmation_totals,
            "short_primary_rows": short_primary_rows,
            "short_confirmation_rows": short_confirmation_rows,
            "short_primary_totals": short_primary_totals,
            "short_confirmation_totals": short_confirmation_totals,
        }

    def build_signal_activity_summary(self, signal_rows: list[dict[str, Any]]) -> SignalActivitySummary:
        return build_signal_activity_summary(signal_rows)

    def build_closed_trade_logic_evaluation(
        self,
        *,
        signal_rows: list[dict[str, Any]],
        closed_positions: list[Any],
    ) -> ClosedTradeLogicEvaluationPayload:
        stats = self.closed_trade_gate_effectiveness(
            signal_rows=signal_rows,
            closed_positions=closed_positions,
        )
        primary_rows, primary_totals = build_closed_trade_group_rows(
            self._PRIMARY_GATES,
            stats,
        )
        confirmation_rows, confirmation_totals = build_closed_trade_group_rows(
            self._CONFIRMATION_GATES,
            stats,
        )
        closed_positions_count = len(closed_positions)
        tp_hits = int(primary_totals["tp"]) + int(confirmation_totals["tp"])
        sl_hits = int(primary_totals["sl"]) + int(confirmation_totals["sl"])
        profit_lock_hits = int(primary_totals["profit_lock"]) + int(
            confirmation_totals["profit_lock"]
        )
        force_close_events = int(primary_totals["force_close"]) + int(confirmation_totals["force_close"])
        summary_total = tp_hits + sl_hits + profit_lock_hits + force_close_events
        summary_wins = sum(net_pnl_value(position) > 0.0 for position in closed_positions)
        summary_win_rate = (summary_wins / summary_total * 100.0) if summary_total > 0 else 0.0
        total_net = sum(net_pnl_value(position) for position in closed_positions)
        avg_net_per_trade = (total_net / closed_positions_count) if closed_positions_count > 0 else 0.0
        return {
            "primary_rows": primary_rows,
            "confirmation_rows": confirmation_rows,
            "primary_totals": primary_totals,
            "confirmation_totals": confirmation_totals,
            "closed_trade_summary": {
                "closed_positions": closed_positions_count,
                "tp_hits": tp_hits,
                "sl_hits": sl_hits,
                "profit_lock_hits": profit_lock_hits,
                "force_close_events": force_close_events,
                "win_rate": round(summary_win_rate, 2),
                "avg_net_per_trade": round(avg_net_per_trade, 2),
            },
        }

    def build_closed_trade_logic_evaluation_from_events(
        self,
        *,
        signal_rows: list[dict[str, Any]],
        position_rows: list[dict[str, Any]],
    ) -> ClosedTradeLogicEvaluationPayload:
        gate_stats = self._closed_trade_gate_effectiveness_from_events(
            signal_rows=signal_rows,
            position_rows=position_rows,
        )
        long_gate_stats = self._closed_trade_gate_effectiveness_from_events(
            signal_rows=signal_rows,
            position_rows=position_rows,
            direction="LONG",
        )
        short_gate_stats = self._closed_trade_gate_effectiveness_from_events(
            signal_rows=signal_rows,
            position_rows=position_rows,
            direction="SHORT",
        )
        primary_rows, primary_totals = self._build_closed_trade_group_rows_with_wins(
            self._PRIMARY_GATES,
            gate_stats,
        )
        confirmation_rows, confirmation_totals = self._build_closed_trade_group_rows_with_wins(
            self._CONFIRMATION_GATES,
            gate_stats,
        )
        long_primary_rows, long_primary_totals = self._build_closed_trade_group_rows_with_wins(
            self._PRIMARY_GATES,
            long_gate_stats,
        )
        long_confirmation_rows, long_confirmation_totals = self._build_closed_trade_group_rows_with_wins(
            self._CONFIRMATION_GATES,
            long_gate_stats,
        )
        short_primary_rows, short_primary_totals = self._build_closed_trade_group_rows_with_wins(
            self._PRIMARY_GATES,
            short_gate_stats,
        )
        short_confirmation_rows, short_confirmation_totals = self._build_closed_trade_group_rows_with_wins(
            self._CONFIRMATION_GATES,
            short_gate_stats,
        )
        closed_trade_summary = self._closed_trade_event_summary(position_rows)
        return {
            "primary_rows": primary_rows,
            "confirmation_rows": confirmation_rows,
            "primary_totals": primary_totals,
            "confirmation_totals": confirmation_totals,
            "long_primary_rows": long_primary_rows,
            "long_confirmation_rows": long_confirmation_rows,
            "long_primary_totals": long_primary_totals,
            "long_confirmation_totals": long_confirmation_totals,
            "short_primary_rows": short_primary_rows,
            "short_confirmation_rows": short_confirmation_rows,
            "short_primary_totals": short_primary_totals,
            "short_confirmation_totals": short_confirmation_totals,
            "closed_trade_summary": closed_trade_summary,
        }

    def gate_effectiveness(self, signal_rows: list[dict[str, Any]]):
        return gate_effectiveness(signal_rows, gate_names=self._GATE_NAMES)

    def closed_trade_gate_effectiveness(
        self,
        *,
        signal_rows: list[dict[str, Any]],
        closed_positions: list[Any],
    ):
        return closed_trade_gate_effectiveness(
            signal_rows=signal_rows,
            closed_positions=closed_positions,
            gate_names=self._GATE_NAMES,
        )

    def _theoretical_signal_outcome(
        self,
        *,
        row: dict[str, Any],
        candle_cache: dict[tuple[str, str], list[dict[str, Any]]],
    ) -> str:
        symbol = str(row.get("symbol") or "")
        timeframe = str(row.get("timeframe") or "")
        cache_key = (symbol, timeframe)
        if cache_key not in candle_cache:
            candle_cache[cache_key] = load_candle_rows(symbol=symbol, timeframe=timeframe)
        return theoretical_outcome(row=row, candles=candle_cache[cache_key])

    def _empty_signal_gate_stats(self) -> dict[str, GateEffectivenessStat]:
        return {
            gate_name: {"participated": 0, "tp": 0, "sl": 0, "open": 0, "win_rate": 0.0}
            for gate_name in self._GATE_NAMES
        }

    def _closed_trade_gate_effectiveness_from_events(
        self,
        *,
        signal_rows: list[dict[str, Any]],
        position_rows: list[dict[str, Any]],
        direction: str | None = None,
    ) -> dict[str, dict[str, float | int]]:
        stats: dict[str, dict[str, float | int]] = {
            gate_name: {
                "participated": 0,
                "tp": 0,
                "sl": 0,
                "profit_lock": 0,
                "force_close": 0,
                "wins": 0,
                "win_rate": 0.0,
            }
            for gate_name in self._GATE_NAMES
        }
        open_events_by_id: dict[str, dict[str, Any]] = {}
        close_events: list[dict[str, Any]] = []
        for row in sorted(position_rows, key=self._position_row_sort_key):
            position_id = str(row.get("position_id") or "").strip()
            if not position_id:
                continue
            event = str(row.get("event") or "").upper()
            if event == "OPENED":
                open_events_by_id[position_id] = row
            elif event == "CLOSED":
                close_events.append(row)

        signal_by_key: dict[tuple[int, str], dict[str, Any]] = {}
        # Position OPENED events are recorded at the execution timestamp, while
        # the originating signal is stamped with the candle close timestamp.
        # Keep both indexes so closed-trade attribution does not depend on those
        # two different clocks being identical.
        signal_by_candle: dict[tuple[str, str], dict[str, Any]] = {}
        for row in signal_rows:
            side = signal_direction(row)
            timestamp_ms = self._as_int(row.get("timestamp_ms"))
            if timestamp_ms is None:
                continue
            if side in {"LONG", "SHORT"}:
                signal_by_key[(timestamp_ms, side)] = row
                candle_close = str(row.get("candle_close_time") or "").strip()
                if candle_close:
                    signal_by_candle[(candle_close, side)] = row

        for close_row in close_events:
            close_direction = self._direction_from_event_row(close_row)
            if direction is not None and close_direction != direction:
                continue
            position_id = str(close_row.get("position_id") or "").strip()
            open_row = open_events_by_id.get(position_id)
            if open_row is None:
                continue
            open_ts = self._as_int(open_row.get("timestamp_ms"))
            if open_ts is None:
                continue
            signal_row = signal_by_key.get((open_ts, close_direction))
            if signal_row is None:
                signal_close = str(close_row.get("signal_candle_close_time") or "").strip()
                if signal_close:
                    signal_row = signal_by_candle.get((signal_close, close_direction))
            if signal_row is None:
                continue
            gates = signal_row.get("gates")
            if not isinstance(gates, dict):
                continue

            outcome = str(close_row.get("outcome") or "").upper()
            net_pnl = self._as_float(close_row.get("net_pnl")) or 0.0
            for gate_name in self._GATE_NAMES:
                if not bool(gates.get(gate_name)):
                    continue
                gate_stats = stats[gate_name]
                gate_stats["participated"] = int(gate_stats["participated"]) + 1
                if outcome == "TP_HIT":
                    gate_stats["tp"] = int(gate_stats["tp"]) + 1
                elif outcome == "SL_HIT":
                    gate_stats["sl"] = int(gate_stats["sl"]) + 1
                elif outcome == "PROFIT_LOCK_HIT":
                    gate_stats["profit_lock"] = int(gate_stats["profit_lock"]) + 1
                elif outcome == "FORCE_CLOSED":
                    gate_stats["force_close"] = int(gate_stats["force_close"]) + 1
                if net_pnl > 0:
                    gate_stats["wins"] = int(gate_stats["wins"]) + 1

        for gate_stats in stats.values():
            participated = int(gate_stats["participated"])
            wins = int(gate_stats["wins"])
            gate_stats["win_rate"] = (wins / participated * 100.0) if participated > 0 else 0.0
        return stats

    def _closed_trade_event_summary(self, position_rows: list[dict[str, Any]]) -> ClosedTradeSummary:
        close_rows = [
            row for row in position_rows if str(row.get("event") or "").upper() == "CLOSED"
        ]
        closed_positions = len(close_rows)
        tp_hits = 0
        sl_hits = 0
        profit_lock_hits = 0
        force_close_events = 0
        total_net = 0.0
        for row in close_rows:
            outcome = str(row.get("outcome") or "").upper()
            if outcome == "TP_HIT":
                tp_hits += 1
            elif outcome == "SL_HIT":
                sl_hits += 1
            elif outcome == "PROFIT_LOCK_HIT":
                profit_lock_hits += 1
            elif outcome == "FORCE_CLOSED":
                force_close_events += 1
            total_net += self._as_float(row.get("net_pnl")) or 0.0
        wins = sum((self._as_float(row.get("net_pnl")) or 0.0) > 0.0 for row in close_rows)
        win_rate = (wins / closed_positions * 100.0) if closed_positions else 0.0
        avg_net_per_trade = (total_net / closed_positions) if closed_positions else 0.0
        return {
            "closed_positions": closed_positions,
            "tp_hits": tp_hits,
            "sl_hits": sl_hits,
            "profit_lock_hits": profit_lock_hits,
            "force_close_events": force_close_events,
            "win_rate": round(win_rate, 2),
            "avg_net_per_trade": round(avg_net_per_trade, 2),
        }

    @staticmethod
    def _build_closed_trade_group_rows_with_wins(
        gate_names: tuple[str, ...],
        stats_by_gate: dict[str, dict[str, float | int]],
    ) -> tuple[list[ClosedTradeLogicEvaluationRow], ClosedTradeLogicEvaluationTotals]:
        rows: list[ClosedTradeLogicEvaluationRow] = []
        total_tp = 0
        total_sl = 0
        total_profit_lock = 0
        total_force = 0
        total_participated = 0
        total_wins = 0
        for gate_name in gate_names:
            stats = stats_by_gate.get(
                gate_name,
                {"participated": 0, "tp": 0, "sl": 0, "profit_lock": 0, "force_close": 0, "wins": 0, "win_rate": 0.0},
            )
            participated = int(stats["participated"])
            tp = int(stats["tp"])
            sl = int(stats["sl"])
            profit_lock = int(stats["profit_lock"])
            force_close = int(stats["force_close"])
            wins = int(stats["wins"])
            total_participated += participated
            total_tp += tp
            total_sl += sl
            total_profit_lock += profit_lock
            total_force += force_close
            total_wins += wins
            rows.append(
                {
                    "gate": gate_name.upper(),
                    "participated": participated,
                    "tp": tp,
                    "sl": sl,
                    "profit_lock": profit_lock,
                    "force_close": force_close,
                    "win_rate": round(float(stats["win_rate"]), 2),
                }
            )
        total_win_rate = (total_wins / total_participated * 100.0) if total_participated > 0 else 0.0
        return rows, {
            "tp": total_tp,
            "sl": total_sl,
            "profit_lock": total_profit_lock,
            "force_close": total_force,
            "wins": total_wins,
            "participated": total_participated,
            "win_rate": round(total_win_rate, 2),
        }

    @staticmethod
    def _position_row_sort_key(row: dict[str, Any]) -> tuple[int, str, str]:
        timestamp_ms = StrategyEffectivenessService._as_int(row.get("timestamp_ms")) or 0
        return (timestamp_ms, str(row.get("position_id") or ""), str(row.get("event") or ""))

    @staticmethod
    def _direction_from_event_row(row: dict[str, Any]) -> str:
        side = signal_direction(row)
        if side in {"LONG", "SHORT"}:
            return side
        return "LONG"

    @staticmethod
    def _as_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
