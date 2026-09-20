"""Persist one normalized main-cycle runtime record for observability."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from platform_v2.shared.backend.runtime_store.spot import CYCLE_RUNS_FAMILY, append_runtime_record

if TYPE_CHECKING:
    from platform_v2.spot.services.ops.main_cycle_service import MainCycleResult


class CycleRunRuntimeService:
    """Persist one normalized runtime record for each main-cycle execution."""

    def build_record(self, *, date_iso: str, result: "MainCycleResult") -> dict[str, Any]:
        signal_result = result.signal_result
        signal = signal_result.signal if signal_result else None
        order_result = signal_result.order_result if signal_result else None
        position = signal_result.position if signal_result else None

        signal_side = getattr(signal.side, "value", None) if signal else None
        score = getattr(signal, "score", None) if signal else None
        threshold = getattr(signal, "threshold", None) if signal else None
        gates = getattr(signal, "gates", None) if signal else None
        gate_map = {} if gates is None else {
            "mtf": bool(getattr(gates, "mtf", False)),
            "regime": bool(getattr(gates, "regime", False)),
            "momentum": bool(getattr(gates, "momentum", False)),
            "trend": bool(getattr(gates, "trend", False)),
            "orderbook": bool(getattr(gates, "orderbook", False)),
            "structure": bool(getattr(gates, "structure", False)),
        }
        failed_gates = [name for name, passed in gate_map.items() if not passed]
        score_passed = bool(score is not None and threshold is not None and float(score) >= float(threshold))
        order_status = getattr(getattr(order_result, "status", None), "value", None)
        position_status = getattr(getattr(position, "status", None), "value", None)

        return {
            "date": date_iso,
            "datetime": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "cycle_key": result.cycle_key,
            "cycle_state": result.cycle_state,
            "cycle_note": result.cycle_note,
            "status": "skipped" if result.skipped else "ok",
            "skip_reason": result.skip_reason,
            "signal_side": signal_side,
            "score": score,
            "threshold": threshold,
            "score_passed": score_passed,
            "failed_gates": failed_gates,
            "gates": gate_map,
            "signal_reasons": list(getattr(signal, "reasons", ()) or ()),
            "order_status": order_status,
            "position_status": position_status,
            "updated_positions_count": len(result.updated_positions),
            "metrics_written": result.metrics_path is not None,
        }

    def build_and_store(self, *, date_iso: str, result: "MainCycleResult") -> Path:
        record = self.build_record(date_iso=date_iso, result=result)
        return append_runtime_record(CYCLE_RUNS_FAMILY, date_iso, record)
