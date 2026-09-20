"""File: cycle_summary_builder.py
Folder: platform_v2/futures/services/simulation
Created date: 2026-06-01
Last updated date: 2026-06-01
Author: Codex
Purpose: Build Futures cycle summary payloads for runtime loop output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from platform_v2.futures.config import ExecutionProfile
from platform_v2.futures.domain.models.signal import GateSnapshot, SignalDecision

from .models import FuturesCycleSummary
from .permission_text import human_permission_text


class FuturesCycleSummaryBuilder:
    """Build typed cycle summaries from metrics and permission context."""

    @classmethod
    def build(
        cls,
        *,
        metrics: dict[str, Any],
        profile: ExecutionProfile,
        decision: SignalDecision,
        signal_side: str,
        position_event: str,
        permission: Any,
        metrics_path: Path,
    ) -> FuturesCycleSummary:
        return FuturesCycleSummary(
            signal=signal_side,
            position_event=position_event,
            open_positions=int(metrics["open_positions"]),
            equity=float(metrics["equity"]),
            total_net_pnl=float(metrics["total_net_pnl"]),
            total_gross_pnl=float(metrics["total_gross_pnl"]),
            total_fees_paid=float(metrics["total_fees_paid"]),
            unrealized_pnl=float(metrics["unrealized_pnl"]),
            net_return_pct=float(metrics.get("net_return_pct", 0.0)),
            peak_capital=float(metrics.get("peak_capital", profile.starting_balance)),
            lowest_capital=float(metrics.get("lowest_capital", profile.starting_balance)),
            signal_to_trade_conversion=float(metrics.get("signal_to_trade_conversion", 0.0)),
            force_closes_by_reason=dict(metrics.get("force_closes_by_reason") or {}),
            score=round(float(decision.score), 2),
            threshold=round(float(decision.threshold), 2),
            direction_scores={
                "long": round(float(decision.direction_scores.get("long", 0.0)), 2),
                "short": round(float(decision.direction_scores.get("short", 0.0)), 2),
            },
            mtf_direction=str(decision.mtf_direction),
            gates=cls.serialize_gates(decision.gates),
            permission_status="ALLOWED" if permission.allowed else "DENIED",
            permission_reason=permission.reason,
            permission_text=human_permission_text(
                reason=permission.reason,
                checks=permission.checks,
            ),
            metrics_path=metrics_path,
        )

    @staticmethod
    def serialize_gates(gates: GateSnapshot) -> dict[str, bool]:
        return {
            "mtf": bool(gates.mtf),
            "regime": bool(gates.regime),
            "momentum": bool(gates.momentum),
            "trend": bool(gates.trend),
            "orderbook": bool(gates.orderbook),
            "structure": bool(gates.structure),
        }
