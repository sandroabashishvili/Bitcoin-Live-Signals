"""File: binance_orderbook_service.py
Folder: platform_v2/spot/services
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Build a V2 orderflow proxy snapshot from Binance aggTrades data.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from platform_v2.spot.domain.models.orderbook_snapshot import OrderbookSnapshot
from platform_v2.spot.storage.paths import orderflow_file_path
from platform_v2.shared.backend.persistence import read_market_series_safely, replace_market_series


class BinanceOrderbookService:
    """Fetch recent Binance aggTrades and build a normalized trade-flow snapshot."""

    base_url = "https://api.binance.com/api/v3/aggTrades"

    def fetch_and_store(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int = 1000,
        lookback_hours: int = 24,
    ) -> Path:
        """Fetch recent aggTrades, build one snapshot, and append it to V2 storage."""

        end_time = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        start_time = int(
            (datetime.now(tz=timezone.utc) - timedelta(hours=lookback_hours)).timestamp() * 1000
        )
        trades = self._request_aggtrades(
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        snapshot = self._build_snapshot(symbol=symbol, timeframe=timeframe, trades=trades)
        target_path = orderflow_file_path(symbol, timeframe)
        rows = read_market_series_safely(
            venue="binance", asset_class="crypto", market_type="spot",
            dataset="orderflow", symbol=symbol, timeframe=timeframe,
        )
        row = {
            "symbol": snapshot.symbol,
            "timeframe": snapshot.timeframe,
            "timestamp_text": snapshot.timestamp_text,
            "buyers": snapshot.buyers,
            "sellers": snapshot.sellers,
            "dominance_ratio": snapshot.dominance_ratio,
            "imbalance": snapshot.imbalance,
            "momentum_classification": snapshot.momentum_classification,
            "period_count": snapshot.period_count,
            "source": snapshot.source,
        }
        rows = self._merge_snapshot_row(rows, row)
        replace_market_series(
            venue="binance",
            asset_class="crypto",
            market_type="spot",
            dataset="orderflow",
            symbol=symbol,
            timeframe=timeframe,
            rows=rows,
            source_path=target_path,
        )
        return target_path

    def _request_aggtrades(
        self,
        *,
        symbol: str,
        start_time: int,
        end_time: int,
        limit: int,
    ) -> list[dict]:
        """Fetch raw aggTrades payload from Binance."""

        params = urlencode(
            {
                "symbol": symbol,
                "startTime": start_time,
                "endTime": end_time,
                "limit": limit,
            }
        )
        url = f"{self.base_url}?{params}"
        with urlopen(url, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        return []

    @staticmethod
    def _build_snapshot(
        *,
        symbol: str,
        timeframe: str,
        trades: list[dict],
    ) -> OrderbookSnapshot:
        """Aggregate raw aggTrades into one normalized orderbook snapshot."""

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

        timestamp_text = BinanceOrderbookService._cycle_timestamp_text(timeframe)
        return OrderbookSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            timestamp_text=timestamp_text,
            buyers=round(buyers, 8),
            sellers=round(sellers, 8),
            dominance_ratio=round(dominance_ratio, 6),
            imbalance=round(imbalance, 6),
            momentum_classification=classification,
            period_count=len(trades),
        )

    @staticmethod
    def _cycle_timestamp_text(timeframe: str) -> str:
        """Normalize snapshot time to the active timeframe boundary in UTC."""

        now = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0)
        if timeframe.endswith("m"):
            minutes = max(int(timeframe[:-1] or 0), 1)
            normalized_minute = (now.minute // minutes) * minutes
            now = now.replace(minute=normalized_minute)
        elif timeframe.endswith("h"):
            hours = max(int(timeframe[:-1] or 0), 1)
            normalized_hour = (now.hour // hours) * hours
            now = now.replace(hour=normalized_hour, minute=0)
        return now.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _row_signature(row: dict) -> tuple:
        """Build a comparable signature that ignores timestamp jitter."""

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
        )

    @classmethod
    def _merge_snapshot_row(cls, rows: list[dict], row: dict) -> list[dict]:
        """Merge one snapshot row into existing rows without duplicates."""

        normalized: list[dict] = []
        by_timestamp: dict[str, dict] = {}
        for existing in rows:
            timestamp_text = cls._normalize_timestamp_text(
                str(existing.get("timestamp_text") or ""),
                str(existing.get("timeframe") or row.get("timeframe") or ""),
            )
            if not timestamp_text:
                continue
            existing = dict(existing)
            existing["timestamp_text"] = timestamp_text
            by_timestamp[timestamp_text] = existing

        timestamp_text = cls._normalize_timestamp_text(
            str(row.get("timestamp_text") or ""),
            str(row.get("timeframe") or ""),
        )
        row = dict(row)
        row["timestamp_text"] = timestamp_text
        existing_same_timestamp = by_timestamp.get(timestamp_text)
        if existing_same_timestamp is not None:
            if cls._row_signature(existing_same_timestamp) == cls._row_signature(row):
                pass
            else:
                by_timestamp[timestamp_text] = row
        else:
            if rows and cls._row_signature(rows[-1]) == cls._row_signature(row):
                by_timestamp[str(rows[-1].get("timestamp_text") or timestamp_text)] = row
            else:
                by_timestamp[timestamp_text] = row

        for key in sorted(by_timestamp.keys()):
            normalized.append(by_timestamp[key])
        return normalized

    @classmethod
    def _normalize_timestamp_text(cls, timestamp_text: str, timeframe: str) -> str:
        """Normalize a stored timestamp text to the timeframe boundary."""

        if not timestamp_text:
            return ""
        try:
            parsed = datetime.strptime(timestamp_text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return timestamp_text

        if timeframe.endswith("m"):
            minutes = max(int(timeframe[:-1] or 0), 1)
            parsed = parsed.replace(second=0, microsecond=0, minute=(parsed.minute // minutes) * minutes)
        elif timeframe.endswith("h"):
            hours = max(int(timeframe[:-1] or 0), 1)
            parsed = parsed.replace(second=0, microsecond=0, minute=0, hour=(parsed.hour // hours) * hours)
        return parsed.strftime("%Y-%m-%d %H:%M:%S")
