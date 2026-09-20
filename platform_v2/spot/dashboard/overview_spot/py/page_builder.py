"""Build a static SEO-friendlier Overview page from V2 data."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from platform_v2.spot.config import settings
from platform_v2.spot.dashboard.overview_spot.py.renderer import OverviewPageRenderer
from platform_v2.spot.services.account.position_state_service import PositionStateService
from platform_v2.spot.services.metrics_system import (
    OverviewPageContentService,
    build_overview_trade_outcomes_snapshot_items,
    build_portfolio_capital_snapshot_items,
)
from platform_v2.shared.backend.runtime_store.spot import (
    load_family_rows_all,
    load_json_dict,
    load_json_list,
    load_latest_document,
)
from platform_v2.shared.backend.persistence import read_market_series_safely
from platform_v2.spot.storage.paths import indicator_snapshots_root


class OverviewPageService:
    """Generate a static HTML overview page from current V2 data."""

    _TARGET_DIR = Path(__file__).resolve().parents[1]
    _TARGET_PATH = _TARGET_DIR / "index.html"

    def __init__(self, position_state_service: PositionStateService | None = None) -> None:
        self._position_state_service = position_state_service or PositionStateService()

    def build_and_store(self, *, symbol: str = settings.DEFAULT_SYMBOL) -> Path:
        payload = self._load_payload(symbol=symbol)
        html_text = OverviewPageRenderer().render(payload)
        self._TARGET_DIR.mkdir(parents=True, exist_ok=True)
        self._TARGET_PATH.write_text(html_text, encoding="utf-8")
        return self._TARGET_PATH

    def _load_payload(self, *, symbol: str) -> dict[str, Any]:
        signal_file, signals = self._load_latest_rows("signals")
        _, all_signals = self._load_all_family_rows("signals")
        denied_file, denied_entries = self._load_latest_rows("denied_entries")
        orders_file, orders = self._load_latest_rows("orders")
        positions_file, positions = self._load_latest_rows("positions")
        metrics_file, metrics = self._load_latest_metrics()
        daily_summary_file, daily_summary = self._load_latest_family_dict("daily_summaries")

        latest_signal = signals[-1] if signals else None
        denied_tail = denied_entries[-3:] if denied_entries else []
        orders_tail = orders[-3:] if orders else []
        matched_denied = self._match_denied_entry(latest_signal, denied_entries)
        matched_order = self._match_order(latest_signal, orders)
        matched_position = self._match_position(latest_signal, positions)

        timeframe_snapshots = []
        for timeframe in settings.DEFAULT_CANDLE_TIMEFRAMES:
            indicator_rows = read_market_series_safely(
                venue="binance",
                asset_class="crypto",
                market_type="spot",
                dataset="indicators",
                symbol=symbol,
                timeframe=timeframe,
            )
            if not indicator_rows:
                path = indicator_snapshots_root() / symbol / f"{timeframe}.json"
                indicator_rows = self._load_json_list(path)

            candle_rows = read_market_series_safely(
                venue="binance",
                asset_class="crypto",
                market_type="spot",
                dataset="candles",
                symbol=symbol,
                timeframe=timeframe,
            )
            snapshot = dict(indicator_rows[-1]) if indicator_rows else None
            if snapshot is not None and candle_rows:
                latest_candle = candle_rows[-1]
                previous_candle = candle_rows[-2] if len(candle_rows) > 1 else latest_candle
                close = self._as_float(latest_candle.get("close"))
                previous_close = self._as_float(previous_candle.get("close"))
                change_pct = None
                if close is not None and previous_close not in (None, 0.0):
                    change_pct = ((close - previous_close) / previous_close) * 100.0
                snapshot["overview_close"] = close
                snapshot["overview_change_pct"] = change_pct
                snapshot["overview_volume"] = self._as_float(latest_candle.get("volume"))
            timeframe_snapshots.append(snapshot)

        candles_health = self._market_health("candles", symbol, ("5m", "15m", "4h"))
        indicators_health = self._market_health("indicators", symbol, ("5m", "15m", "4h"))
        orderbook_health = self._market_health("orderflow", symbol, (settings.DEFAULT_TIMEFRAME,))
        overview_content = OverviewPageContentService(self._position_state_service).build_content(
            latest_signal=latest_signal,
            signals=all_signals,
            denied_entries=denied_entries,
            metrics=metrics,
            timeframe_snapshots=timeframe_snapshots,
            symbol=symbol,
            candles_health=candles_health,
            indicators_health=indicators_health,
            orderbook_health=orderbook_health,
        )

        return {
            "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "symbol": symbol,
            "signal_file": signal_file,
            "denied_file": denied_file,
            "orders_file": orders_file,
            "positions_file": positions_file,
            "metrics_file": metrics_file,
            "latest_signal": latest_signal,
            "latest_order": matched_order,
            "latest_position": matched_position,
            "latest_denied_entry": matched_denied,
            "denied_entries": denied_tail,
            "orders": orders_tail,
            "metrics": metrics,
            "equity_chart_rows": overview_content.get("equity_chart_rows") or [],
            "runtime_health": overview_content.get("runtime_health") or {},
            "portfolio_snapshot_items": build_portfolio_capital_snapshot_items(metrics),
            "trade_outcomes_snapshot_items": build_overview_trade_outcomes_snapshot_items(metrics),
            "daily_summary_file": daily_summary_file,
            "daily_summary": daily_summary,
            **overview_content,
        }

    @staticmethod
    def _load_json_list(path: Path) -> list[dict[str, Any]]:
        return load_json_list(path)

    @staticmethod
    def _load_json_dict(path: Path) -> dict[str, Any]:
        return load_json_dict(path)

    @staticmethod
    def _as_float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _load_latest_rows(self, family_name: str) -> tuple[str, list[dict[str, Any]]]:
        payload = load_latest_document(family_name)
        rows = [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []
        return (f"database:{family_name}" if rows else "No data"), rows

    def _load_all_family_rows(self, family_name: str) -> tuple[str, list[dict[str, Any]]]:
        rows = load_family_rows_all(family_name)
        return (f"database:{family_name}:history" if rows else "No data"), rows

    def _load_latest_metrics(self) -> tuple[str, dict[str, Any]]:
        payload = load_latest_document("metrics")
        return ("database:metrics", payload) if isinstance(payload, dict) else ("No data", {})

    def _load_latest_family_dict(self, family_name: str) -> tuple[str, dict[str, Any]]:
        payload = load_latest_document(family_name)
        return (f"database:{family_name}", payload) if isinstance(payload, dict) else ("No data", {})

    @staticmethod
    def _parse_int(value: Any):
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            if stripped.isdigit() or (stripped.startswith("-") and stripped[1:].isdigit()):
                return int(stripped)
        return None

    @staticmethod
    def _market_health(dataset: str, symbol: str, timeframes: tuple[str, ...]) -> str:
        present = sum(
            bool(
                read_market_series_safely(
                    venue="binance",
                    asset_class="crypto",
                    market_type="spot",
                    dataset=dataset,
                    symbol=symbol,
                    timeframe=timeframe,
                )
            )
            for timeframe in timeframes
        )
        if present == len(timeframes):
            return f"Ready ({present}/{len(timeframes)})"
        if present == 0:
            return f"Unavailable (0/{len(timeframes)})"
        return f"Partial ({present}/{len(timeframes)})"

    @classmethod
    def _match_denied_entry(
        cls,
        latest_signal: dict[str, Any] | None,
        denied_entries: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not latest_signal:
            return None
        signal_ts = cls._parse_int(latest_signal.get("timestamp_ms"))
        signal_side = str(latest_signal.get("side") or "").upper()
        signal_tf = str(latest_signal.get("timeframe") or "")
        if signal_ts is None or not signal_side:
            return None
        for denied in reversed(denied_entries):
            denied_signal = denied.get("signal") or {}
            denied_ts = cls._parse_int(denied_signal.get("timestamp_ms"))
            denied_side = str(denied_signal.get("side") or "").upper()
            denied_tf = str(denied_signal.get("timeframe") or "")
            if denied_ts == signal_ts and denied_side == signal_side and denied_tf == signal_tf:
                return denied
        return None

    @classmethod
    def _match_order(
        cls,
        latest_signal: dict[str, Any] | None,
        orders: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not latest_signal:
            return None
        signal_ts = cls._parse_int(latest_signal.get("timestamp_ms"))
        signal_side = str(latest_signal.get("side") or "").upper()
        signal_tf = str(latest_signal.get("timeframe") or "")
        signal_symbol = str(latest_signal.get("symbol") or settings.DEFAULT_SYMBOL)
        if signal_ts is None or signal_side != "BUY":
            return None
        window_end = signal_ts + (15 * 60 * 1000)
        for order in reversed(orders):
            request = order.get("request") or {}
            requested_at = cls._parse_int(request.get("requested_at_ms"))
            order_side = str(request.get("side") or "").upper()
            order_tf = str(request.get("timeframe") or "")
            order_symbol = str(request.get("symbol") or "")
            if (
                requested_at is not None
                and signal_ts <= requested_at <= window_end
                and order_side == signal_side
                and order_tf == signal_tf
                and order_symbol == signal_symbol
            ):
                return order
        return None

    @classmethod
    def _match_position(
        cls,
        latest_signal: dict[str, Any] | None,
        positions: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not latest_signal:
            return None
        signal_ts = cls._parse_int(latest_signal.get("timestamp_ms"))
        if signal_ts is None:
            return None
        signal_close = datetime.utcfromtimestamp(signal_ts / 1000).strftime("%Y-%m-%d %H:%M:%S")
        for position in reversed(positions):
            if str(position.get("signal_candle_close_time") or "") == signal_close:
                return position
        return None
