"""File: portfolio_content.py
Folder: platform_v2/futures/services/metrics_system
Created date: 2026-05-25
Last updated date: 2026-06-02
Author: Codex
Purpose: Backend-prepared content builders for the Futures Portfolio page.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime
from typing import Any


class PortfolioPageContentService:
    """Build backend-owned content payloads for Portfolio page sections."""

    def build_positions_content(
        self,
        *,
        position_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        latest_positions = self._latest_position_states(position_rows)
        open_positions = self._sort_open_positions(
            [row for row in latest_positions if row.get("status") == "OPEN"]
        )
        closed_positions = self._sort_closed_positions(
            [row for row in latest_positions if row.get("status") != "OPEN"]
        )
        open_positions_table_rows = [self._build_open_position_table_item(row) for row in open_positions]
        closed_positions_table_rows = [self._build_closed_position_table_item(row) for row in closed_positions]
        return {
            "open_positions_section": {
                "title": "Open Positions",
                "badge": len(open_positions),
                "intro": "Live positions with entry, notional, margin, TP/SL, and unrealized performance.",
                "table_id": "open-positions",
                "headers": [
                    "Opened",
                    "Symbol",
                    "Side",
                    "Entry",
                    "Notional",
                    "Margin",
                    "R:R",
                    "TP",
                    "SL",
                    "Unreal",
                    {"label": "Unreal %", "explanation_key": "portfolio.open_positions.unreal_pct"},
                    {"label": "ROE %", "explanation_key": "portfolio.open_positions.roe_pct"},
                ],
                "rows": open_positions_table_rows,
                "empty_text": "No open positions recorded yet.",
            },
            "closed_positions_section": {
                "title": "Closed Positions",
                "badge": len(closed_positions),
                "intro": "Completed positions with opened time, confirmed exit time, outcome, and force-close flag.",
                "table_id": "closed-positions",
                "headers": ["Opened", "Confirmed Exit", "Symbol", "Side", "Result", "Entry", "Exit", "Net", "Duration", "R:R", "Force"],
                "rows": closed_positions_table_rows,
                "empty_text": "No closed positions recorded yet.",
            },
            "closed_trade_chart_rows": [
                self._build_closed_trade_chart_row(row)
                for row in sorted(closed_positions, key=self._closed_chart_sort_key)
            ],
        }

    @staticmethod
    def _latest_position_states(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        latest_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            position_id = row.get("position_id")
            if not position_id:
                continue
            latest_by_id[str(position_id)] = row
        return list(reversed(list(latest_by_id.values())))

    @classmethod
    def _sort_open_positions(cls, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(rows, key=cls._open_sort_key, reverse=True)

    @classmethod
    def _sort_closed_positions(cls, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(rows, key=cls._closed_sort_key, reverse=True)

    @classmethod
    def _open_sort_key(cls, row: dict[str, Any]) -> tuple[datetime, str]:
        return (
            cls._parse_timestamp(row.get("opened_at")) or datetime.min.replace(tzinfo=UTC),
            str(row.get("position_id") or ""),
        )

    @classmethod
    def _closed_sort_key(cls, row: dict[str, Any]) -> tuple[datetime, datetime, str]:
        return (
            cls._parse_timestamp(row.get("closed_at"))
            or cls._parse_timestamp(row.get("opened_at"))
            or datetime.min.replace(tzinfo=UTC),
            cls._parse_timestamp(row.get("opened_at")) or datetime.min.replace(tzinfo=UTC),
            str(row.get("position_id") or ""),
        )

    @classmethod
    def _closed_chart_sort_key(cls, row: dict[str, Any]) -> tuple[datetime, datetime, str]:
        return (
            cls._parse_timestamp(row.get("closed_at"))
            or cls._parse_timestamp(row.get("opened_at"))
            or datetime.min.replace(tzinfo=UTC),
            cls._parse_timestamp(row.get("opened_at")) or datetime.min.replace(tzinfo=UTC),
            str(row.get("position_id") or ""),
        )

    def _build_open_position_row(self, row: dict[str, Any]) -> list[str]:
        execution = self._execution_dict(row)
        position_notional, position_margin = self._position_notional_and_margin(row, execution)
        unrealized = row.get("unrealized_pnl")
        return [
            self._escape(self._fmt_timestamp(row.get("opened_at"))),
            self._escape(row.get("symbol", "—")),
            self._strong(self._display_side(row.get("side"))),
            self._strong(self._fmt_number(execution.get("entry_price"))),
            self._strong(self._fmt_usd(position_notional)),
            self._strong(self._fmt_usd(position_margin)),
            self._strong(self._fmt_number(execution.get("rr_ratio"))),
            self._strong(self._fmt_number(execution.get("take_profit")), kind="tp"),
            self._strong(self._fmt_number(execution.get("stop_loss")), kind="sl"),
            self._strong(self._fmt_usd(unrealized), kind="pnl"),
            self._strong(self._fmt_pct_from_notional(unrealized, position_notional), kind="pnl"),
            self._strong(self._fmt_pct_from_base(unrealized, position_margin), kind="pnl"),
        ]

    def _build_closed_position_row(self, row: dict[str, Any]) -> list[str]:
        execution = self._execution_dict(row)
        net_pnl = row.get("net_pnl")
        return [
            self._escape(self._fmt_timestamp(row.get("opened_at"))),
            self._escape(self._fmt_timestamp(row.get("closed_at"))),
            self._escape(row.get("symbol", "—")),
            self._strong(self._display_side(row.get("side"))),
            self._strong(row.get("exit_reason", row.get("status", "—"))),
            self._strong(self._fmt_number(execution.get("entry_price"))),
            self._strong(self._fmt_number(row.get("exit_price"))),
            self._strong(self._fmt_usd(net_pnl), kind="pnl"),
            self._strong(row.get("duration_text") or "—"),
            self._strong(self._fmt_number(execution.get("rr_ratio"))),
            self._strong("YES" if row.get("was_force_closed") else "NO"),
        ]

    def _build_open_position_table_item(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "cells": self._build_open_position_row(row),
            "details": self._build_open_position_detail_items(row),
        }

    def _build_closed_position_table_item(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "cells": self._build_closed_position_row(row),
            "details": self._build_closed_position_detail_items(row),
        }

    def _build_open_position_detail_items(self, row: dict[str, Any]) -> list[dict[str, str]]:
        execution = self._execution_dict(row)
        leverage = row.get("leverage")
        notional, margin = self._position_notional_and_margin(row, execution)
        unrealized = row.get("unrealized_pnl")
        details = [
            ("Position ID", row.get("position_id"), "generic"),
            ("Signal Candle Closed", row.get("signal_candle_close_time"), "generic"),
            ("Decision Time", row.get("entry_decision_time") or row.get("decision_time"), "generic"),
            ("Position Opened", self._fmt_timestamp(row.get("opened_at")), "generic"),
            ("Signal Reference Price", self._fmt_number(row.get("signal_reference_price")), "generic"),
            ("Execution Price Source", row.get("execution_quote_source"), "generic"),
            ("Market", row.get("market"), "generic"),
            ("Mode", row.get("mode"), "generic"),
            ("Status", row.get("status"), "generic"),
            ("Timeframe", row.get("timeframe"), "generic"),
            ("Leverage", f"x{leverage}" if leverage not in (None, "") else "—", "generic"),
            ("Notional", self._fmt_usd(notional), "generic"),
            ("Margin", self._fmt_usd(margin), "generic"),
            ("Entry", self._fmt_number(execution.get("entry_price")), "generic"),
            ("Unrealized", self._fmt_usd(unrealized), "pnl"),
            ("Unreal %", self._fmt_pct_from_notional(unrealized, notional), "pnl"),
            ("ROE %", self._fmt_pct_from_base(unrealized, margin), "pnl"),
            ("R:R", self._fmt_number(execution.get("rr_ratio")), "generic"),
            ("TP", self._fmt_number(execution.get("take_profit")), "tp"),
            ("SL", self._fmt_number(execution.get("stop_loss")), "sl"),
        ]
        return self._detail_payload(details)

    def _build_closed_position_detail_items(self, row: dict[str, Any]) -> list[dict[str, str]]:
        execution = self._execution_dict(row)
        leverage = row.get("leverage")
        notional, margin = self._position_notional_and_margin(row, execution)
        net_pnl = row.get("net_pnl")
        gross_pnl = row.get("gross_pnl")
        details = [
            ("Position ID", row.get("position_id"), "generic"),
            ("Signal Candle Closed", row.get("signal_candle_close_time"), "generic"),
            ("Decision Time", row.get("entry_decision_time") or row.get("decision_time"), "generic"),
            ("Position Opened", self._fmt_timestamp(row.get("opened_at")), "generic"),
            ("Signal Reference Price", self._fmt_number(row.get("signal_reference_price")), "generic"),
            ("Execution Price Source", row.get("execution_quote_source"), "generic"),
            ("Market", row.get("market"), "generic"),
            ("Mode", row.get("mode"), "generic"),
            ("Timeframe", row.get("timeframe"), "generic"),
            ("Leverage", f"x{leverage}" if leverage not in (None, "") else "—", "generic"),
            ("Notional", self._fmt_usd(notional), "generic"),
            ("Margin", self._fmt_usd(margin), "generic"),
            ("Gross PnL", self._fmt_usd(gross_pnl), "pnl"),
            ("Fees Paid", self._fmt_usd(row.get("fees_paid")), "sl"),
            ("Net PnL", self._fmt_usd(net_pnl), "pnl"),
            ("Net %", self._fmt_pct_from_notional(net_pnl, notional), "pnl"),
            ("ROE %", self._fmt_pct_from_base(net_pnl, margin), "pnl"),
            ("TP", self._fmt_number(execution.get("take_profit")), "tp"),
            ("SL", self._fmt_number(execution.get("stop_loss")), "sl"),
            ("Exit Trigger", row.get("exit_trigger_type") or row.get("exit_reason"), "generic"),
            ("Trigger Price", self._fmt_number(row.get("exit_trigger_price") or row.get("exit_price")), "generic"),
            ("Exit Check TF", row.get("exit_check_timeframe"), "generic"),
            ("Execution Mode", execution.get("mode"), "generic"),
            ("Force Reason", row.get("force_close_reason") or "—", "generic"),
            ("Closed Candle", self._fmt_timestamp(row.get("exit_trigger_candle_close_ms") or row.get("closed_at")), "generic"),
            ("Opened At", self._fmt_timestamp(row.get("opened_at")), "generic"),
            ("Event Candle Open", row.get("candle_open_time") or "—", "generic"),
            ("Event Candle Close", row.get("candle_close_time") or "—", "generic"),
            ("Duration", row.get("duration_text") or "—", "generic"),
        ]
        return self._detail_payload(details)

    def _detail_payload(self, details: list[tuple[str, Any, str]]) -> list[dict[str, str]]:
        return [
            {"label": str(label), "value": self._format_detail_value(value), "kind": kind}
            for label, value, kind in details
        ]

    @staticmethod
    def _format_detail_value(value: Any) -> str:
        if value in (None, ""):
            return "—"
        return str(value)

    def _build_closed_trade_chart_row(self, row: dict[str, Any]) -> dict[str, Any]:
        execution = self._execution_dict(row)
        position_notional, _ = self._position_notional_and_margin(row, execution)
        net_pnl = row.get("net_pnl")
        return {
            "opened_at": self._fmt_timestamp(row.get("opened_at")),
            "closed_at": row.get("closed_at"),
            "net_pnl": net_pnl,
            "symbol": row.get("symbol"),
            "side": self._display_side(row.get("side")),
            "exit_reason": row.get("exit_reason", row.get("status")),
            "was_force_closed": row.get("was_force_closed"),
            "entry_price": self._fmt_number(execution.get("entry_price")),
            "exit_price": self._fmt_number(row.get("exit_price")),
            "rr_ratio": self._fmt_number(execution.get("rr_ratio")),
            "duration": row.get("duration_text") or "—",
            "net_pct": self._fmt_pct_from_notional(net_pnl, position_notional),
        }

    @staticmethod
    def _execution_dict(row: dict[str, Any]) -> dict[str, Any]:
        execution = row.get("execution")
        return execution if isinstance(execution, dict) else {}

    @staticmethod
    def _position_notional_and_margin(
        row: dict[str, Any], execution: dict[str, Any]
    ) -> tuple[float | None, float | None]:
        position_size = execution.get("position_size")
        margin = execution.get("margin_usdt") or row.get("margin_usdt")
        leverage = row.get("leverage")
        notional_value = PortfolioPageContentService._to_float(position_size)
        margin_value = PortfolioPageContentService._to_float(margin)
        if margin_value is not None:
            return notional_value, margin_value
        if notional_value is None:
            return None, None
        leverage_value = PortfolioPageContentService._to_float(leverage)
        if leverage_value is None:
            return notional_value, None
        if leverage_value <= 0:
            return notional_value, None
        return notional_value * leverage_value, notional_value

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _escape(value: Any) -> str:
        return html.escape(str(value if value not in (None, "") else "—"))

    @staticmethod
    def _value_class(value: Any, *, kind: str = "generic") -> str:
        text = str(value or "").upper()
        if kind == "pnl":
            number = PortfolioPageContentService._numeric_value_for_style(value)
            if number is None:
                return "value-muted"
            if number > 0:
                return "value-green"
            if number < 0:
                return "value-red"
            return "value-muted"
        if kind == "tp":
            return "value-green"
        if kind == "sl":
            return "value-red"
        if text in {"BUY", "LONG", "OPEN", "TP_HIT", "PROFIT_LOCK_HIT"}:
            return "value-green"
        if text in {"SELL", "SHORT", "SL_HIT", "DENIED"}:
            return "value-red"
        if "FORCE" in text or text == "CLOSED":
            return "value-amber"
        return ""

    @staticmethod
    def _numeric_value_for_style(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if not text:
            return None
        cleaned = text.replace("$", "").replace("%", "").replace(",", "").strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _strong(cls, value: Any, *, kind: str = "generic") -> str:
        safe = cls._escape(value)
        value_class = cls._value_class(value, kind=kind)
        if value_class:
            return f'<strong class="{value_class}">{safe}</strong>'
        return f"<strong>{safe}</strong>"

    @staticmethod
    def _display_side(value: Any) -> str:
        side = str(value or "—").upper()
        if side == "BUY":
            return "LONG"
        if side == "SELL":
            return "SHORT"
        if side in {"LONG", "SHORT", "NO_SIGNAL"}:
            return side
        return side if side else "—"

    @staticmethod
    def _fmt_number(value: Any, digits: int = 2) -> str:
        if value is None:
            return "—"
        try:
            return f"{float(value):.{digits}f}"
        except (TypeError, ValueError):
            return "—"

    @staticmethod
    def _fmt_timestamp(value: Any) -> str:
        if value in (None, ""):
            return "—"
        text = str(value).strip()
        if text.isdigit():
            try:
                return datetime.fromtimestamp(int(text) / 1000, UTC).strftime("%Y-%m-%d %H:%M")
            except (OverflowError, ValueError):
                return text
        return text[:16]

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if value in (None, ""):
            return None
        text = str(value).strip()
        if text.isdigit():
            try:
                return datetime.fromtimestamp(int(text) / 1000, UTC)
            except (OverflowError, ValueError):
                return None
        try:
            return datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        except ValueError:
            return None

    @staticmethod
    def _fmt_pct_from_notional(value: Any, position_size: Any) -> str:
        try:
            pnl = float(value)
            size = float(position_size)
        except (TypeError, ValueError):
            return "—"
        if size <= 0:
            return "—"
        return f"{(pnl / size) * 100.0:.2f}%"

    @staticmethod
    def _fmt_pct_from_base(value: Any, base: Any) -> str:
        try:
            pnl = float(value)
            base_value = float(base)
        except (TypeError, ValueError):
            return "—"
        if base_value <= 0:
            return "—"
        return f"{(pnl / base_value) * 100.0:.2f}%"

    @staticmethod
    def _fmt_usd(value: Any, digits: int = 2) -> str:
        if value is None:
            return "—"
        try:
            amount = float(value)
        except (TypeError, ValueError):
            return "—"
        return f"${amount:.{digits}f}"
