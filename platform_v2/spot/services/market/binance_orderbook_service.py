"""File: binance_orderbook_service.py
Folder: platform_v2/spot/services
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Build a V2 orderflow proxy snapshot from Binance aggTrades data.
"""

from __future__ import annotations

import math
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from platform_v2.shared.backend.market import BinancePublicHttpClient

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
        close_time_ms: int | None = None,
        max_pages: int = 200,
        deadline_seconds: float = 120,
    ) -> Path:
        """Publish only a fully enumerated closed candle; failures never publish a prefix."""
        interval = self._interval_ms(timeframe)
        now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        end_time = now_ms // interval * interval - 1 if close_time_ms is None else close_time_ms
        if isinstance(end_time, bool) or not isinstance(end_time, int) or end_time < interval - 1 or end_time % interval != interval - 1 or end_time >= now_ms:
            raise ValueError('Orderflow requires an aligned, already closed candle')
        start_time = end_time - interval + 1
        trades, pages = self._collect_window(symbol, start_time, end_time, limit, max_pages, deadline_seconds)
        snapshot = self._build_snapshot(symbol=symbol, timeframe=timeframe, trades=trades,
                                        window_start_ms=start_time, window_end_ms=end_time, page_count=pages)
        target_path = orderflow_file_path(symbol, timeframe)
        rows = read_market_series_safely(
            venue="binance", asset_class="crypto", market_type="spot",
            dataset="orderflow", symbol=symbol, timeframe=timeframe,
        )
        row = asdict(snapshot)
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

    @staticmethod
    def _interval_ms(timeframe: str) -> int:
        if timeframe not in {'1m', '5m', '15m', '30m', '1h', '4h'}:
            raise ValueError('Unsupported orderflow timeframe')
        return int(timeframe[:-1]) * (60000 if timeframe.endswith('m') else 3600000)

    def _collect_window(self, symbol, start, end, limit, max_pages, deadline_seconds):
        if not 1 <= limit <= 1000 or max_pages < 1 or not math.isfinite(deadline_seconds) or deadline_seconds <= 0:
            raise ValueError('Invalid orderflow request budget')
        deadline = time.monotonic() + deadline_seconds
        cursor = None
        seen = {}
        collected = []
        for pages in range(1, max_pages + 1):
            if time.monotonic() >= deadline:
                raise TimeoutError('Orderflow pagination deadline exceeded; no snapshot published')
            page = self._request_aggtrades(symbol=symbol, start_time=start if cursor is None else None,
                end_time=end if cursor is None else None, from_id=cursor, limit=limit, deadline=deadline)
            if time.monotonic() >= deadline:
                raise TimeoutError('Orderflow pagination deadline exceeded; no snapshot published')
            if not isinstance(page, list) or len(page) > limit:
                raise ValueError('Invalid aggregate-trade page')
            previous_id = previous_time = None
            new_ids = []
            crossed_end = False
            for row in page:
                if not isinstance(row, dict):raise ValueError('Invalid aggregate-trade row')
                ident, stamp = row.get('a'), row.get('T')
                if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in (ident, stamp)):
                    raise ValueError('Invalid aggregate-trade identity/time')
                qty = float(row['q'])
                if not math.isfinite(qty) or qty < 0 or not isinstance(row.get('m'), bool):
                    raise ValueError('Invalid aggregate-trade quantity/side')
                if previous_id is not None and (ident < previous_id or stamp < previous_time):
                    raise ValueError('Unordered aggregate trades')
                previous_id, previous_time = ident, stamp
                if ident in seen:
                    if seen[ident] != row:raise ValueError('Conflicting duplicate aggregate trade')
                    continue
                if cursor is not None and ident < cursor:
                    raise ValueError('Unexpected aggregate-trade cursor regression')
                if stamp < start:raise ValueError('Aggregate trade precedes requested window')
                seen[ident] = row
                new_ids.append(ident)
                if stamp > end:crossed_end = True
                else:collected.append(row)
            if crossed_end or not page or (len(page) < limit and new_ids):
                return collected, pages
            if not new_ids:raise RuntimeError('Orderflow pagination made no progress')
            cursor = max(new_ids) + 1  # fromId is inclusive; do not advance time past same-ms trades.
        raise RuntimeError('Orderflow page budget exhausted; no snapshot published')

    def _request_aggtrades(
        self,
        *,
        symbol: str,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int,
        from_id: int | None = None,
        deadline: float | None = None,
    ) -> list[dict]:
        """Fetch raw aggTrades payload from Binance."""

        values = {"symbol": symbol, "limit": limit}
        if from_id is None:
            values.update(startTime=start_time, endTime=end_time)
        else:
            values['fromId'] = from_id
        params = urlencode(values)
        url = f"{self.base_url}?{params}"
        payload = BinancePublicHttpClient(opener=urlopen).get_json(url, deadline=deadline)
        if not isinstance(payload, list):raise ValueError('Non-list aggregate-trade API response')
        return payload

    @staticmethod
    def _build_snapshot(
        *,
        symbol: str,
        timeframe: str,
        trades: list[dict],
        window_start_ms: int,
        window_end_ms: int,
        page_count: int,
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

        timestamp_text = datetime.fromtimestamp((window_end_ms + 1) / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
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
            source="binance_aggtrades_closed_window_v2",
            window_start_ms=window_start_ms, window_end_ms=window_end_ms,
            first_trade_ms=min((r['T'] for r in trades), default=None),
            last_trade_ms=max((r['T'] for r in trades), default=None),
            page_count=page_count, completeness="COMPLETE_CLOSED_WINDOW_V1",
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
            row.get("window_start_ms"), row.get("window_end_ms"),
            row.get("first_trade_ms"), row.get("last_trade_ms"),
            row.get("page_count"), row.get("completeness"),
        )

    @classmethod
    def _merge_snapshot_row(cls, rows: list[dict], row: dict) -> list[dict]:
        """Preserve historical rows and never collapse equal volumes across different candles."""
        timestamp = row['timestamp_text']
        matches = [r for r in rows if r.get('timestamp_text') == timestamp]
        if matches:
            if len(matches) == 1 and matches[0] == row:return list(rows)
            raise ValueError('Refusing to overwrite historical orderflow window')
        return sorted([dict(r) for r in rows] + [dict(row)], key=lambda r: str(r.get('timestamp_text') or ''))

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
