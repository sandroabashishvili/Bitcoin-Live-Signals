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
            if row.get('completeness') != 'COMPLETE_CLOSED_WINDOW_V1':
                raise ValueError('Legacy or incomplete orderflow cannot be treated as current')
            start, end = int(row['window_start_ms']), int(row['window_end_ms'])
            if timeframe not in {'1m', '5m', '15m', '30m'}:
                raise ValueError('Unsupported Futures orderflow timeframe')
            interval = int(timeframe[:-1]) * 60000
            count = int(row['period_count'])
            first, last = row.get('first_trade_ms'), row.get('last_trade_ms')
            if end-start+1 != interval or end % interval != interval-1 or count < 0:
                raise ValueError('Invalid closed orderflow window')
            if count and (first is None or last is None or not start <= int(first) <= int(last) <= end):
                raise ValueError('Trade times outside orderflow window')
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
                window_start_ms=start, window_end_ms=end,
                first_trade_ms=None if first is None else int(first),
                last_trade_ms=None if last is None else int(last),
                page_count=int(row.get('page_count', 0)),
                completeness=str(row['completeness']),
            )
        except (TypeError, ValueError, KeyError) as exc:
            warn_runtime_fallback(
                scope="futures_orderbook_snapshot_repository",
                operation="parse_latest_snapshot",
                error=exc,
                fallback="return_none",
                extra={"symbol": symbol, "timeframe": timeframe, "source_path": str(source_path)},
            )
            return None
