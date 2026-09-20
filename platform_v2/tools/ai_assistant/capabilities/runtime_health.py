"""Runtime health capability for Spot and Futures loops."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from platform_v2.tools.ai_assistant.runtime_readers import latest_family_row

from .contracts import CapabilityAnswer


def answer_runtime_health(market: str | None = None) -> CapabilityAnswer:
    markets = [market] if market in ("futures", "spot") else ["futures", "spot"]
    sections = [_format_market_health(selected_market) for selected_market in markets]
    return CapabilityAnswer("runtime_health", "\n\n".join(sections))


def _format_market_health(market: str) -> str:
    family = "futures_cycle_runs" if market == "futures" else "cycle_runs"
    result = latest_family_row(market, family)
    row = result.row
    if row is None:
        return f"{market.title()} health: no cycle rows found. Source: {result.source}"

    timestamp = _event_time(row)
    status = str(row.get("status") or row.get("state") or "--")
    permission = row.get("permission_reason") or row.get("position_event") or row.get("skip_reason") or "--"
    raw_failed_gates = row.get("failed_gates")
    failed_gates = [str(item) for item in raw_failed_gates] if isinstance(raw_failed_gates, list) else []
    lines = [
        f"{market.title()} runtime health",
        f"Latest cycle time: {timestamp}",
        f"Status: {status}",
        f"Cycle state: {_value(row.get('cycle_state') or row.get('state'))}",
        f"Signal: {_value(row.get('signal_side') or row.get('signal'))}",
        f"Permission/event: {_value(permission)}",
        f"Open positions: {_value(row.get('open_positions'))}",
        f"Failed gates: {', '.join(failed_gates) if failed_gates else 'none'}",
        f"Rows in family: {result.count}",
        f"Source: {result.source}",
    ]
    if status.casefold() not in {"ok", "ready"} and status != "--":
        lines.append("Attention: latest cycle status is not OK.")
    return "\n".join(lines)


def _event_time(row: dict[str, Any]) -> str:
    readable = row.get("datetime") or row.get("decision_time") or row.get("time_readable")
    if readable:
        return str(readable)
    timestamp = row.get("timestamp_ms")
    if timestamp is None:
        return "--"
    try:
        timestamp_int = int(timestamp)
    except (TypeError, ValueError):
        return str(timestamp or "--")
    return datetime.fromtimestamp(timestamp_int / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def _value(value: Any) -> str:
    return "--" if value is None else str(value)
