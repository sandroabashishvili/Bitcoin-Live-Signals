"""Hedge-owned chronological equity risk metrics."""

from math import isfinite
from typing import Any


DEFINITION = "peak_to_trough_v1"


def equity_risk_metrics(points: list[dict[str, Any]], starting_capital: float) -> dict[str, Any]:
    """Measure peak drawdown and loss below starting capital independently.

    Include starting capital as the initial peak. Only finite, market-timed
    equity observations count; zero/negative equity is a real observation.
    Missing history returns unknown metrics rather than relabelling legacy data.
    """
    rows = []
    for point in points:
        try:
            timestamp = int(point.get("timestamp_ms") or point.get("opened_at_ms") or 0)
            equity = float(point["equity_usdt"])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if timestamp > 0 and isfinite(equity):
            rows.append((timestamp, equity))
    result = {
        "drawdown_definition": DEFINITION,
        "max_drawdown_pct": None,
        "max_loss_from_start_pct": None,
    }
    if not rows or not isfinite(starting_capital) or starting_capital <= 0:
        return result
    peak = starting_capital
    max_drawdown = max_loss = 0.0
    for _, equity in sorted(rows, key=lambda row: row[0]):
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak * 100.0)
        max_loss = max(max_loss, (starting_capital - equity) / starting_capital * 100.0)
    result.update(max_drawdown_pct=round(max_drawdown, 4), max_loss_from_start_pct=round(max_loss, 4))
    return result
