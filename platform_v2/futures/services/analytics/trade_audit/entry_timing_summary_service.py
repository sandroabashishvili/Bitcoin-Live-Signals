"""Summarize Futures trade entry timing audit rows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from platform_v2.shared.backend.runtime_store.futures import (
    ENTRY_TIMING_SUMMARIES_FAMILY,
    TRADE_ENTRY_AUDITS_FAMILY,
    daily_json_path,
    load_json_list,
    store_runtime_snapshot,
)


class FuturesEntryTimingSummaryService:
    """Aggregate entry timing performance by side and timing bucket."""

    def build_and_store(self, *, date_iso: str) -> Path:
        summary = self.build_summary(date_iso=date_iso)
        return store_runtime_snapshot(ENTRY_TIMING_SUMMARIES_FAMILY, date_iso, summary)

    def build_summary(self, *, date_iso: str) -> dict[str, Any]:
        rows = load_json_list(daily_json_path(TRADE_ENTRY_AUDITS_FAMILY, date_iso))
        by_timing: dict[str, dict[str, Any]] = {}
        by_side_timing: dict[str, dict[str, Any]] = {}

        for row in rows:
            timing = str(row.get("entry_timing_type") or "UNKNOWN")
            side = str(row.get("side") or "UNKNOWN")
            self._accumulate(by_timing.setdefault(timing, self._empty_bucket()), row)
            key = f"{side}:{timing}"
            self._accumulate(by_side_timing.setdefault(key, self._empty_bucket(side=side, timing=timing)), row)

        return {
            "date": date_iso,
            "total_trades": len(rows),
            "by_timing": self._finalize_buckets(by_timing),
            "by_side_timing": self._finalize_buckets(by_side_timing),
        }

    @staticmethod
    def _empty_bucket(*, side: str | None = None, timing: str | None = None) -> dict[str, Any]:
        bucket: dict[str, Any] = {
            "trades": 0,
            "wins": 0,
            "tp": 0,
            "sl": 0,
            "force": 0,
            "other": 0,
            "net_pnl": 0.0,
            "avg_net_pnl": 0.0,
            "win_rate": 0.0,
        }
        if side is not None:
            bucket["side"] = side
        if timing is not None:
            bucket["entry_timing_type"] = timing
        return bucket

    @classmethod
    def _accumulate(cls, bucket: dict[str, Any], row: dict[str, Any]) -> None:
        outcome = str(row.get("outcome") or "").upper()
        net_pnl = cls._as_float(row.get("net_pnl")) or 0.0
        bucket["trades"] = int(bucket["trades"]) + 1
        bucket["net_pnl"] = round(float(bucket["net_pnl"]) + net_pnl, 4)
        if net_pnl > 0:
            bucket["wins"] = int(bucket["wins"]) + 1
        if outcome == "TP_HIT":
            bucket["tp"] = int(bucket["tp"]) + 1
        elif outcome == "SL_HIT":
            bucket["sl"] = int(bucket["sl"]) + 1
        elif outcome == "FORCE_CLOSED":
            bucket["force"] = int(bucket["force"]) + 1
        else:
            bucket["other"] = int(bucket["other"]) + 1

    @classmethod
    def _finalize_buckets(cls, buckets: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        finalized: dict[str, dict[str, Any]] = {}
        for key, bucket in sorted(buckets.items()):
            trades = int(bucket["trades"])
            wins = int(bucket["wins"])
            bucket["avg_net_pnl"] = round(float(bucket["net_pnl"]) / trades, 4) if trades else 0.0
            bucket["win_rate"] = round((wins / trades) * 100.0, 2) if trades else 0.0
            finalized[key] = bucket
        return finalized

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
