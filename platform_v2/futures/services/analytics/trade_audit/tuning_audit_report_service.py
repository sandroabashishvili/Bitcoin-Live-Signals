"""File: tuning_audit_report_service.py
Folder: platform_v2/futures/services/analytics/trade_audit
Created date: 2026-05-25
Last updated date: 2026-05-25
Author: Codex
Purpose: Build focused Futures tuning audit reports from closed trade attribution rows.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from platform_v2.shared.backend.runtime_store.futures import (
    TRADE_ENTRY_AUDITS_FAMILY,
    TUNING_AUDIT_REPORTS_FAMILY,
    load_family_rows_all,
    store_runtime_snapshot,
)


class FuturesTuningAuditReportService:
    """Build a compact report for rule-tuning decisions without changing trading rules."""

    _GATE_NAMES = ("mtf", "regime", "momentum", "trend", "orderbook", "structure")
    _MIN_TOTAL_TRADES = 50
    _MIN_SIDE_TRADES = 20

    def build_and_store(self, *, date_iso: str) -> Path:
        report = self.build_report(date_iso=date_iso)
        return store_runtime_snapshot(TUNING_AUDIT_REPORTS_FAMILY, date_iso, report)

    def build_report(self, *, date_iso: str) -> dict[str, Any]:
        rows = [
            row
            for row in load_family_rows_all(TRADE_ENTRY_AUDITS_FAMILY)
            if self._row_date(row) and self._row_date(row) <= date_iso
        ]
        rows.sort(key=lambda row: int(row.get("close_timestamp_ms") or 0))

        by_side = self._group(rows, lambda row: self._side(row))
        by_timing = self._group(rows, lambda row: str(row.get("entry_timing_type") or "UNKNOWN").upper())
        by_location = self._group(rows, lambda row: str(row.get("entry_location_type") or "UNKNOWN").upper())
        by_market_plan = self._group(
            rows,
            lambda row: str(row.get("entry_market_plan_alignment") or "UNKNOWN").upper(),
        )
        by_side_timing = self._group(
            rows,
            lambda row: f"{self._side(row)}:{str(row.get('entry_timing_type') or 'UNKNOWN').upper()}",
        )
        by_side_location = self._group(
            rows,
            lambda row: f"{self._side(row)}:{str(row.get('entry_location_type') or 'UNKNOWN').upper()}",
        )
        by_side_market_plan = self._group(
            rows,
            lambda row: f"{self._side(row)}:{str(row.get('entry_market_plan_alignment') or 'UNKNOWN').upper()}",
        )

        gate_combos = self._gate_combos(rows)
        by_side_gate = self._side_gate_stats(rows)
        sample_status = self._sample_status(rows=rows, by_side=by_side)

        return {
            "date": date_iso,
            "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"),
            "window_start": self._row_date(rows[0]) if rows else date_iso,
            "window_end": date_iso,
            "sample_size": len(rows),
            "minimum_total_trades": self._MIN_TOTAL_TRADES,
            "minimum_side_trades": self._MIN_SIDE_TRADES,
            "sample_status": sample_status,
            "by_side": by_side,
            "by_timing": by_timing,
            "by_location": by_location,
            "by_market_plan_alignment": by_market_plan,
            "by_side_timing": by_side_timing,
            "by_side_location": by_side_location,
            "by_side_market_plan_alignment": by_side_market_plan,
            "by_side_gate": by_side_gate,
            "gate_combos": gate_combos,
            "worst_buckets": self._worst_buckets(
                {
                    "side_timing": by_side_timing,
                    "side_location": by_side_location,
                    "side_market_plan": by_side_market_plan,
                    "gate_combo": gate_combos,
                }
            ),
            "candidate_rules": self._candidate_rules(
                by_side=by_side,
                by_side_timing=by_side_timing,
                by_side_location=by_side_location,
                by_side_market_plan=by_side_market_plan,
                by_side_gate=by_side_gate,
                gate_combos=gate_combos,
            ),
            "notes": self._notes(sample_status),
        }

    @classmethod
    def _group(cls, rows: list[dict[str, Any]], key_fn: Callable[[dict[str, Any]], str]) -> dict[str, dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(key_fn(row) or "UNKNOWN").upper()].append(row)
        return {key: cls._bucket(grouped[key]) for key in sorted(grouped)}

    @classmethod
    def _bucket(cls, rows: list[dict[str, Any]]) -> dict[str, Any]:
        trades = len(rows)
        wins = sum(1 for row in rows if cls._net_pnl(row) > 0)
        tp = sum(1 for row in rows if cls._outcome(row) == "TP_HIT")
        sl = sum(1 for row in rows if cls._outcome(row) == "SL_HIT")
        force = sum(1 for row in rows if cls._outcome(row) == "FORCE_CLOSED")
        net_pnl = round(sum(cls._net_pnl(row) for row in rows), 4)
        return {
            "trades": trades,
            "wins": wins,
            "tp": tp,
            "sl": sl,
            "force": force,
            "net_pnl": net_pnl,
            "avg_net_pnl": round(net_pnl / trades, 4) if trades else 0.0,
            "win_rate": round((wins / trades) * 100.0, 2) if trades else 0.0,
        }

    @classmethod
    def _gate_combos(cls, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return cls._group(rows, cls._gate_combo_key)

    @classmethod
    def _side_gate_stats(cls, rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
        output: dict[str, dict[str, dict[str, Any]]] = {}
        for side in ("LONG", "SHORT"):
            side_rows = [row for row in rows if cls._side(row) == side]
            output[side] = {}
            for gate in cls._GATE_NAMES:
                passed = [row for row in side_rows if cls._gate_passed(row, gate)]
                missing = [row for row in side_rows if not cls._gate_passed(row, gate)]
                output[side][gate.upper()] = {
                    "passed": cls._bucket(passed),
                    "missing": cls._bucket(missing),
                    "passed_minus_missing_net_pnl": round(
                        cls._bucket(passed)["net_pnl"] - cls._bucket(missing)["net_pnl"],
                        4,
                    ),
                }
        return output

    @classmethod
    def _worst_buckets(cls, groups: dict[str, dict[str, dict[str, Any]]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for group_name, buckets in groups.items():
            for bucket_name, bucket in buckets.items():
                trades = int(bucket.get("trades") or 0)
                net_pnl = float(bucket.get("net_pnl") or 0.0)
                if trades < 2 or net_pnl >= 0:
                    continue
                rows.append(
                    {
                        "group": group_name,
                        "bucket": bucket_name,
                        "trades": trades,
                        "net_pnl": round(net_pnl, 4),
                        "win_rate": bucket.get("win_rate"),
                    }
                )
        return sorted(rows, key=lambda row: float(row["net_pnl"]))[:12]

    @classmethod
    def _candidate_rules(
        cls,
        *,
        by_side: dict[str, dict[str, Any]],
        by_side_timing: dict[str, dict[str, Any]],
        by_side_location: dict[str, dict[str, Any]],
        by_side_market_plan: dict[str, dict[str, Any]],
        by_side_gate: dict[str, dict[str, dict[str, Any]]],
        gate_combos: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []

        short = by_side.get("SHORT", {})
        long = by_side.get("LONG", {})
        if int(short.get("trades") or 0) >= cls._MIN_SIDE_TRADES and float(short.get("net_pnl") or 0.0) < float(long.get("net_pnl") or 0.0):
            candidates.append(
                {
                    "rule": "Review SHORT separately from LONG",
                    "reason": f"SHORT net_pnl={short.get('net_pnl')} vs LONG net_pnl={long.get('net_pnl')}.",
                    "confidence": cls._confidence(short),
                }
            )

        for key in ("SHORT:OUTSIDE_ZONE", "SHORT:NO_PLAN", "SHORT:NO_SIDE_PLAN"):
            bucket = by_side_market_plan.get(key, {})
            if cls._negative_enough(bucket):
                candidates.append(
                    {
                        "rule": f"Block or tighten {key}",
                        "reason": f"{key} trades={bucket.get('trades')}, net_pnl={bucket.get('net_pnl')}, win_rate={bucket.get('win_rate')}%.",
                        "confidence": cls._confidence(bucket),
                    }
                )

        for key in ("SHORT:LATE_EXTENSION", "SHORT:EXHAUSTED_MOVE", "LONG:LATE_EXTENSION", "LONG:EXHAUSTED_MOVE"):
            bucket = by_side_timing.get(key, {})
            if cls._negative_enough(bucket):
                candidates.append(
                    {
                        "rule": f"Keep or tighten entry_quality block for {key}",
                        "reason": f"{key} trades={bucket.get('trades')}, net_pnl={bucket.get('net_pnl')}, win_rate={bucket.get('win_rate')}%.",
                        "confidence": cls._confidence(bucket),
                    }
                )

        for key in ("SHORT:EXTENDED", "SHORT:INTO_SUPPORT", "SHORT:EXTENDED_INTO_SUPPORT", "LONG:EXTENDED", "LONG:INTO_RESISTANCE", "LONG:EXTENDED_INTO_RESISTANCE"):
            bucket = by_side_location.get(key, {})
            if cls._negative_enough(bucket):
                candidates.append(
                    {
                        "rule": f"Require better entry location for {key}",
                        "reason": f"{key} trades={bucket.get('trades')}, net_pnl={bucket.get('net_pnl')}, win_rate={bucket.get('win_rate')}%.",
                        "confidence": cls._confidence(bucket),
                    }
                )

        short_orderbook = by_side_gate.get("SHORT", {}).get("ORDERBOOK", {})
        short_orderbook_passed = short_orderbook.get("passed", {})
        short_orderbook_missing = short_orderbook.get("missing", {})
        if cls._negative_enough(short_orderbook_passed):
            candidates.append(
                {
                    "rule": "Review SHORT orderbook interpretation",
                    "reason": (
                        "SHORT+ORDERBOOK passed is still negative: "
                        f"net_pnl={short_orderbook_passed.get('net_pnl')}, "
                        f"win_rate={short_orderbook_passed.get('win_rate')}%; "
                        f"missing net_pnl={short_orderbook_missing.get('net_pnl')}."
                    ),
                    "confidence": cls._confidence(short_orderbook_passed),
                }
            )

        for combo, bucket in sorted(gate_combos.items(), key=lambda item: float(item[1].get("net_pnl") or 0.0))[:5]:
            if cls._negative_enough(bucket):
                candidates.append(
                    {
                        "rule": f"Watch gate combo {combo}",
                        "reason": f"combo trades={bucket.get('trades')}, net_pnl={bucket.get('net_pnl')}, win_rate={bucket.get('win_rate')}%.",
                        "confidence": cls._confidence(bucket),
                    }
                )

        return candidates[:12]

    @classmethod
    def _negative_enough(cls, bucket: dict[str, Any]) -> bool:
        return int(bucket.get("trades") or 0) >= 2 and float(bucket.get("net_pnl") or 0.0) < 0.0

    @classmethod
    def _confidence(cls, bucket: dict[str, Any]) -> str:
        trades = int(bucket.get("trades") or 0)
        if trades >= 20:
            return "MEDIUM"
        if trades >= 10:
            return "LOW_MEDIUM"
        return "LOW_SAMPLE"

    @classmethod
    def _sample_status(cls, *, rows: list[dict[str, Any]], by_side: dict[str, dict[str, Any]]) -> str:
        long_trades = int(by_side.get("LONG", {}).get("trades") or 0)
        short_trades = int(by_side.get("SHORT", {}).get("trades") or 0)
        if len(rows) >= cls._MIN_TOTAL_TRADES and long_trades >= cls._MIN_SIDE_TRADES and short_trades >= cls._MIN_SIDE_TRADES:
            return "ENOUGH_FOR_RULE_REVIEW"
        return "COLLECT_MORE_BEFORE_MAJOR_RULE_CHANGE"

    @staticmethod
    def _notes(sample_status: str) -> list[str]:
        notes = [
            "This report describes historical closed trades only; it does not change live trading rules.",
            "Use candidate_rules as review targets, not automatic production changes.",
        ]
        if sample_status != "ENOUGH_FOR_RULE_REVIEW":
            notes.append("Sample is still small for major strategy changes; prefer small permission filters over weight rewrites.")
        return notes

    @classmethod
    def _gate_combo_key(cls, row: dict[str, Any]) -> str:
        passed = [gate.upper() for gate in cls._GATE_NAMES if cls._gate_passed(row, gate)]
        return "+".join(passed) if passed else "NO_GATES"

    @classmethod
    def _gate_passed(cls, row: dict[str, Any], gate: str) -> bool:
        signal_value = row.get("entry_signal")
        signal: dict[str, Any] = signal_value if isinstance(signal_value, dict) else {}

        direction_gates_value = signal.get("direction_gates")
        direction_gates: dict[str, Any] = direction_gates_value if isinstance(direction_gates_value, dict) else {}

        side_gate_value = direction_gates.get(cls._side(row).lower())
        side_gates: dict[str, Any] = side_gate_value if isinstance(side_gate_value, dict) else {}

        fallback_gates_value = signal.get("gates")
        fallback_gates: dict[str, Any] = fallback_gates_value if isinstance(fallback_gates_value, dict) else {}

        gates: dict[str, Any] = side_gates or fallback_gates
        return bool(gates.get(gate))

    @staticmethod
    def _side(row: dict[str, Any]) -> str:
        return str(row.get("side") or "UNKNOWN").upper()

    @staticmethod
    def _outcome(row: dict[str, Any]) -> str:
        return str(row.get("outcome") or "UNKNOWN").upper()

    @staticmethod
    def _net_pnl(row: dict[str, Any]) -> float:
        try:
            return float(row.get("net_pnl") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _row_date(row: dict[str, Any]) -> str:
        text = str(row.get("close_time") or row.get("entry_time") or "")
        if len(text) >= 10:
            return text[:10]
        timestamp_ms = int(row.get("close_timestamp_ms") or row.get("entry_timestamp_ms") or 0)
        if timestamp_ms > 0:
            return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        return ""
