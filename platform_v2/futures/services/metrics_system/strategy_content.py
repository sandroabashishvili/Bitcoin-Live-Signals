"""File: strategy_content.py
Folder: platform_v2/futures/services/metrics_system
Created date: 2026-05-25
Last updated date: 2026-06-02
Author: Codex
Purpose: Backend-prepared content builders for the Futures Strategy page.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any, cast

from platform_v2.futures.services.analytics.futures_strategy_effectiveness import (
    ClosedTradeLogicEvaluationPayload,
    LogicEvaluationPayload,
    LogicEvaluationTotals,
)

from .grouped_payloads import (
    build_strategy_activity_evaluation_items,
    build_strategy_activity_items,
    build_strategy_outcome_items,
)


class StrategyPageContentService:
    """Build backend-owned content payloads for Strategy page sections."""

    _TIMEFRAME_MS = {
        "5m": 5 * 60 * 1000,
        "15m": 15 * 60 * 1000,
        "1h": 60 * 60 * 1000,
        "4h": 4 * 60 * 60 * 1000,
        "1d": 24 * 60 * 60 * 1000,
    }

    def build_page_content(
        self,
        *,
        signal_rows: list[dict[str, Any]],
        denied_rows: list[dict[str, Any]],
        metrics: dict[str, Any],
        logic_evaluation: Any,
    ) -> dict[str, Any]:
        today_signal_rows = self.same_day_signal_rows(signal_rows)
        today_denied_rows = self.same_day_denied_rows(denied_rows)
        recent_signal_rows = list(reversed(today_signal_rows))
        recent_denied_rows = list(reversed(today_denied_rows))
        return {
            "strategy_status_summary": {
                "total_signals": metrics.get("total_signals_since_start", 0),
                "buy_signals": metrics.get("long_signals_since_start", metrics.get("buy_signals_since_start", 0)),
                "denied_entries": metrics.get("denied_entries_since_start", 0),
                "closed_positions": metrics.get("closed_positions", 0),
                "trades_opened": metrics.get("trades_opened_since_start", 0),
            },
            "strategy_activity_items": build_strategy_activity_items(metrics),
            "strategy_outcome_items": build_strategy_outcome_items(metrics),
            "recent_signals_section": self.build_recent_signals_section(
                recent_signals=recent_signal_rows,
                denied_rows=recent_denied_rows,
            ),
            "logic_tables_section": self.build_logic_tables_section(logic_evaluation),
            "logic_chart_payload": logic_evaluation,
        }

    def build_recent_signals_section(
        self,
        *,
        recent_signals: list[dict[str, Any]],
        denied_rows: list[dict[str, Any]],
        title: str = "Recent Signal Decisions",
        intro: str = "Latest same-day signal outcomes, split into no-trade signals, denied directional signals, and signals that opened trades.",
    ) -> dict[str, Any]:
        headers = ["Signal Candle Close (UTC)", "Signal", "Score", "Passed Gates", "Missing Gates", "Entry Status", "Main Blocker"]
        rows = [
            [
                self.format_signal_timestamp(row),
                self.signal_side_html(row.get("side")),
                self.fmt_number(row.get("score")),
                self.passed_gates_text(row),
                self.failed_gates_text(row),
                self.execution_result_html(row, denied_rows),
                self.denial_reason_cell_html(row, denied_rows),
            ]
            for row in recent_signals
        ]
        return {
            "title": title,
            "badge": len(recent_signals),
            "intro": intro,
            "table_id": "recent-signals",
            "headers": headers,
            "rows": rows,
            "empty_text": "No recent signals recorded yet.",
            "page_size": 5,
        }

    @classmethod
    def same_day_signal_rows(cls, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        today = datetime.now(tz=timezone.utc).date()
        filtered: list[dict[str, Any]] = []
        for row in rows:
            timestamp_ms = cls.normalized_signal_timestamp_ms(row)
            if timestamp_ms is None:
                continue
            if datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).date() == today:
                filtered.append(row)
        return filtered

    @classmethod
    def same_day_denied_rows(cls, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        today = datetime.now(tz=timezone.utc).date()
        filtered: list[dict[str, Any]] = []
        for row in rows:
            raw_signal = row.get("signal")
            signal: dict[str, Any] = raw_signal if isinstance(raw_signal, dict) else {}
            timestamp_ms = cls.normalized_signal_timestamp_ms(signal)
            if timestamp_ms is None:
                timestamp_ms = cls.parse_int(row.get("timestamp_ms"))
            if timestamp_ms is None:
                continue
            try:
                parsed = datetime.fromtimestamp(int(timestamp_ms) / 1000, tz=timezone.utc).date()
            except (TypeError, ValueError, OSError):
                continue
            if parsed == today:
                filtered.append(row)
        return filtered

    @staticmethod
    def build_logic_tables_section(logic_evaluation: LogicEvaluationPayload) -> dict[str, Any]:
        return {
            "title": "Gate Effectiveness",
            "intro": "Gate usage across theoretical LONG and SHORT setup outcomes.",
            "primary_title": "Primary Gates",
            "confirmation_title": "Confirmation Gates",
            "long_primary_title": "LONG Primary Gates",
            "long_confirmation_title": "LONG Confirmation Gates",
            "short_primary_title": "SHORT Primary Gates",
            "short_confirmation_title": "SHORT Confirmation Gates",
            "headers": ["Gate", "Used In", "TP", "SL", "Open", "Win Rate"],
            "primary_rows": logic_evaluation["primary_rows"],
            "confirmation_rows": logic_evaluation["confirmation_rows"],
            "long_primary_rows": logic_evaluation.get("long_primary_rows", logic_evaluation["primary_rows"]),
            "long_confirmation_rows": logic_evaluation.get("long_confirmation_rows", logic_evaluation["confirmation_rows"]),
            "short_primary_rows": logic_evaluation.get("short_primary_rows", []),
            "short_confirmation_rows": logic_evaluation.get("short_confirmation_rows", []),
        }

    @staticmethod
    def build_trade_outcomes_logic_tables_section(
        logic_evaluation: ClosedTradeLogicEvaluationPayload,
    ) -> dict[str, Any]:
        return {
            "title": "Gate Effectiveness",
            "intro": "Closed trades mapped back to the gates that allowed them.",
            "primary_title": "Primary Gates",
            "primary_subtitle": "Core direction filters used before entry.",
            "confirmation_title": "Confirmation Gates",
            "confirmation_subtitle": "Supporting checks that confirm setup quality.",
            "long_primary_title": "LONG Primary Gates",
            "long_primary_subtitle": "Core LONG direction filters used before entry.",
            "long_confirmation_title": "LONG Confirmation Gates",
            "long_confirmation_subtitle": "Supporting LONG checks that confirm setup quality.",
            "short_primary_title": "SHORT Primary Gates",
            "short_primary_subtitle": "Core SHORT direction filters used before entry.",
            "short_confirmation_title": "SHORT Confirmation Gates",
            "short_confirmation_subtitle": "Supporting SHORT checks that confirm setup quality.",
            "headers": [
                "Gate",
                "Passed",
                "TP",
                "SL",
                "Lock",
                "Force",
                "Win %",
            ],
            "primary_rows": logic_evaluation["primary_rows"],
            "confirmation_rows": logic_evaluation["confirmation_rows"],
            "long_primary_rows": logic_evaluation.get("long_primary_rows", logic_evaluation["primary_rows"]),
            "long_confirmation_rows": logic_evaluation.get("long_confirmation_rows", logic_evaluation["confirmation_rows"]),
            "short_primary_rows": logic_evaluation.get("short_primary_rows", []),
            "short_confirmation_rows": logic_evaluation.get("short_confirmation_rows", []),
        }


    @staticmethod
    def passed_gates_text(row: dict[str, Any]) -> str:
        gates = row.get("gates") or {}
        passed = [str(name).replace("_", " ").title() for name, passed in gates.items() if passed]
        if not passed:
            return "—"
        return ", ".join(passed[:4])

    @staticmethod
    def failed_gates_text(row: dict[str, Any]) -> str:
        gates = row.get("gates") or {}
        failed = [str(name).replace("_", " ").title() for name, passed in gates.items() if not passed]
        if not failed:
            return "—"
        return ", ".join(failed[:3])

    @classmethod
    def matching_denied_row(
        cls,
        signal_row: dict[str, Any],
        denied_rows: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        signal_ts = cls.normalized_signal_timestamp_ms(signal_row)
        signal_side = str(signal_row.get("side") or "").upper()
        for denied_row in denied_rows:
            raw_signal = denied_row.get("signal")
            denied_signal = raw_signal if isinstance(raw_signal, dict) else {}
            denied_ts = cls.normalized_signal_timestamp_ms(denied_signal)
            denied_side = str(denied_signal.get("side") or "").upper()
            if signal_ts is not None and denied_ts == signal_ts and signal_side == denied_side:
                return denied_row
        return None

    @classmethod
    def execution_result_html(
        cls,
        signal_row: dict[str, Any],
        denied_rows: list[dict[str, Any]],
    ) -> str:
        side = str(signal_row.get("side") or "").upper()
        if side == "BUY":
            side = "LONG"
        elif side == "SELL":
            side = "SHORT"
        if side not in {"LONG", "SHORT"}:
            return cls.strong_value("No Setup", kind="neutral")
        permission_status = str(signal_row.get("permission_status") or "").upper()
        if permission_status == "DENIED":
            return cls.strong_value("Denied", kind="fail")
        if permission_status == "ALLOWED":
            return cls.strong_value("Opened", kind="pass")
        if cls.matching_denied_row(signal_row, denied_rows):
            return cls.strong_value("Denied", kind="fail")
        return cls.strong_value("Opened", kind="pass")

    @classmethod
    def live_entry_price_html(
        cls,
        signal_row: dict[str, Any],
        denied_rows: list[dict[str, Any]],
    ) -> str:
        denied_row = cls.matching_denied_row(signal_row, denied_rows)
        if denied_row:
            return cls.fmt_number(denied_row.get("live_entry_price"))
        return "—"

    @classmethod
    def denial_reason_cell_html(
        cls,
        signal_row: dict[str, Any],
        denied_rows: list[dict[str, Any]],
    ) -> str:
        denied_row = cls.matching_denied_row(signal_row, denied_rows)
        if denied_row:
            return cls.denial_reason_html(denied_row.get("denial_reason", "unknown"))
        if str(signal_row.get("permission_status") or "").upper() == "DENIED":
            return cls.denial_reason_html(signal_row.get("permission_reason", "unknown"))
        return "—"

    @staticmethod
    def fmt_number(value: Any, digits: int = 2) -> str:
        if value is None:
            return "—"
        try:
            return f"{float(value):.{digits}f}"
        except (TypeError, ValueError):
            return "—"

    @staticmethod
    def parse_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def normalized_timestamp_ms(cls, *, timestamp_ms: Any, timeframe: Any) -> int | None:
        parsed = cls.parse_int(timestamp_ms)
        if parsed is None:
            return None
        return parsed

    @classmethod
    def normalized_signal_timestamp_ms(cls, row: dict[str, Any]) -> int | None:
        return cls.normalized_timestamp_ms(
            timestamp_ms=row.get("timestamp_ms"),
            timeframe=row.get("timeframe"),
        )

    @classmethod
    def format_signal_timestamp(cls, row: dict[str, Any]) -> str:
        value = cls.normalized_signal_timestamp_ms(row)
        if value is None:
            return "—"
        try:
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc).strftime(
                "%d.%m.%Y, %H:%M:%S"
            )
        except (TypeError, ValueError, OSError):
            return "—"

    @staticmethod
    def wrap_value(text: Any, css_class: str) -> str:
        safe = html.escape(str(text if text not in (None, "") else "—"))
        return f'<strong class="{css_class}">{safe}</strong>'

    @classmethod
    def signal_side_html(cls, value: Any) -> str:
        side = str(value or "—").upper()
        if side == "BUY":
            side = "LONG"
        elif side == "SELL":
            side = "SHORT"
        if side == "LONG":
            return cls.wrap_value(side, "value-green")
        if side == "NO_SIGNAL":
            return cls.wrap_value(side, "value-amber")
        if side in {"SHORT", "DENIED"}:
            return cls.wrap_value(side, "value-red")
        return html.escape(side)

    @classmethod
    def passed_gate_count_html(cls, value: int) -> str:
        if value >= 4:
            return cls.wrap_value(value, "value-green")
        if value <= 2:
            return cls.wrap_value(value, "value-red")
        return cls.wrap_value(value, "value-amber")

    @staticmethod
    def denial_reason_html(value: Any) -> str:
        label_map = {
            "entry_quality_block": "Entry timing blocked",
            "flip_confirmation_pending": "SHORT flip awaiting confirmation",
        "entry_history_gap": "Waiting for next candle after history gap",
        "short_entry_location_unconfirmed": "Mature SHORT needs a clean current entry zone",
            "proximity_block": "Too close to recent entry",
            "cooldown_block": "Cooldown active",
            "signal_block": "No actionable setup",
            "capital_block": "Capital limit",
            "exposure_block": "Exposure limit",
            "position_slots_block": "Position limit",
            "direction_position_slots_block": "Direction limit",
            "long_entry_location_block": "Long into resistance",
            "short_market_plan_zone_block": "Outside short zone",
            "manual_block": "Manual block",
            "duplicate_block": "Duplicate position",
            "liquidation_buffer_block": "Liquidation buffer",
            "no_data": "Missing data",
            "allowed": "Opened",
        }
        raw = str(value or "unknown")
        label = label_map.get(raw, raw.replace("_", " ").title())
        return f'<span class="value-red">{html.escape(label)}</span>'

    @classmethod
    def strong_value(cls, value: Any, *, kind: str = "generic") -> str:
        text = str(value or "").upper()
        css_class = ""
        if kind == "pass":
            css_class = "value-green"
        elif kind == "fail":
            css_class = "value-red"
        elif kind == "neutral":
            css_class = "value-amber"
        elif text in {"BUY", "PASS", "TP_HIT", "PROFIT_LOCK_HIT"}:
            css_class = "value-green"
        elif text in {"FAIL", "SL_HIT", "DENIED"}:
            css_class = "value-red"
        elif text in {"NO_SIGNAL", "FORCE_CLOSE", "FORCE_CLOSED"}:
            css_class = "value-amber"
        safe = html.escape(str(value if value not in (None, "") else "—"))
        if css_class:
            return f'<strong class="{css_class}">{safe}</strong>'
        return f"<strong>{safe}</strong>"


class StrategyActivityPageContentService:
    """Build backend-owned content payloads for the Strategy Activity page."""

    def __init__(self, strategy_content_service: StrategyPageContentService | None = None) -> None:
        self._strategy_content_service = strategy_content_service or StrategyPageContentService()

    @staticmethod
    def _empty_logic_evaluation_payload() -> LogicEvaluationPayload:
        empty_totals: LogicEvaluationTotals = {"tp": 0, "sl": 0, "open": 0, "win_rate": 0.0}
        return {
            "primary_rows": [],
            "confirmation_rows": [],
            "primary_totals": empty_totals,
            "confirmation_totals": empty_totals,
        }

    def build_page_content(self, payload: dict[str, Any]) -> dict[str, Any]:
        signal_rows = payload.get("signal_rows")
        denied_rows = payload.get("denied_rows")
        signal_activity_summary = payload.get("signal_activity_summary")
        logic_evaluation = payload.get("logic_evaluation")
        signal_rows_list = signal_rows if isinstance(signal_rows, list) else []
        denied_rows_list = denied_rows if isinstance(denied_rows, list) else []
        signal_activity_summary_dict = (
            signal_activity_summary if isinstance(signal_activity_summary, dict) else {}
        )
        logic_evaluation_payload: LogicEvaluationPayload = (
            cast(LogicEvaluationPayload, logic_evaluation)
            if isinstance(logic_evaluation, dict)
            else self._empty_logic_evaluation_payload()
        )
        recent_signal_rows = list(reversed(signal_rows_list))
        return {
            "strategy_activity_summary": {
                "total_signals": signal_activity_summary_dict.get("total_signals", 0),
                "buy_signals": signal_activity_summary_dict.get("buy_signals", 0),
                "theoretical_tp_hits": signal_activity_summary_dict.get("theoretical_tp_hits", 0),
                "theoretical_sl_hits": signal_activity_summary_dict.get("theoretical_sl_hits", 0),
            },
            "strategy_activity_items": build_strategy_activity_evaluation_items(
                signal_activity_summary_dict
            ),
            "recent_signals_section": self._strategy_content_service.build_recent_signals_section(
                recent_signals=recent_signal_rows,
                denied_rows=denied_rows_list,
                title="Recent Signal Decisions",
                intro="Latest recorded signal outcomes across the full strategy history, shown before portfolio-level trade management and force-close logic.",
            ),
            "logic_tables_section": self._strategy_content_service.build_logic_tables_section(
                logic_evaluation_payload
            ),
            "logic_chart_payload": logic_evaluation_payload,
        }
