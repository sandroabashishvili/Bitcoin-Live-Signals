"""File: orderbook_snapshot_repository.py
Folder: platform_v2/spot/infrastructure/market_data
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Read normalized V2 orderflow snapshots from runtime storage.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from ...domain.models.orderbook_snapshot import OrderbookSnapshot
from ...storage.paths import orderflow_root as v2_orderflow_root
from platform_v2.shared.backend.persistence import read_market_series_safely
from platform_v2.shared.runtime_warnings import warn_runtime_fallback


class OrderbookSnapshotRepository(Protocol):
    """Repository contract for normalized orderbook snapshot access."""

    def get_latest_snapshot(self, symbol: str, timeframe: str) -> OrderbookSnapshot | None:
        """Return the latest available orderbook snapshot."""
        ...


class JsonOrderbookSnapshotRepository:
    """Read normalized orderbook snapshots from V2 JSON storage."""

    def __init__(self, orderflow_root: Path | None = None) -> None:
        self._use_database = orderflow_root is None
        if orderflow_root is None:
            orderflow_root = v2_orderflow_root()
        self._orderflow_root = orderflow_root

    def get_latest_snapshot(self, symbol: str, timeframe: str) -> OrderbookSnapshot | None:
        source_path = self._orderflow_root / symbol / f"{timeframe}.json"
        try:
            raw_rows = (
                read_market_series_safely(
                    venue="binance",
                    asset_class="crypto",
                    market_type="spot",
                    dataset="orderflow",
                    symbol=symbol,
                    timeframe=timeframe,
                )
                if self._use_database
                else []
            )
            if not raw_rows:
                if not source_path.exists():
                    return None
                raw_rows = json.loads(source_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            warn_runtime_fallback(
                scope="spot_orderbook_snapshot_repository",
                operation="load_latest_snapshot_rows",
                error=exc,
                fallback="return_none",
                extra={"symbol": symbol, "timeframe": timeframe, "source_path": str(source_path)},
            )
            return None

        if not isinstance(raw_rows, list) or not raw_rows:
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
                source=str(row.get("source") or "binance_aggtrades"),
            )
        except (TypeError, ValueError) as exc:
            warn_runtime_fallback(
                scope="spot_orderbook_snapshot_repository",
                operation="parse_latest_snapshot",
                error=exc,
                fallback="return_none",
                extra={"symbol": symbol, "timeframe": timeframe, "source_path": str(source_path)},
            )
            return None
