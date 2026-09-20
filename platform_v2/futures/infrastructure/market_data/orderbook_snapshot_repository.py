"""Read normalized futures orderflow snapshots from runtime storage."""

from __future__ import annotations

from typing import Protocol

from platform_v2.futures.domain.models.orderbook_snapshot import OrderbookSnapshot
from platform_v2.futures.storage import load_json_list, orderflow_file_path
from platform_v2.shared.backend.persistence import read_market_series_safely
from platform_v2.shared.runtime_warnings import warn_runtime_fallback


class OrderbookSnapshotRepository(Protocol):
    def get_latest_snapshot(self, symbol: str, timeframe: str) -> OrderbookSnapshot | None: ...


class JsonOrderbookSnapshotRepository:
    def __init__(self) -> None:
        pass

    def get_latest_snapshot(self, symbol: str, timeframe: str) -> OrderbookSnapshot | None:
        source_path = orderflow_file_path(symbol, timeframe)
        raw_rows = read_market_series_safely(
            venue="binance",
            asset_class="crypto",
            market_type="futures",
            dataset="orderflow",
            symbol=symbol,
            timeframe=timeframe,
        ) or load_json_list(source_path)
        if not raw_rows:
            return None

        row = raw_rows[-1]
        if not isinstance(row, dict):
            return None

        try:
            return OrderbookSnapshot(
                symbol=str(row.get("symbol") or symbol),
                timeframe=str(row.get("timeframe") or timeframe),
                timestamp_text=str(row.get("timestamp_text") or row.get("datetime") or ""),
                buyers=float(row.get("buyers", 0.0) or 0.0),
                sellers=float(row.get("sellers", 0.0) or 0.0),
                dominance_ratio=float(row.get("dominance_ratio", 0.0) or 0.0),
                imbalance=float(row.get("imbalance", 0.0) or 0.0),
                momentum_classification=str(
                    row.get("momentum_classification") or row.get("classification") or "neutral"
                ),
                period_count=int(row.get("period_count", 0) or 0),
                source=str(row.get("source") or "binance_futures_aggtrades"),
            )
        except (TypeError, ValueError) as exc:
            warn_runtime_fallback(
                scope="futures_orderbook_snapshot_repository",
                operation="parse_latest_snapshot",
                error=exc,
                fallback="return_none",
                extra={"symbol": symbol, "timeframe": timeframe, "source_path": str(source_path)},
            )
            return None
