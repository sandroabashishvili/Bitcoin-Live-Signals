"""Backend-prepared content builders for the Orderbook page."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any


class OrderbookPageContentService:
    """Build backend-owned content payloads for Orderbook page sections."""

    def build_page_content(
        self,
        *,
        rows: list[dict[str, Any]],
        symbol: str,
        timeframe: str,
    ) -> dict[str, Any]:
        unique_rows = self._latest_unique_rows(rows)
        current_day = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        same_day_rows = [
            row for row in unique_rows if str(row.get("timestamp_text") or "").startswith(current_day)
        ]
        effective_rows = same_day_rows or unique_rows

        buyers_values = [float(row.get("buyers", 0.0) or 0.0) for row in effective_rows]
        sellers_values = [float(row.get("sellers", 0.0) or 0.0) for row in effective_rows]

        cumulative = 0.0
        cumulative_rows: list[dict[str, Any]] = []
        for row in effective_rows:
            delta = float(row.get("buyers", 0.0) or 0.0) - float(row.get("sellers", 0.0) or 0.0)
            cumulative += delta
            enriched = dict(row)
            enriched["delta"] = delta
            enriched["cumulative_delta"] = cumulative
            cumulative_rows.append(enriched)

        history_rows = list(reversed(cumulative_rows))
        latest = history_rows[0] if history_rows else {}
        serialized_rows = [self._serialize_history_row(row) for row in history_rows]

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "latest_orderflow_row": latest,
            "orderflow_snapshot_items": self._build_snapshot_items(
                total_buy=sum(buyers_values),
                total_sell=sum(sellers_values),
                max_buy=max(buyers_values) if buyers_values else 0.0,
                max_sell=max(sellers_values) if sellers_values else 0.0,
                net_delta=sum(float(row["delta"]) for row in cumulative_rows),
                latest_cumulative_delta=float(cumulative_rows[-1]["cumulative_delta"]) if cumulative_rows else 0.0,
                count=len(effective_rows),
                latest=latest,
            ),
            "orderflow_history_section": {
                "title": "Orderflow History",
                "badge": len(history_rows),
                "intro": "Full same-day orderflow history with buy, sell, delta, cumulative delta, and classification.",
                "table_id": "orderbook-history",
                "headers": ["Time", "Buy", "Sell", "Δ", "Cum Δ", "Class"],
                "rows": serialized_rows,
                "empty_text": "No orderbook snapshots recorded yet.",
            },
            "orderflow_chart_rows": serialized_rows,
            "status_summary": {
                "snapshots": len(effective_rows),
                "net_delta": self._fmt_number(sum(float(row["delta"]) for row in cumulative_rows)),
            },
        }

    @staticmethod
    def _latest_unique_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        latest_by_timestamp: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = str(row.get("timestamp_text") or "")
            if not key:
                continue
            latest_by_timestamp[key] = row
        return [latest_by_timestamp[key] for key in sorted(latest_by_timestamp.keys())]

    def _build_snapshot_items(
        self,
        *,
        total_buy: float,
        total_sell: float,
        max_buy: float,
        max_sell: float,
        net_delta: float,
        latest_cumulative_delta: float,
        count: int,
        latest: dict[str, Any],
    ) -> list[dict[str, str]]:
        return [
            self._metric_item("Total Buy (BTC)", self._fmt_number(total_buy), kind="buy"),
            self._metric_item("Total Sell (BTC)", self._fmt_number(total_sell), kind="sell"),
            self._metric_item("Max Buy (BTC)", self._fmt_number(max_buy), kind="buy"),
            self._metric_item("Max Sell (BTC)", self._fmt_number(max_sell), kind="sell"),
            self._metric_item("Net Δ", self._fmt_number(net_delta), kind="delta"),
            self._metric_item("Latest Cum Δ", self._fmt_number(latest_cumulative_delta), kind="delta"),
            self._metric_item("Snapshots", str(count)),
            self._metric_item("Latest Buy", self._fmt_number(latest.get("buyers")), kind="buy"),
            self._metric_item("Latest Sell", self._fmt_number(latest.get("sellers")), kind="sell"),
            self._metric_item("Latest Δ", self._fmt_number(latest.get("delta")), kind="delta"),
            self._metric_item("Latest Timestamp", str(latest.get("timestamp_text") or "—")),
            self._metric_item("Source", str(latest.get("source") or "—")),
        ]

    @staticmethod
    def _metric_item(label: str, value: str, *, kind: str = "generic") -> dict[str, str]:
        return {"label": label, "value": value, "kind": kind}

    def _serialize_history_row(self, row: dict[str, Any]) -> dict[str, str]:
        return {
            "timestamp_text": html.escape(str(row.get("timestamp_text", "—"))),
            "buyers": self._fmt_number(row.get("buyers")),
            "sellers": self._fmt_number(row.get("sellers")),
            "delta": self._fmt_number(row.get("delta")),
            "cumulative_delta": self._fmt_number(row.get("cumulative_delta")),
            "momentum_classification": html.escape(str(row.get("momentum_classification", "neutral"))),
            "imbalance": self._fmt_number(row.get("imbalance"), 4),
            "dominance_ratio": self._fmt_number(row.get("dominance_ratio"), 4),
            "period_count": html.escape(str(row.get("period_count", "—"))),
            "source": html.escape(str(row.get("source", "—"))),
        }

    @staticmethod
    def _fmt_number(value: Any, digits: int = 2) -> str:
        if value is None:
            return "—"
        try:
            return f"{float(value):.{digits}f}"
        except (TypeError, ValueError):
            return "—"
