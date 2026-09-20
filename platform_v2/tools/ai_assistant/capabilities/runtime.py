"""Runtime trading capability for signals, positions, and denied entries."""

from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Sequence
from typing import Any

from platform_v2.tools.ai_assistant.formatters import (
    format_denied_entry,
    format_overview,
    format_position_pnl,
    format_spot_silence,
)
from platform_v2.tools.ai_assistant.intents import AssistantIntent
from platform_v2.tools.ai_assistant.runtime_readers import (
    latest_denied_entry,
    latest_position,
    latest_signal,
    latest_metrics,
    family_rows,
    signal_history,
)

from .contracts import CapabilityAnswer


def answer_runtime(intent: AssistantIntent) -> CapabilityAnswer:
    markets = _markets_for_intent(intent)

    if intent.topic == "signal":
        results = [latest_signal(market) for market in markets]
        return CapabilityAnswer("runtime", format_overview(results), _sources(results))
    if intent.topic == "position":
        results = [latest_position(market) for market in markets]
        return CapabilityAnswer("runtime", format_overview(results), _sources(results))
    if intent.topic == "position_pnl":
        results = [latest_position(market) for market in markets]
        text = "\n\n".join(format_position_pnl(result) for result in results)
        return CapabilityAnswer("runtime", text, _sources(results))
    if intent.topic == "capital_snapshot":
        results = [latest_metrics(market) for market in markets]
        return CapabilityAnswer("runtime", _format_capital_snapshot(results), _sources(results))
    if intent.topic == "spot_silence":
        result = latest_signal("spot")
        return CapabilityAnswer("runtime", format_spot_silence(result), _sources([result]))
    if intent.topic == "denied_entry":
        results = [latest_denied_entry(market) for market in markets]
        text = "\n\n".join(format_denied_entry(result) for result in results)
        return CapabilityAnswer("runtime", text, _sources(results))
    if intent.topic == "denied_vs_open_position":
        return answer_denied_vs_open_position()

    results = []
    for market in markets:
        results.append(latest_signal(market))
        results.append(latest_position(market))
    return CapabilityAnswer("runtime", format_overview(results), _sources(results))


def answer_denied_vs_open_position() -> CapabilityAnswer:
    denied = latest_denied_entry("futures")
    positions = family_rows("futures", "futures_positions")
    denied_row = denied.row
    position_rows = []
    positions_payload = positions.row
    if isinstance(positions_payload, dict):
        raw_position_rows = positions_payload.get("rows")
        if isinstance(raw_position_rows, list):
            position_rows = [row for row in raw_position_rows if isinstance(row, dict)]
    if not denied_row:
        return CapabilityAnswer("runtime", f"No latest Futures denied entry found. Source: {denied.source}")
    side = str(denied_row.get("signal_side") or denied_row.get("side") or "").upper()
    open_same_side = [
        row for row in position_rows
        if str(row.get("status") or "").upper() == "OPEN" and str(row.get("side") or "").upper() == side
    ]
    latest_open = open_same_side[-1] if open_same_side else None
    lines = [
        "Latest denied Futures signal vs open same-direction position",
        f"1. Latest denied signal: side={side or '--'}, time={_event_time(denied_row)}, reason={denied_row.get('reason') or denied_row.get('permission_reason')}.",
    ]
    if latest_open:
        lines.append(
            f"2. Existing open same-direction position remains open: id={latest_open.get('position_id')}, side={latest_open.get('side')}, opened={latest_open.get('opened_at')}, entry={latest_open.get('entry_price')}."
        )
    else:
        lines.append("2. No open same-direction position was found in the latest positions family.")
    raw_checks = denied_row.get("checks")
    checks = raw_checks if isinstance(raw_checks, dict) else {}
    failed = [key for key, value in checks.items() if value is False]
    lines.extend(
        [
            f"3. Failed permission checks: {', '.join(failed) if failed else 'none listed'}.",
            "4. A denied signal blocks a new entry only. It does not close or modify an already-open position.",
            f"Source: {denied.source}",
        ]
    )
    if positions.source:
        lines.append(f"Source: {positions.source}")
    return CapabilityAnswer("runtime", "\n".join(lines), tuple(source for source in (denied.source, positions.source) if source))


def answer_latest_signal_compare(market: str | None = None) -> CapabilityAnswer:
    markets = [market] if market in ("futures", "spot") else ["futures", "spot"]
    sections: list[str] = []
    sources: list[str] = []
    for selected_market in markets:
        history = signal_history(selected_market)
        row = history.row
        if row is None:
            sections.append(f"{selected_market.title()} signals: no rows found. Source: {history.source}")
        else:
            first = row.get("first")
            latest = row.get("latest")
            if isinstance(first, dict) and isinstance(latest, dict):
                sections.append(_format_signal_compare(selected_market, first, latest, history.count))
            else:
                sections.append(f"{selected_market.title()} signals: malformed history row. Source: {history.source}")
        if history.source:
            sources.append(history.source)
    return CapabilityAnswer("runtime", "\n\n".join(sections), tuple(dict.fromkeys(sources)))


def _markets_for_intent(intent: AssistantIntent) -> list[str]:
    if intent.market in ("futures", "spot"):
        return [intent.market]
    return ["futures", "spot"]


def _sources(results: Sequence[object]) -> tuple[str, ...]:
    sources: list[str] = []
    for result in results:
        source = getattr(result, "source", None)
        if source:
            sources.append(source)
    return tuple(dict.fromkeys(sources))


def _format_signal_compare(market: str, first: dict[str, Any], latest: dict[str, Any], count: int) -> str:
    lines = [
        f"{market.title()} first vs latest signal",
        f"Rows compared: {count}",
        f"First: time={_event_time(first)}, side={first.get('side')}, score={first.get('score')}/{first.get('threshold')}",
        f"Latest: time={_event_time(latest)}, side={latest.get('side')}, score={latest.get('score')}/{latest.get('threshold')}",
        f"First failed gates: {_failed_gates(first)}",
        f"Latest failed gates: {_failed_gates(latest)}",
    ]
    if latest.get("permission_status") or latest.get("permission_reason"):
        lines.append(
            f"Latest entry status: {latest.get('permission_status', '--')} / {latest.get('permission_reason', '--')}"
        )
    return "\n".join(lines)


def _format_capital_snapshot(results: Sequence[object]) -> str:
    sections: list[str] = []
    for result in results:
        market = getattr(result, "market", "system")
        row = getattr(result, "row", None)
        source = getattr(result, "source", None)
        if not isinstance(row, dict):
            sections.append(f"{str(market).title()} metrics: no rows found. Source: {source}")
            continue
        sections.append(
            "\n".join(
                [
                    f"{str(market).title()} capital snapshot",
                    f"Starting capital: {_value(row.get('starting_capital'))}",
                    f"Available balance: {_value(row.get('available_balance'))}",
                    f"Equity: {_value(row.get('equity'))}",
                    f"Total net PnL: {_value(row.get('total_net_pnl'))}",
                    f"Net return %: {_value(row.get('net_return_pct'))}",
                    f"Annualized return: {_value(row.get('annualized_return'))}",
                    f"Reserved capital: {_value(row.get('reserved_capital'))}",
                    f"Unrealized PnL: {_value(row.get('unrealized_pnl'))}",
                    f"Open positions: {_value(row.get('open_positions'))}",
                    f"Source: {source}",
                ]
            )
        )
    return "\n\n".join(sections)


def _failed_gates(row: dict[str, Any]) -> str:
    raw_gates = row.get("gates")
    gates = raw_gates if isinstance(raw_gates, dict) else {}
    failed = [key for key, passed in gates.items() if passed is False]
    return ", ".join(failed) if failed else "none"


def _value(value: Any) -> str:
    if value is None:
        return "--"
    return str(value)


def _event_time(row: dict[str, Any]) -> str:
    readable = row.get("decision_time") or row.get("candle_close_time") or row.get("time_readable")
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
