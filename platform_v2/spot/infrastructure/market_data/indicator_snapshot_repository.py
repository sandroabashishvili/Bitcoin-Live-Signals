"""File: indicator_snapshot_repository.py
Folder: platform_v2/spot/infrastructure/market_data
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Read indicator snapshots from storage and expose normalized V2 models.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from ...domain.models.indicator_snapshot import IndicatorSnapshot
from ...storage.paths import indicator_snapshots_root as v2_indicator_snapshots_root
from platform_v2.shared.backend.persistence import read_market_series_safely


class IndicatorSnapshotRepository(Protocol):
    """Repository contract for normalized indicator snapshot access."""

    def get_snapshots(
        self,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
    ) -> list[IndicatorSnapshot]:
        """Return normalized snapshots for a symbol and timeframe."""
        ...

    def get_latest_snapshot(self, symbol: str, timeframe: str) -> IndicatorSnapshot | None:
        """Return the latest available normalized snapshot."""
        ...


class JsonIndicatorSnapshotRepository:
    """Read normalized indicator snapshots from V2 JSON storage."""

    _PROMOTED_KEYS = {
        "symbol",
        "timeframe",
        "datetime",
        "price",
        "volume",
        "rsi",
        "macd",
        "macd_signal",
        "macd_trend",
        "ema9",
        "ema50",
        "ema200",
        "ema50_slope",
        "vwap",
        "vwap_signal",
        "adx",
        "atr",
        "atr_spike",
        "tenkan",
        "kijun",
        "ichimoku_signal",
        "plus_di",
        "minus_di",
        "adx_slope",
        "atr_growth_20",
        "atr_spike_threshold",
        "swing_low",
        "swing_high",
        "resistance_level",
        "liquidity_zone",
        "liquidity_tolerance",
        "bounce_confirmed",
        "avg_volume_10",
    }

    def __init__(self, indicator_root: Path | None = None) -> None:
        """Initialize the repository.

        Args:
            indicator_root: Optional indicator result directory.
        """

        self._use_database = indicator_root is None
        if indicator_root is None:
            indicator_root = v2_indicator_snapshots_root()
        self._indicator_root = indicator_root

    def get_snapshots(
        self,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
    ) -> list[IndicatorSnapshot]:
        """Return normalized snapshots from the JSON source."""

        source_path = self._indicator_root / symbol / f"{timeframe}.json"
        raw_rows = (
            read_market_series_safely(
                venue="binance",
                asset_class="crypto",
                market_type="spot",
                dataset="indicators",
                symbol=symbol,
                timeframe=timeframe,
            )
            if self._use_database
            else []
        )
        if not raw_rows:
            if not source_path.exists():
                return []
            raw_rows = json.loads(source_path.read_text(encoding="utf-8"))
        if not isinstance(raw_rows, list):
            return []

        snapshots: list[IndicatorSnapshot] = []
        for row in raw_rows:
            snapshot = self._parse_snapshot_row(symbol=symbol, timeframe=timeframe, row=row)
            if snapshot is not None:
                snapshots.append(snapshot)

        if limit is not None and limit > 0:
            return snapshots[-limit:]

        return snapshots

    def get_latest_snapshot(self, symbol: str, timeframe: str) -> IndicatorSnapshot | None:
        """Return the latest available normalized snapshot."""

        snapshots = self.get_snapshots(symbol=symbol, timeframe=timeframe, limit=1)
        if not snapshots:
            return None
        return snapshots[0]

    @classmethod
    def _parse_snapshot_row(
        cls,
        symbol: str,
        timeframe: str,
        row: object,
    ) -> IndicatorSnapshot | None:
        """Parse one legacy row into a normalized IndicatorSnapshot."""

        if not isinstance(row, dict):
            return None

        try:
            extras = {
                key: value
                for key, value in row.items()
                if key not in cls._PROMOTED_KEYS and value is not None
            }

            return IndicatorSnapshot(
                symbol=str(row.get("symbol") or symbol),
                timeframe=str(row.get("timeframe") or timeframe),
                timestamp_text=str(row.get("datetime") or ""),
                price=float(row.get("price", 0.0) or 0.0),
                volume=cls._optional_float(row.get("volume")),
                rsi=cls._optional_float(row.get("rsi")),
                macd=cls._optional_float(row.get("macd")),
                macd_signal=cls._optional_float(row.get("macd_signal")),
                macd_trend=cls._optional_str(row.get("macd_trend")),
                ema9=cls._optional_float(row.get("ema9")),
                ema50=cls._optional_float(row.get("ema50")),
                ema200=cls._optional_float(row.get("ema200")),
                ema50_slope=cls._optional_float(row.get("ema50_slope")),
                vwap=cls._optional_float(row.get("vwap")),
                vwap_signal=cls._optional_str(row.get("vwap_signal")),
                adx=cls._optional_float(row.get("adx")),
                atr=cls._optional_float(row.get("atr")),
                atr_spike=cls._optional_bool(row.get("atr_spike")),
                tenkan=cls._optional_float(row.get("tenkan")),
                kijun=cls._optional_float(row.get("kijun")),
                ichimoku_signal=cls._optional_str(row.get("ichimoku_signal")),
                plus_di=cls._optional_float(row.get("plus_di")),
                minus_di=cls._optional_float(row.get("minus_di")),
                adx_slope=cls._optional_float(row.get("adx_slope")),
                atr_growth_20=cls._optional_float(row.get("atr_growth_20")),
                atr_spike_threshold=cls._optional_float(row.get("atr_spike_threshold")),
                swing_low=cls._optional_float(row.get("swing_low")),
                swing_high=cls._optional_float(row.get("swing_high")),
                resistance_level=cls._optional_float(row.get("resistance_level")),
                liquidity_zone=cls._optional_float(row.get("liquidity_zone")),
                liquidity_tolerance=cls._optional_float(row.get("liquidity_tolerance")),
                bounce_confirmed=cls._optional_bool(row.get("bounce_confirmed")),
                avg_volume_10=cls._optional_float(row.get("avg_volume_10")),
                extras=extras,
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_float(value: object) -> float | None:
        """Convert a value into an optional float."""

        if value is None:
            return None
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _optional_str(value: object) -> str | None:
        """Convert a value into an optional string."""

        if value is None:
            return None
        return str(value)

    @staticmethod
    def _optional_bool(value: object) -> bool | None:
        """Convert a value into an optional boolean."""

        if value is None:
            return None
        return bool(value)
