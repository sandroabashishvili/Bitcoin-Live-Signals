"""Period-level market context summaries for interpreting replay stability."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from statistics import mean
from typing import Any, Iterable


def build_market_context_7d(
    *,
    snapshots: Any,
    timestamps: Iterable[int],
    origin_timestamp_ms: int,
) -> list[dict[str, Any]]:
    period_ms = 7 * 24 * 60 * 60 * 1000
    grouped: dict[int, list[Any]] = {}
    for timestamp_ms in sorted({int(value) for value in timestamps}):
        snapshot = snapshots.at(timestamp_ms)
        if snapshot is None:
            continue
        bucket = max(0, (timestamp_ms - origin_timestamp_ms) // period_ms)
        grouped.setdefault(bucket, []).append(snapshot)

    rows: list[dict[str, Any]] = []
    for bucket, values in sorted(grouped.items()):
        start = datetime.fromtimestamp(
            (origin_timestamp_ms + bucket * period_ms) / 1000,
            tz=UTC,
        )
        prices = [_number(getattr(value, "price", None)) for value in values]
        prices = [value for value in prices if value is not None and value > 0]
        return_pct = (
            round((prices[-1] / prices[0] - 1.0) * 100.0, 2)
            if len(prices) >= 2
            else None
        )
        rows.append(
            {
                "bucket": bucket,
                "start_date": start.date().isoformat(),
                "end_date_exclusive": (start + timedelta(days=7)).date().isoformat(),
                "snapshot_count": len(values),
                "price_return_pct": return_pct,
                "avg_rsi": _average(values, "rsi"),
                "avg_adx": _average(values, "adx"),
                "avg_atr_growth_20": _average(values, "atr_growth_20"),
                "avg_atr": _average(values, "atr"),
            }
        )
    return rows


def _average(values: list[Any], attribute: str) -> float | None:
    numbers = [_number(getattr(value, attribute, None)) for value in values]
    present = [value for value in numbers if value is not None]
    return round(mean(present), 4) if present else None


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
