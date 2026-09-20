"""Build orderflow proxy snapshots from Binance Futures aggTrades."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from platform_v2.futures.storage import orderflow_file_path
from platform_v2.shared.backend.persistence import read_market_series_safely, replace_market_series
from platform_v2.shared.runtime_warnings import warn_runtime_fallback


class BinanceFuturesOrderflowService:
    BASE_URL = "https://fapi.binance.com/fapi/v1/aggTrades"

    def fetch_and_store(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int = 1000,
        lookback_hours: int = 24,
    ) -> Path:
        end_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
        start_ms = int((datetime.now(tz=UTC) - timedelta(hours=lookback_hours)).timestamp() * 1000)
        trades = self._request_aggtrades(symbol=symbol, start_time=start_ms, end_time=end_ms, limit=limit)
        row = self._build_snapshot_row(symbol=symbol, timeframe=timeframe, trades=trades)
        path = orderflow_file_path(symbol, timeframe)
        existing = read_market_series_safely(
            venue="binance", asset_class="crypto", market_type="futures",
            dataset="orderflow", symbol=symbol, timeframe=timeframe,
        )
        merged = self._merge_snapshot_row(existing, row)
        replace_market_series(
            venue="binance",
            asset_class="crypto",
            market_type="futures",
            dataset="orderflow",
            symbol=symbol,
            timeframe=timeframe,
            rows=merged,
            source_path=path,
        )
        return path

    def _request_aggtrades(self, *, symbol: str, start_time: int, end_time: int, limit: int) -> list[dict]:
        query = urlencode(
            {
                "symbol": symbol,
                "startTime": start_time,
                "endTime": end_time,
                "limit": limit,
            }
        )
        try:
            with urlopen(f"{self.BASE_URL}?{query}", timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (URLError, OSError, ValueError) as exc:
            warn_runtime_fallback(
                scope="binance_futures_orderflow_service",
                operation="request_aggtrades",
                error=exc,
                fallback="return_empty_trades",
                extra={"symbol": symbol, "start_time": start_time, "end_time": end_time, "limit": limit},
            )
            return []
        if not isinstance(payload, list):
            return []
        return [row for row in payload if isinstance(row, dict)]

    @staticmethod
    def _build_snapshot_row(*, symbol: str, timeframe: str, trades: list[dict]) -> dict:
        buyers = 0.0
        sellers = 0.0
        for trade in trades:
            qty = float(trade.get("q", 0.0) or 0.0)
            if bool(trade.get("m")):
                sellers += qty
            else:
                buyers += qty

        total = buyers + sellers
        dominance_ratio = ((buyers - sellers) / total) if total > 0 else 0.0
        imbalance = dominance_ratio
        if dominance_ratio > 0.3:
            classification = "bullish"
        elif dominance_ratio < -0.3:
            classification = "bearish"
        else:
            classification = "neutral"

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp_text": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S"),
            "buyers": round(buyers, 8),
            "sellers": round(sellers, 8),
            "dominance_ratio": round(dominance_ratio, 6),
            "imbalance": round(imbalance, 6),
            "momentum_classification": classification,
            "period_count": len(trades),
            "source": "binance_futures_aggTrades",
            "market": "futures",
        }

    @staticmethod
    def _row_signature(row: dict) -> tuple:
        return (
            row.get("symbol"),
            row.get("timeframe"),
            row.get("buyers"),
            row.get("sellers"),
            row.get("dominance_ratio"),
            row.get("imbalance"),
            row.get("momentum_classification"),
            row.get("period_count"),
            row.get("source"),
            row.get("market"),
        )

    @classmethod
    def _merge_snapshot_row(cls, rows: list[dict], row: dict) -> list[dict]:
        by_timestamp: dict[str, dict] = {}
        for existing in rows:
            ts = str(existing.get("timestamp_text") or "")
            if not ts:
                continue
            by_timestamp[ts] = dict(existing)
        ts = str(row.get("timestamp_text") or "")
        if ts in by_timestamp and cls._row_signature(by_timestamp[ts]) == cls._row_signature(row):
            pass
        else:
            by_timestamp[ts] = dict(row)
        return [by_timestamp[key] for key in sorted(by_timestamp.keys())]
