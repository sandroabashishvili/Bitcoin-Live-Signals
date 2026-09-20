"""Build full-history indicator rows from frozen candle data."""

from __future__ import annotations

import json
from pathlib import Path

from platform_v2.spot.infrastructure.market_data.candle_repository import JsonCandleRepository
from platform_v2.spot.services.analytics.indicator_snapshot_builder import IndicatorSnapshotBuilder
from platform_v2.shared.backend.market.indicator_series import ema_series


def build_spot_indicator_history(
    *,
    spot_data_root: Path,
    output_root: Path,
    symbol: str,
    timeframes: list[str],
    include_candidate_ema9: bool = False,
) -> list[Path]:
    repository = JsonCandleRepository(candles_root=spot_data_root / "candles")
    builder = IndicatorSnapshotBuilder()
    written: list[Path] = []
    for timeframe in timeframes:
        candles = repository.get_closed_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=None,
        )
        if len(candles) < 35:
            continue
        rows = builder.build_rows(symbol=symbol, timeframe=timeframe, candles=candles)
        if include_candidate_ema9:
            ema9_values = ema_series([candle.close_price for candle in candles], 9)
            for row, ema9 in zip(rows, ema9_values[34:], strict=True):
                row["ema9"] = round(ema9, 8) if ema9 is not None else None
        path = output_root / symbol / f"{timeframe}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written
