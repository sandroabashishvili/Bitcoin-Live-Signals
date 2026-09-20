"""File: service.py
Folder: platform_v2/spot/services/analytics/strategy_effectiveness
Created date: 2026-05-01
Last updated date: 2026-05-01
Author: Codex
Purpose: Public facade for Spot strategy effectiveness analytics.
"""

from __future__ import annotations

from typing import Any

from .gate_stats import (
    build_closed_trade_group_rows,
    build_group_rows,
    closed_trade_gate_effectiveness,
    gate_effectiveness,
)
from .signal_activity import build_signal_activity_summary
from .types import (
    ClosedTradeLogicEvaluationPayload,
    GateEffectivenessStat,
    LogicEvaluationPayload,
    SignalActivitySummary,
)


class StrategyEffectivenessService:
    """Aggregate per-gate effectiveness for BUY signals."""

    _GATE_NAMES = ("mtf", "regime", "momentum", "trend", "orderbook", "structure")
    _PRIMARY_GATES = ("mtf", "regime", "trend")
    _CONFIRMATION_GATES = ("momentum", "orderbook", "structure")

    def build_logic_evaluation(self, signal_rows: list[dict[str, Any]]) -> LogicEvaluationPayload:
        stats = self.gate_effectiveness(signal_rows)
        primary_rows, primary_totals = build_group_rows(self._PRIMARY_GATES, stats)
        confirmation_rows, confirmation_totals = build_group_rows(
            self._CONFIRMATION_GATES,
            stats,
        )
        return {
            "primary_rows": primary_rows,
            "confirmation_rows": confirmation_rows,
            "primary_totals": primary_totals,
            "confirmation_totals": confirmation_totals,
        }

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
        primary_rows, primary_totals = build_closed_trade_group_rows(self._PRIMARY_GATES, stats)
        confirmation_rows, confirmation_totals = build_closed_trade_group_rows(
            self._CONFIRMATION_GATES,
            stats,
        )
        return {
            "primary_rows": primary_rows,
            "confirmation_rows": confirmation_rows,
            "primary_totals": primary_totals,
            "confirmation_totals": confirmation_totals,
            "closed_trade_summary": {
                "closed_positions": 0,
                "tp_hits": 0,
                "sl_hits": 0,
                "profit_lock_hits": 0,
                "force_close_events": 0,
                "win_rate": 0.0,
                "avg_net_per_trade": 0.0,
            },
        }

    def build_signal_activity_summary(
        self,
        signal_rows: list[dict[str, Any]],
    ) -> SignalActivitySummary:
        return build_signal_activity_summary(signal_rows)

    def gate_effectiveness(self, signal_rows: list[dict[str, Any]]) -> dict[str, GateEffectivenessStat]:
        return gate_effectiveness(signal_rows, gate_names=self._GATE_NAMES)

    def closed_trade_gate_effectiveness(
        self,
        *,
        signal_rows: list[dict[str, Any]],
        closed_positions: list[Any],
    ) -> dict[str, dict[str, float | int]]:
        return closed_trade_gate_effectiveness(
            signal_rows=signal_rows,
            closed_positions=closed_positions,
            gate_names=self._GATE_NAMES,
        )
