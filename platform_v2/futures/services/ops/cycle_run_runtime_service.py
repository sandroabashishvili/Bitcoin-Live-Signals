"""Persist one normalized futures main-cycle runtime record for observability."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from platform_v2.shared.backend.runtime_store.futures import CYCLE_RUNS_FAMILY, append_runtime_record
from platform_v2.futures.services.ops.main_cycle.models import MainCycleResult


class CycleRunRuntimeService:
    """Persist one normalized runtime record for each futures main-cycle execution."""

    def build_record(self, *, date_iso: str, result: MainCycleResult) -> dict[str, Any]:
        summary = result.summary
        return {
            "date": date_iso,
            "datetime": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "cycle_key": result.cycle_key,
            "cycle_state": result.cycle_state,
            "cycle_note": result.cycle_note,
            "status": "skipped" if result.skipped else "ok",
            "skip_reason": result.skip_reason,
            "signal_side": summary.signal if summary is not None else None,
            "score": summary.score if summary is not None else None,
            "threshold": summary.threshold if summary is not None else None,
            "score_passed": (
                bool(summary is not None and summary.score >= summary.threshold)
                if summary is not None
                else False
            ),
            "gates": dict(summary.gates) if summary is not None else {},
            "failed_gates": (
                [name for name, passed in summary.gates.items() if not passed]
                if summary is not None
                else []
            ),
            "permission_status": summary.permission_status if summary is not None else None,
            "permission_reason": summary.permission_reason if summary is not None else None,
            "permission_text": summary.permission_text if summary is not None else None,
            "position_event": summary.position_event if summary is not None else None,
            "open_positions": summary.open_positions if summary is not None else None,
            "equity": summary.equity if summary is not None else None,
            "gross_pnl": summary.total_gross_pnl if summary is not None else None,
            "fees_paid": summary.total_fees_paid if summary is not None else None,
            "net_pnl": summary.total_net_pnl if summary is not None else None,
            "unrealized_pnl": summary.unrealized_pnl if summary is not None else None,
            "updated_page": result.page_path is not None,
            "metrics_written": bool(summary is not None and summary.metrics_path is not None),
        }

    def build_and_store(self, *, date_iso: str, result: MainCycleResult) -> Path:
        record = self.build_record(date_iso=date_iso, result=result)
        return append_runtime_record(CYCLE_RUNS_FAMILY, date_iso, record)
