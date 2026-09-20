"""Build Futures Overview page from futures runtime data."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from platform_v2.futures.config import ExecutionProfile
from platform_v2.shared.backend.persistence import read_market_series_safely
from platform_v2.shared.backend.runtime_store.futures import (
    STRATEGY_GATE_EFFECTIVENESS_REPORTS_FAMILY,
    load_family_documents,
    load_family_rows_all,
    load_latest_document,
)
from platform_v2.futures.storage import candle_file_path, load_json_list
from platform_v2.futures.services.metrics_system import (
    build_overview_trade_outcomes_snapshot_items,
    build_portfolio_capital_snapshot_items,
    build_strategy_activity_evaluation_items,
)

from .renderer import OverviewFuturesPageRenderer


class OverviewFuturesPageBuilder:
    """Generate a static HTML Futures overview page from futures runtime data."""

    _TARGET_DIR = Path(__file__).resolve().parents[1]
    _TARGET_PATH = _TARGET_DIR / "index.html"
    _SOURCE_CSS_PATH = Path(__file__).resolve().parents[1] / "css" / "styles.css"
    _TARGET_CSS_PATH = _TARGET_DIR / "css" / "styles.css"

    def build_and_store(self, *, profile: ExecutionProfile, cycle_summary: Any | None = None) -> Path:
        payload = self._load_payload(profile=profile, cycle_summary=cycle_summary)
        html_text = OverviewFuturesPageRenderer().render(payload)
        self._TARGET_DIR.mkdir(parents=True, exist_ok=True)
        self._TARGET_PATH.write_text(html_text, encoding="utf-8")
        self._copy_css()
        return self._TARGET_PATH

    def _copy_css(self) -> None:
        if not self._SOURCE_CSS_PATH.exists():
            return
        if self._SOURCE_CSS_PATH.resolve() == self._TARGET_CSS_PATH.resolve():
            return
        self._TARGET_CSS_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._TARGET_CSS_PATH.write_text(self._SOURCE_CSS_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    def _load_payload(self, *, profile: ExecutionProfile, cycle_summary: Any | None) -> dict[str, Any]:
        generated_at = datetime.now(tz=UTC).strftime("%d.%m.%Y %H:%M:%S UTC")
        metrics_file, metrics = self._load_latest_metrics()
        signal_file, latest_signal, all_signals = self._load_latest_signal()
        strategy_report_file, strategy_report = self._load_latest_family_dict(
            STRATEGY_GATE_EFFECTIVENESS_REPORTS_FAMILY
        )
        orders_file, orders = self._load_family_rows("futures_orders")
        denied_file, denied_entries = self._load_family_rows("futures_denied_entries")

        metrics_data = metrics if isinstance(metrics, dict) else {}
        signal_data = latest_signal if isinstance(latest_signal, dict) else {}
        matched_order = self._match_order(signal_data, orders)
        matched_denied = self._match_denied_entry(signal_data, denied_entries)

        runtime_health = {
            "candles": self._health_status_for_candles(profile.symbol),
            "signals": "Ready" if signal_file != "No file" else "No file",
            "metrics": "Ready" if metrics_file != "No file" else "No file",
        }

        timeframe_cards = self._build_timeframe_context_cards(
            symbol=profile.symbol,
            latest_signal=signal_data,
        )
        equity_chart_rows = self._load_equity_chart_rows()

        signal_activity_summary = self._signal_activity_from_report(strategy_report)
        strategy_items = build_strategy_activity_evaluation_items(signal_activity_summary)

        return {
            "generated_at": generated_at,
            "profile": {
                "symbol": profile.symbol,
                "timeframe": profile.timeframe,
                "mode": profile.mode,
                "leverage": profile.leverage,
                "margin_mode": profile.margin_mode,
                "order_size_usdt": profile.order_size_usdt,
                "starting_balance": profile.starting_balance,
            },
            "runtime_health": runtime_health,
            "metrics_file": metrics_file,
            "signal_file": signal_file,
            "strategy_report_file": strategy_report_file,
            "orders_file": orders_file,
            "denied_file": denied_file,
            "metrics": metrics_data,
            "latest_signal": signal_data,
            "latest_order": matched_order,
            "latest_denied_entry": matched_denied,
            "portfolio_snapshot_items": build_portfolio_capital_snapshot_items(metrics_data),
            "trade_outcomes_snapshot_items": build_overview_trade_outcomes_snapshot_items(metrics_data),
            "strategy_snapshot_items": strategy_items,
            "timeframe_context_cards": timeframe_cards,
            "equity_chart_rows": equity_chart_rows,
            "signals_count": len(all_signals),
            "latest_market_price": self._latest_market_price(symbol=profile.symbol, timeframe=profile.timeframe),
        }

    @staticmethod
    def _signal_activity_from_report(report: dict[str, Any]) -> dict[str, Any]:
        payload = report.get("signal_activity_summary")
        if isinstance(payload, dict):
            return payload
        return {
            "total_signals": 0,
            "buy_signals": 0,
            "short_signals": 0,
            "no_signal": 0,
            "theoretical_tp_hits": 0,
            "theoretical_sl_hits": 0,
            "theoretical_open_signals": 0,
            "signal_win_rate": 0.0,
        }

    def _load_latest_metrics(self) -> tuple[str, dict[str, Any]]:
        payload = load_latest_document("futures_metrics")
        return ("database:futures_metrics", payload) if isinstance(payload, dict) else ("No data", {})

    def _load_latest_family_dict(self, family_name: str) -> tuple[str, dict[str, Any]]:
        payload = load_latest_document(family_name)
        return (f"database:{family_name}", payload) if isinstance(payload, dict) else ("No data", {})

    def _load_latest_signal(self) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
        rows = load_family_rows_all("futures_signals")
        if not rows:
            return "No data", {}, []
        rows.sort(key=lambda row: int(row.get("timestamp_ms") or 0))
        return "database:futures_signals", rows[-1], rows


    def _load_family_rows(self, family_name: str) -> tuple[str, list[dict[str, Any]]]:
        rows = load_family_rows_all(family_name)
        return (f"database:{family_name}" if rows else "No data"), rows

    def _load_equity_chart_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for date_iso, payload in load_family_documents("futures_metrics"):
            if not isinstance(payload, dict):
                continue
            rows.append(
                {
                    "date": date_iso,
                    "datetime": f"{date_iso}T00:00:00Z",
                    "starting_capital": payload.get("starting_capital"),
                    "equity": payload.get("equity"),
                }
            )
        return rows

    def _build_timeframe_context_cards(
        self,
        *,
        symbol: str,
        latest_signal: dict[str, Any],
    ) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        mtf_signals = self._normalize_mtf_signals(latest_signal.get("mtf_signals"))
        timeframe_roles = {
            "5m": "Fast momentum and short-term pressure.",
            "15m": "Primary timeframe used for the signal decision.",
            "4h": "Broader trend and market backdrop.",
        }
        for timeframe in ("5m", "15m", "4h"):
            rows = load_json_list(candle_file_path(symbol, timeframe))
            label = self._tf_label(timeframe)
            if not rows:
                cards.append({
                    "label": f"{label} Trend",
                    "signal": "NO DATA",
                    "role": timeframe_roles[timeframe],
                    "stats": [{"label": "Status", "value": "No candle data", "kind": "neutral"}],
                })
                continue

            latest = rows[-1]
            prev = rows[-2] if len(rows) > 1 else rows[-1]
            close = self._as_float(latest.get("close"))
            prev_close = self._as_float(prev.get("close"))
            volume = self._as_float(latest.get("volume"))
            change_pct = None
            if close is not None and prev_close not in (None, 0.0):
                change_pct = ((close - prev_close) / prev_close) * 100.0
            signal = str(mtf_signals.get(timeframe) or "")
            if signal == "BUY":
                signal = "LONG"
            elif signal == "SELL":
                signal = "SHORT"
            if signal not in {"LONG", "SHORT", "NO_SIGNAL"}:
                signal = "LONG" if change_pct is not None and change_pct >= 0 else "NO_SIGNAL"
            cards.append(
                {
                    "label": f"{label} Direction",
                    "signal": signal,
                    "role": timeframe_roles[timeframe],
                    "stats": [
                        {
                            "label": "Close",
                            "value": f"{close:.2f}" if close is not None else "—",
                            "kind": "neutral",
                        },
                        {
                            "label": "Change",
                            "value": f"{change_pct:.2f}%" if change_pct is not None else "—",
                            "kind": "tp" if (change_pct or 0) >= 0 else "sl",
                        },
                        {
                            "label": "Volume",
                            "value": f"{volume:.2f}" if volume is not None else "—",
                            "kind": "neutral",
                        },
                        {
                            "label": "Rows",
                            "value": str(len(rows)),
                            "kind": "neutral",
                        },
                    ],
                }
            )
        return cards

    def _latest_market_price(self, *, symbol: str, timeframe: str) -> float | None:
        rows = load_json_list(candle_file_path(symbol, timeframe))
        if not rows:
            return None
        return self._as_float(rows[-1].get("close"))

    @staticmethod
    def _normalize_mtf_signals(value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        normalized: dict[str, str] = {}
        for key, raw in value.items():
            timeframe = str(key or "").strip()
            if not timeframe:
                continue
            signal = str(raw or "").strip().upper()
            normalized[timeframe] = signal
        return normalized

    @staticmethod
    def _match_order(signal: dict[str, Any], orders: list[dict[str, Any]]) -> dict[str, Any] | None:
        signal_ts = OverviewFuturesPageBuilder._as_int(signal.get("timestamp_ms"))
        signal_side = str(signal.get("side") or "").upper()
        signal_symbol = str(signal.get("symbol") or "").upper()
        signal_tf = str(signal.get("timeframe") or "")
        if signal_side == "BUY":
            signal_side = "LONG"
        if signal_side == "SELL":
            signal_side = "SHORT"
        if signal_ts is None or signal_side not in {"LONG", "SHORT"}:
            return None
        for order in reversed(orders):
            request = order.get("request") or {}
            req_ts = (
                OverviewFuturesPageBuilder._as_int(order.get("signal_timestamp_ms"))
                or OverviewFuturesPageBuilder._as_int(request.get("requested_at_ms"))
                or OverviewFuturesPageBuilder._as_int(order.get("timestamp_ms"))
            )
            req_side = str(request.get("side") or order.get("side") or "").upper()
            if req_side == "BUY":
                req_side = "LONG"
            elif req_side == "SELL":
                req_side = "SHORT"
            req_symbol = str(request.get("symbol") or order.get("symbol") or "").upper()
            req_tf = str(request.get("timeframe") or order.get("timeframe") or "")
            if (
                req_ts == signal_ts
                and req_side == signal_side
                and req_symbol == signal_symbol
                and req_tf == signal_tf
            ):
                return order
        return None

    @staticmethod
    def _match_denied_entry(signal: dict[str, Any], denied_entries: list[dict[str, Any]]) -> dict[str, Any] | None:
        signal_ts = OverviewFuturesPageBuilder._as_int(signal.get("timestamp_ms"))
        signal_side = str(signal.get("side") or "").upper()
        signal_symbol = str(signal.get("symbol") or "").upper()
        signal_tf = str(signal.get("timeframe") or "")
        if signal_ts is None or not signal_side:
            return None
        for denied in reversed(denied_entries):
            denied_signal = denied.get("signal") or {}
            denied_ts = (
                OverviewFuturesPageBuilder._as_int(denied_signal.get("timestamp_ms"))
                or OverviewFuturesPageBuilder._as_int(denied.get("timestamp_ms"))
            )
            denied_side = str(
                denied_signal.get("side")
                or denied.get("signal_side")
                or denied.get("side")
                or ""
            ).upper()
            denied_symbol = str(
                denied_signal.get("symbol")
                or denied.get("symbol")
                or ""
            ).upper()
            denied_tf = str(
                denied_signal.get("timeframe")
                or denied.get("timeframe")
                or ""
            )
            if (
                denied_ts == signal_ts
                and denied_side == signal_side
                and denied_symbol == signal_symbol
                and denied_tf == signal_tf
            ):
                return denied
        return None

    @staticmethod
    def _health_status_for_candles(symbol: str) -> str:
        expected = ("5m", "15m", "4h")
        present = sum(
            bool(
                read_market_series_safely(
                    venue="binance",
                    asset_class="crypto",
                    market_type="futures",
                    dataset="candles",
                    symbol=symbol,
                    timeframe=timeframe,
                )
            )
            for timeframe in expected
        )
        if present == len(expected):
            return f"Ready ({present}/{len(expected)})"
        if present == 0:
            return f"Unavailable (0/{len(expected)})"
        return f"Partial ({present}/{len(expected)})"

    @staticmethod
    def _date_from_metrics_filename(name: str) -> str:
        prefix = "futures_metrics_"
        if name.startswith(prefix) and name.endswith(".json"):
            return name[len(prefix) : -5]
        return datetime.now(tz=UTC).strftime("%Y-%m-%d")

    @staticmethod
    def _as_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _tf_label(timeframe: str) -> str:
        if timeframe == "5m":
            return "5m"
        if timeframe == "15m":
            return "15m"
        if timeframe == "4h":
            return "4h"
        return timeframe
