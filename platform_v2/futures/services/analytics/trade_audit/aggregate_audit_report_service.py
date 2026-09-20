"""File: aggregate_audit_report_service.py
Folder: platform_v2/futures/services/analytics/trade_audit
Created date: 2026-04-28
Last updated date: 2026-05-01
Author: Codex
Purpose: Build multi-day Futures trade audit reports for tuning decisions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from platform_v2.shared.backend.runtime_store.futures import (
    TRADE_AUDIT_REPORTS_FAMILY,
    TRADE_ENTRY_AUDITS_FAMILY,
    load_family_rows_all,
    store_runtime_snapshot,
)


class FuturesAggregateAuditReportService:
    """Aggregate closed-trade audit rows without changing trading behavior."""

    _MIN_RULE_CHANGE_TRADES = 50
    _MIN_SIDE_TRADES = 20
    _RISKY_LOCATION_TYPES = {
        "EXTENDED",
        "EXTENDED_INTO_RESISTANCE",
        "EXTENDED_INTO_SUPPORT",
        "INTO_RESISTANCE",
        "INTO_SUPPORT",
        "OVERHEATED_EXTENSION",
        "OVERSOLD_EXTENSION",
    }

    def build_and_store(self, *, date_iso: str) -> Path:
        report = self.build_report(date_iso=date_iso)
        return store_runtime_snapshot(TRADE_AUDIT_REPORTS_FAMILY, date_iso, report)

    def build_report(self, *, date_iso: str) -> dict[str, Any]:
        rows = [
            row
            for row in load_family_rows_all(TRADE_ENTRY_AUDITS_FAMILY)
            if self._row_date(row) and self._row_date(row) <= date_iso
        ]
        rows.sort(key=lambda row: int(row.get("close_timestamp_ms") or 0))

        by_timing: dict[str, dict[str, Any]] = {}
        by_location: dict[str, dict[str, Any]] = {}
        by_side: dict[str, dict[str, Any]] = {}
        by_side_timing: dict[str, dict[str, Any]] = {}
        by_side_location: dict[str, dict[str, Any]] = {}

        for row in rows:
            timing = str(row.get("entry_timing_type") or "UNKNOWN").upper()
            location = str(row.get("entry_location_type") or "UNKNOWN").upper()
            side = str(row.get("side") or "UNKNOWN").upper()
            self._accumulate(by_timing.setdefault(timing, self._empty_bucket()), row)
            self._accumulate(by_location.setdefault(location, self._empty_bucket(location=location)), row)
            self._accumulate(by_side.setdefault(side, self._empty_bucket(side=side)), row)
            key = f"{side}:{timing}"
            self._accumulate(
                by_side_timing.setdefault(key, self._empty_bucket(side=side, timing=timing)),
                row,
            )
            location_key = f"{side}:{location}"
            self._accumulate(
                by_side_location.setdefault(
                    location_key,
                    self._empty_bucket(side=side, location=location),
                ),
                row,
            )

        finalized_by_timing = self._finalize_buckets(by_timing)
        finalized_by_location = self._finalize_buckets(by_location)
        finalized_by_side = self._finalize_buckets(by_side)
        finalized_by_side_timing = self._finalize_buckets(by_side_timing)
        finalized_by_side_location = self._finalize_buckets(by_side_location)
        sample_size = len(rows)
        window_start = self._row_date(rows[0]) if rows else date_iso
        warnings = self._warnings(
            finalized_by_timing,
            finalized_by_side_timing,
            finalized_by_location,
            finalized_by_side_location,
        )

        return {
            "date": date_iso,
            "window_start": window_start,
            "window_end": date_iso,
            "sample_size": sample_size,
            "sample_status": self._sample_status(sample_size, finalized_by_side),
            "minimum_rule_change_trades": self._MIN_RULE_CHANGE_TRADES,
            "minimum_side_trades": self._MIN_SIDE_TRADES,
            "by_timing": finalized_by_timing,
            "by_location": finalized_by_location,
            "by_side": finalized_by_side,
            "by_side_timing": finalized_by_side_timing,
            "by_side_location": finalized_by_side_location,
            "warnings": warnings,
            "watchlist": self._watchlist(finalized_by_side_timing, finalized_by_side_location),
            "recommendation": self._recommendation(sample_size, warnings),
        }

    @staticmethod
    def _empty_bucket(
        *,
        side: str | None = None,
        timing: str | None = None,
        location: str | None = None,
    ) -> dict[str, Any]:
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
        if location is not None:
            bucket["entry_location_type"] = location
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

    @staticmethod
    def _finalize_buckets(buckets: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        finalized: dict[str, dict[str, Any]] = {}
        for key, bucket in sorted(buckets.items()):
            trades = int(bucket["trades"])
            wins = int(bucket["wins"])
            bucket["avg_net_pnl"] = round(float(bucket["net_pnl"]) / trades, 4) if trades else 0.0
            bucket["win_rate"] = round((wins / trades) * 100.0, 2) if trades else 0.0
            finalized[key] = bucket
        return finalized

    @classmethod
    def _sample_status(cls, sample_size: int, by_side: dict[str, dict[str, Any]]) -> str:
        long_trades = int(by_side.get("LONG", {}).get("trades") or 0)
        short_trades = int(by_side.get("SHORT", {}).get("trades") or 0)
        if (
            sample_size >= cls._MIN_RULE_CHANGE_TRADES
            and long_trades >= cls._MIN_SIDE_TRADES
            and short_trades >= cls._MIN_SIDE_TRADES
        ):
            return "ENOUGH_FOR_RULE_REVIEW"
        return "TOO_SMALL_FOR_RULE_CHANGE"

    @classmethod
    def _warnings(
        cls,
        by_timing: dict[str, dict[str, Any]],
        by_side_timing: dict[str, dict[str, Any]],
        by_location: dict[str, dict[str, Any]],
        by_side_location: dict[str, dict[str, Any]],
    ) -> list[str]:
        warnings: list[str] = []
        cls._append_late_timing_warning(warnings, by_timing)
        cls._append_negative_bucket_warnings(warnings, by_side_timing)
        cls._append_risky_location_warning(warnings, by_location)
        cls._append_risky_side_location_warnings(warnings, by_side_location)
        return warnings

    @staticmethod
    def _append_late_timing_warning(
        warnings: list[str],
        by_timing: dict[str, dict[str, Any]],
    ) -> None:
        late = by_timing.get("LATE_EXTENSION", {})
        exhausted = by_timing.get("EXHAUSTED_MOVE", {})
        late_trades = int(late.get("trades") or 0) + int(exhausted.get("trades") or 0)
        late_wins = int(late.get("wins") or 0) + int(exhausted.get("wins") or 0)
        late_pnl = round(float(late.get("net_pnl") or 0.0) + float(exhausted.get("net_pnl") or 0.0), 4)
        if late_trades >= 3 and late_wins == 0:
            warnings.append(
                f"LATE_EXTENSION+EXHAUSTED_MOVE has {late_trades} trades, 0 wins, net_pnl={late_pnl}"
            )

    @staticmethod
    def _append_negative_bucket_warnings(
        warnings: list[str],
        buckets: dict[str, dict[str, Any]],
    ) -> None:
        for key, bucket in sorted(buckets.items()):
            trades = int(bucket.get("trades") or 0)
            net_pnl = float(bucket.get("net_pnl") or 0.0)
            if trades >= 3 and net_pnl < 0:
                warnings.append(f"{key} is negative over {trades} trades, net_pnl={round(net_pnl, 4)}")

    @classmethod
    def _append_risky_location_warning(
        cls,
        warnings: list[str],
        by_location: dict[str, dict[str, Any]],
    ) -> None:
        risky_trades = 0
        risky_pnl = 0.0
        for location_type, bucket in by_location.items():
            if location_type not in cls._RISKY_LOCATION_TYPES:
                continue
            risky_trades += int(bucket.get("trades") or 0)
            risky_pnl += float(bucket.get("net_pnl") or 0.0)
        if risky_trades >= 3 and risky_pnl < 0:
            warnings.append(
                f"risky entry locations have {risky_trades} trades, net_pnl={round(risky_pnl, 4)}"
            )

    @classmethod
    def _append_risky_side_location_warnings(
        cls,
        warnings: list[str],
        by_side_location: dict[str, dict[str, Any]],
    ) -> None:
        for key, bucket in sorted(by_side_location.items()):
            location_type = str(bucket.get("entry_location_type") or "")
            trades = int(bucket.get("trades") or 0)
            net_pnl = float(bucket.get("net_pnl") or 0.0)
            if location_type in cls._RISKY_LOCATION_TYPES and trades >= 3 and net_pnl < 0:
                warnings.append(f"{key} is negative over {trades} trades, net_pnl={round(net_pnl, 4)}")

    @staticmethod
    def _watchlist(
        by_side_timing: dict[str, dict[str, Any]],
        by_side_location: dict[str, dict[str, Any]],
    ) -> list[str]:
        watchlist: list[str] = []
        for key, bucket in sorted(by_side_timing.items()):
            trades = int(bucket.get("trades") or 0)
            if trades < 2:
                continue
            watchlist.append(
                f"{key}: trades={trades}, win_rate={bucket.get('win_rate')}, net_pnl={bucket.get('net_pnl')}"
            )
        for key, bucket in sorted(by_side_location.items()):
            trades = int(bucket.get("trades") or 0)
            if trades < 2:
                continue
            watchlist.append(
                f"{key}: trades={trades}, win_rate={bucket.get('win_rate')}, net_pnl={bucket.get('net_pnl')}"
            )
        return watchlist

    @classmethod
    def _recommendation(cls, sample_size: int, warnings: list[str]) -> str:
        if sample_size < cls._MIN_RULE_CHANGE_TRADES:
            return "Do not change trading rules yet; continue collecting audit data."
        if warnings:
            return "Sample is large enough for rule review; inspect warnings before changing execution rules."
        return "Sample is large enough for review, but no strong aggregate warning is active."

    @staticmethod
    def _row_date(row: dict[str, Any]) -> str:
        text = str(row.get("close_time") or row.get("entry_time") or "")
        if len(text) >= 10:
            return text[:10]
        timestamp_ms = int(row.get("close_timestamp_ms") or row.get("entry_timestamp_ms") or 0)
        if timestamp_ms > 0:
            return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        return ""

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
