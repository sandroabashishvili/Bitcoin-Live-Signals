"""File: short_failure_report_service.py
Folder: platform_v2/futures/services/analytics/trade_audit
Created date: 2026-05-14
Last updated date: 2026-05-14
Author: Codex
Purpose: Build SHORT-only Futures failure attribution reports for tuning.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from platform_v2.shared.backend.runtime_store.futures import (
    SHORT_FAILURE_REPORTS_FAMILY,
    TRADE_ENTRY_AUDITS_FAMILY,
    load_family_rows_all,
    store_runtime_snapshot,
)


class FuturesShortFailureReportService:
    """Aggregate SHORT closed-trade diagnostics without changing trading rules."""

    _MIN_SHORT_TRADES_FOR_REVIEW = 30
    _GATE_NAMES = ("mtf", "regime", "momentum", "trend", "orderbook", "structure")

    def build_and_store(self, *, date_iso: str) -> Path:
        report = self.build_report(date_iso=date_iso)
        return store_runtime_snapshot(SHORT_FAILURE_REPORTS_FAMILY, date_iso, report)

    def build_report(self, *, date_iso: str) -> dict[str, Any]:
        rows = [
            row
            for row in load_family_rows_all(TRADE_ENTRY_AUDITS_FAMILY)
            if self._row_date(row) and self._row_date(row) <= date_iso
        ]
        rows.sort(key=lambda row: int(row.get("close_timestamp_ms") or 0))
        short_rows = [row for row in rows if str(row.get("side") or "").upper() == "SHORT"]
        short_losses = [row for row in short_rows if self._net_pnl(row) < 0]
        short_wins = [row for row in short_rows if self._net_pnl(row) > 0]

        sample_size = len(rows)
        short_sample_size = len(short_rows)
        short_net_pnl = round(sum(self._net_pnl(row) for row in short_rows), 4)
        long_rows = [row for row in rows if str(row.get("side") or "").upper() == "LONG"]
        long_net_pnl = round(sum(self._net_pnl(row) for row in long_rows), 4)

        return {
            "date": date_iso,
            "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"),
            "window_start": self._row_date(rows[0]) if rows else date_iso,
            "window_end": date_iso,
            "sample_size": sample_size,
            "short_sample_size": short_sample_size,
            "minimum_short_trades_for_review": self._MIN_SHORT_TRADES_FOR_REVIEW,
            "sample_status": self._sample_status(short_sample_size),
            "short_net_pnl": short_net_pnl,
            "long_net_pnl": long_net_pnl,
            "short_vs_long_delta": round(short_net_pnl - long_net_pnl, 4),
            "short_overview": self._bucket(short_rows),
            "short_losses": self._bucket(short_losses),
            "short_wins": self._bucket(short_wins),
            "loss_share": self._loss_share(short_rows, short_losses),
            "by_outcome": self._bucket_by(short_rows, lambda row: str(row.get("outcome") or "UNKNOWN").upper()),
            "losses_by_timing": self._bucket_by(short_losses, lambda row: str(row.get("entry_timing_type") or "UNKNOWN").upper()),
            "wins_by_timing": self._bucket_by(short_wins, lambda row: str(row.get("entry_timing_type") or "UNKNOWN").upper()),
            "losses_by_location": self._bucket_by(short_losses, lambda row: str(row.get("entry_location_type") or "UNKNOWN").upper()),
            "wins_by_location": self._bucket_by(short_wins, lambda row: str(row.get("entry_location_type") or "UNKNOWN").upper()),
            "losses_by_market_plan_alignment": self._bucket_by(
                short_losses,
                lambda row: str(row.get("entry_market_plan_alignment") or "UNKNOWN").upper(),
            ),
            "wins_by_market_plan_alignment": self._bucket_by(
                short_wins,
                lambda row: str(row.get("entry_market_plan_alignment") or "UNKNOWN").upper(),
            ),
            "losses_by_mtf_context": self._bucket_by(short_losses, self._mtf_context_key),
            "losses_by_passed_gate": self._gate_buckets(short_losses, passed=True),
            "losses_by_missing_gate": self._gate_buckets(short_losses, passed=False),
            "wins_by_passed_gate": self._gate_buckets(short_wins, passed=True),
            "worst_short_trades": self._compact_trades(short_rows, reverse=False, limit=8),
            "best_short_trades": self._compact_trades(short_rows, reverse=True, limit=5),
            "findings": self._findings(short_rows=short_rows, short_losses=short_losses, short_wins=short_wins),
            "next_research_questions": self._next_research_questions(short_rows),
        }

    @classmethod
    def _gate_buckets(cls, rows: list[dict[str, Any]], *, passed: bool) -> dict[str, dict[str, Any]]:
        buckets: dict[str, list[dict[str, Any]]] = {}
        for gate in cls._GATE_NAMES:
            selected = [row for row in rows if cls._gate_passed(row, gate) is passed]
            buckets[gate.upper()] = cls._bucket(selected)
        return buckets

    @staticmethod
    def _bucket_by(
        rows: list[dict[str, Any]],
        key_fn: Callable[[dict[str, Any]], str],
    ) -> dict[str, dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            key = str(key_fn(row) or "UNKNOWN").upper()
            grouped.setdefault(key, []).append(row)
        return {key: FuturesShortFailureReportService._bucket(grouped[key]) for key in sorted(grouped)}

    @staticmethod
    def _bucket(rows: list[dict[str, Any]]) -> dict[str, Any]:
        trades = len(rows)
        wins = sum(1 for row in rows if FuturesShortFailureReportService._net_pnl(row) > 0)
        tp = sum(1 for row in rows if str(row.get("outcome") or "").upper() == "TP_HIT")
        sl = sum(1 for row in rows if str(row.get("outcome") or "").upper() == "SL_HIT")
        force = sum(1 for row in rows if str(row.get("outcome") or "").upper() == "FORCE_CLOSED")
        net_pnl = round(sum(FuturesShortFailureReportService._net_pnl(row) for row in rows), 4)
        avg_net_pnl = round(net_pnl / trades, 4) if trades else 0.0
        win_rate = round((wins / trades) * 100.0, 2) if trades else 0.0
        return {
            "trades": trades,
            "wins": wins,
            "tp": tp,
            "sl": sl,
            "force": force,
            "net_pnl": net_pnl,
            "avg_net_pnl": avg_net_pnl,
            "win_rate": win_rate,
        }

    @staticmethod
    def _loss_share(short_rows: list[dict[str, Any]], short_losses: list[dict[str, Any]]) -> dict[str, Any]:
        total_abs_loss = sum(abs(FuturesShortFailureReportService._net_pnl(row)) for row in short_losses)
        total_trades = len(short_rows)
        return {
            "losing_trades": len(short_losses),
            "loss_rate": round((len(short_losses) / total_trades) * 100.0, 2) if total_trades else 0.0,
            "total_abs_loss": round(total_abs_loss, 4),
            "avg_abs_loss": round(total_abs_loss / len(short_losses), 4) if short_losses else 0.0,
        }

    @staticmethod
    def _compact_trades(rows: list[dict[str, Any]], *, reverse: bool, limit: int) -> list[dict[str, Any]]:
        sorted_rows = sorted(rows, key=FuturesShortFailureReportService._net_pnl, reverse=reverse)
        compact: list[dict[str, Any]] = []
        for row in sorted_rows[:limit]:
            entry_signal = row.get("entry_signal") if isinstance(row.get("entry_signal"), dict) else {}
            compact.append(
                {
                    "position_id": row.get("position_id"),
                    "outcome": row.get("outcome"),
                    "entry_time": row.get("entry_time"),
                    "close_time": row.get("close_time"),
                    "entry_price": row.get("entry_price"),
                    "exit_price": row.get("exit_price"),
                    "net_pnl": FuturesShortFailureReportService._net_pnl(row),
                    "timing": row.get("entry_timing_type"),
                    "location": row.get("entry_location_type"),
                    "market_plan_alignment": row.get("entry_market_plan_alignment"),
                    "passed_gates": FuturesShortFailureReportService._gate_names(row, passed=True),
                    "missing_gates": FuturesShortFailureReportService._gate_names(row, passed=False),
                    "mtf_signals": entry_signal.get("mtf_signals"),
                }
            )
        return compact

    @classmethod
    def _findings(
        cls,
        *,
        short_rows: list[dict[str, Any]],
        short_losses: list[dict[str, Any]],
        short_wins: list[dict[str, Any]],
    ) -> list[str]:
        findings: list[str] = []
        short_bucket = cls._bucket(short_rows)
        if short_bucket["trades"]:
            findings.append(
                "SHORT sample: "
                f"{short_bucket['trades']} trades, net_pnl={short_bucket['net_pnl']}, "
                f"win_rate={short_bucket['win_rate']}%."
            )
        timing = cls._bucket_by(short_losses, lambda row: str(row.get("entry_timing_type") or "UNKNOWN"))
        cls._append_top_negative_bucket(findings, "Worst losing timing", timing)
        location = cls._bucket_by(short_losses, lambda row: str(row.get("entry_location_type") or "UNKNOWN"))
        cls._append_top_negative_bucket(findings, "Worst losing location", location)
        plan = cls._bucket_by(short_losses, lambda row: str(row.get("entry_market_plan_alignment") or "UNKNOWN"))
        cls._append_top_negative_bucket(findings, "Worst market-plan alignment among losses", plan)

        loss_missing = cls._gate_buckets(short_losses, passed=False)
        top_missing = sorted(loss_missing.items(), key=lambda item: int(item[1]["trades"]), reverse=True)[:3]
        if top_missing:
            findings.append(
                "Most common missing gates in SHORT losses: "
                + ", ".join(f"{name}={bucket['trades']}" for name, bucket in top_missing)
                + "."
            )

        if len(short_rows) < cls._MIN_SHORT_TRADES_FOR_REVIEW:
            findings.append("Sample is still below the preferred SHORT rule-review threshold.")
        elif short_bucket["net_pnl"] < 0:
            findings.append("SHORT side is large enough for focused review and currently negative.")
        if short_wins:
            win_bucket = cls._bucket(short_wins)
            findings.append(
                f"SHORT winners exist ({win_bucket['trades']} trades), so the likely issue is filtering/context, not disabling SHORT entirely."
            )
        return findings

    @staticmethod
    def _append_top_negative_bucket(
        findings: list[str],
        label: str,
        buckets: dict[str, dict[str, Any]],
    ) -> None:
        if not buckets:
            return
        negative = [
            (name, bucket)
            for name, bucket in buckets.items()
            if int(bucket.get("trades") or 0) > 0 and float(bucket.get("net_pnl") or 0.0) < 0
        ]
        if not negative:
            return
        name, bucket = min(negative, key=lambda item: float(item[1].get("net_pnl") or 0.0))
        findings.append(
            f"{label}: {name}, trades={bucket['trades']}, net_pnl={bucket['net_pnl']}, win_rate={bucket['win_rate']}%."
        )

    @classmethod
    def _next_research_questions(cls, short_rows: list[dict[str, Any]]) -> list[str]:
        if not short_rows:
            return ["Collect SHORT trades before tuning SHORT rules."]
        return [
            "Test SHORT only when market-plan alignment is IN_ZONE versus OUTSIDE_ZONE.",
            "Test whether SHORT entries missing ORDERBOOK or STRUCTURE should require stronger 4h/15m alignment.",
            "Compare SHORT losses where 5m MTF disagrees against losses where all MTF frames are SHORT.",
            "Review whether SHORT TP/SL is too wide after sharp downside moves and bounce risk.",
        ]

    @classmethod
    def _gate_names(cls, row: dict[str, Any], *, passed: bool) -> list[str]:
        return [gate.upper() for gate in cls._GATE_NAMES if cls._gate_passed(row, gate) is passed]

    @staticmethod
    def _gate_passed(row: dict[str, Any], gate: str) -> bool:
        signal = row.get("entry_signal") if isinstance(row.get("entry_signal"), dict) else {}
        direction_gates = signal.get("direction_gates") if isinstance(signal.get("direction_gates"), dict) else {}
        short_gates = direction_gates.get("short") if isinstance(direction_gates.get("short"), dict) else {}
        fallback_gates = signal.get("gates") if isinstance(signal.get("gates"), dict) else {}
        gates = short_gates or fallback_gates
        return bool(gates.get(gate))

    @staticmethod
    def _mtf_context_key(row: dict[str, Any]) -> str:
        signal = row.get("entry_signal") if isinstance(row.get("entry_signal"), dict) else {}
        mtf = signal.get("mtf_signals") if isinstance(signal.get("mtf_signals"), dict) else {}
        return f"5m={mtf.get('5m', 'UNKNOWN')}|15m={mtf.get('15m', 'UNKNOWN')}|4h={mtf.get('4h', 'UNKNOWN')}"

    @staticmethod
    def _sample_status(short_sample_size: int) -> str:
        if short_sample_size >= FuturesShortFailureReportService._MIN_SHORT_TRADES_FOR_REVIEW:
            return "ENOUGH_FOR_SHORT_REVIEW"
        return "TOO_SMALL_FOR_RULE_CHANGE"

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
    def _net_pnl(row: dict[str, Any]) -> float:
        try:
            return float(row.get("net_pnl") or 0.0)
        except (TypeError, ValueError):
            return 0.0
