"""Backend-owned chart values; browsers only render this versioned contract.

Gate counts are overlapping participations, not unique signals/trades. Equity
contains recorded observations only. Orderflow uses supplied delta/cumulative
values, never reconstitutes them from rounded buy/sell display strings.
"""
from __future__ import annotations

from datetime import UTC, datetime
import math
from typing import Any


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _timestamp(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return int(dt.timestamp() * 1000)
    except (TypeError, ValueError, OverflowError):
        return None


def build_gate_chart_payload(logic: dict[str, Any], *, directional: bool = False) -> dict[str, Any]:
    """Prepare denominators, outcomes and weighted win rates on the server."""
    closed = logic.get("chart_mode") == "outcomes" or "closed_trade_summary" in logic
    groups = (("LONG", "long"), ("SHORT", "short")) if directional else (("Primary", "primary"), ("Confirmation", "confirmation"))
    charts = []
    for title, key in groups:
        if directional:
            sources = [logic.get(f"{key}_{group}_totals") or {} for group in ("primary", "confirmation")]
        else:
            sources = [logic.get(f"{key}_totals") or {}]
        fields = ("tp", "sl", "profit_lock", "force_close") if closed else ("tp", "sl", "open")
        counts = {}
        for field in fields:
            counts[field] = sum(int(_number(s.get(field, s.get("lock", 0) if field == "profit_lock" else 0)) or 0) for s in sources)
        total = sum(counts.values())
        resolved = counts["tp"] + counts["sl"]
        if closed:
            wins_available = all(_number(s.get("wins")) is not None for s in sources)
            wins = sum(int(s["wins"]) for s in sources) if wins_available else None
            denominator = total
        else:
            wins = counts["tp"]
            denominator = resolved
        rate = wins / denominator * 100 if wins is not None and denominator else None
        labels = {"tp": "TP", "sl": "SL", "profit_lock": "Profit Lock", "force_close": "Force Close", "open": "Open"}
        outcomes = [
            {"key": field, "name": labels[field], "value": count,
             "percent": round(count / total * 100, 4) if total else 0,
             "percent_text": f"{count / total * 100:.1f}%" if total else "—"}
            for field, count in counts.items()
        ]
        charts.append({"title": title, "total": total, "outcomes": outcomes,
                       "win_rate": round(rate, 4) if rate is not None else None,
                       "win_rate_text": f"{rate:.1f}%" if rate is not None else "—",
                       "denominator": denominator, "wins": wins,
                       "has_data": total > 0,
                       "count_definition": "Overlapping gate participations; not unique trades/signals",
                       "win_rate_definition": "Net-positive closed participations / all closed participations" if closed else "TP participations / resolved (TP + SL) participations"})
    return {"version": 1, "charts": charts}


def build_equity_chart_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    prepared = []
    for row in rows:
        start, equity = _number(row.get("starting_capital")), _number(row.get("equity"))
        ts = _timestamp(row.get("datetime") or row.get("date") or row.get("timestamp"))
        if start is None or start <= 0 or equity is None or ts is None:
            continue
        change = equity - start
        pct = round(change / start * 100, 4)
        prepared.append({**row, "timestamp_ms": ts, "delta_abs": change, "delta_pct": pct,
                         "chart_point": [ts, pct, equity, start, change]})
    prepared.sort(key=lambda r: r["timestamp_ms"])
    extent = max((abs(r["delta_pct"]) for r in prepared), default=0)
    axis = max(round(extent * 1.25, 4), .1)
    maximum = max(prepared, key=lambda r: r["delta_pct"], default=None)
    minimum = min(prepared, key=lambda r: r["delta_pct"], default=None)
    return {"version": 1, "rows": prepared, "axis_min": -axis, "axis_max": axis,
            "max_point": maximum["chart_point"] if maximum else None,
            "min_point": minimum["chart_point"] if minimum else None}


def build_orderflow_chart_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared = []
    for row in rows:
        ts = _timestamp(row.get("timestamp_text"))
        delta, cumulative = _number(row.get("delta")), _number(row.get("cumulative_delta"))
        if ts is None or delta is None or cumulative is None:
            continue
        prepared.append({**row, "timestamp_ms": ts, "delta_value": delta,
                         "cumulative_value": cumulative,
                         "positive_cumulative": cumulative if cumulative > 0 else None,
                         "negative_cumulative": cumulative if cumulative < 0 else None})
    return sorted(prepared, key=lambda r: r["timestamp_ms"], reverse=True)
