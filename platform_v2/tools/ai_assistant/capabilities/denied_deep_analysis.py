"""Deep denied-entry analysis from deterministic ledgers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from platform_v2.tools.ai_assistant.intents import AssistantIntent
from platform_v2.tools.ai_assistant.runtime_readers import family_rows, latest_denied_entry, latest_signal

from .contracts import CapabilityAnswer


def answer_denied_deep_analysis(intent: AssistantIntent | None = None) -> CapabilityAnswer:
    market = intent.market if intent and intent.market in {"futures", "spot"} else "futures"
    if market == "spot":
        return _answer_spot_signal_block_analysis()

    denied = latest_denied_entry("futures")
    row = denied.row
    if not row:
        return CapabilityAnswer("denied_deep_analysis", f"No Futures denied entry found. Source: {denied.source}")

    positions = _rows(family_rows("futures", "futures_positions"))
    side = str(row.get("signal_side") or row.get("side") or "").upper()
    open_same_side = [
        item for item in positions
        if str(item.get("status") or "").upper() == "OPEN" and str(item.get("side") or "").upper() == side
    ]
    latest_open = open_same_side[-1] if open_same_side else None
    failed_checks = _failed_checks(row)

    lines = [
        "Latest denied Futures signal analysis",
        "Signal:",
        f"- time={_event_time(row)}",
        f"- side={side or '--'}",
        f"- score={_value(row.get('signal_score'))}",
        f"- reason={_value(row.get('reason') or row.get('permission_reason'))}",
        "Failed checks:",
    ]
    lines.extend(f"- {check}" for check in failed_checks) if failed_checks else lines.append("- none listed")
    lines.extend(_position_lines(row, latest_open))
    lines.extend(_entry_quality_lines(row))
    lines.extend(_market_plan_lines(row))
    lines.extend(_entry_location_lines(row))
    lines.append("Verdict:")
    lines.append(f"- Denied because permission reason is {_value(row.get('reason') or row.get('permission_reason'))}.")
    if "proximity" in failed_checks and latest_open:
        lines.append("- Proximity failed against an existing same-direction open position.")
    if "short_market_plan_zone" in failed_checks:
        lines.append("- SHORT was outside the active market-plan working zone.")
    if "entry_quality" in failed_checks:
        lines.append("- Entry quality check rejected the timing/location context.")
    lines.append(f"Source: {denied.source}")
    return CapabilityAnswer("denied_deep_analysis", "\n".join(lines), (denied.source,) if denied.source else ())


def _answer_spot_signal_block_analysis() -> CapabilityAnswer:
    result = latest_signal("spot")
    row = result.row
    if not row:
        return CapabilityAnswer("denied_deep_analysis", f"No Spot signal rows found. Source: {result.source}")
    failed_checks = _failed_checks(row)
    raw_reasons = row.get("reasons")
    reasons = raw_reasons if isinstance(raw_reasons, list) else []
    lines = [
        "Latest Spot signal block analysis",
        "Signal:",
        f"- time={_event_time(row)}",
        f"- side={_value(row.get('side'))}",
        f"- score={_value(row.get('score'))}/{_value(row.get('threshold'))}",
        f"- snapshot_price={_value(row.get('snapshot_price'))}",
        "Failed gates:",
    ]
    lines.extend(f"- {check}" for check in failed_checks) if failed_checks else lines.append("- none listed")
    raw_mtf = row.get("mtf_signals")
    mtf = raw_mtf if isinstance(raw_mtf, dict) else {}
    if mtf:
        lines.append("MTF:")
        lines.extend(f"- {key}={value}" for key, value in sorted(mtf.items()))
    if reasons:
        lines.append("Reasons:")
        lines.extend(f"- {reason}" for reason in reasons[-6:])
    lines.append("Verdict:")
    if str(row.get("side") or "").upper() == "NO_SIGNAL":
        lines.append("- Spot did not open because latest BUY did not clear required gate/action conditions.")
    else:
        lines.append("- Latest Spot row is actionable signal data, not a denied-entry row.")
    lines.append("- Spot does not currently expose a separate denied_entries ledger in runtime data.")
    lines.append(f"Source: {result.source}")
    return CapabilityAnswer("denied_deep_analysis", "\n".join(lines), (result.source,) if result.source else ())


def _position_lines(denied_row: dict[str, Any], position: dict[str, Any] | None) -> list[str]:
    lines = ["Existing same-direction position:"]
    if not position:
        lines.append("- none found")
        return lines
    entry_price = _float(denied_row.get("entry_price"))
    last_entry = _float(position.get("entry_price"))
    distance = abs(entry_price - last_entry) if entry_price is not None and last_entry is not None else None
    distance_pct = (distance / last_entry * 100.0) if distance is not None and last_entry else None
    lines.append(f"- id={_value(position.get('position_id'))}")
    lines.append(f"- side={_value(position.get('side'))}")
    lines.append(f"- entry={_value(position.get('entry_price'))}")
    lines.append(f"- mark={_value(position.get('mark_price'))}")
    lines.append(f"- unrealized_pnl={_value(position.get('unrealized_pnl'))}")
    if distance is not None:
        lines.append(f"- distance_from_denied_entry={round(distance, 4)}")
    if distance_pct is not None:
        lines.append(f"- distance_pct={round(distance_pct, 4)}")
    lines.append("- required proximity threshold is configured in FuturesPermissionDecisionService/settings; denied row stores pass/fail, not the numeric threshold.")
    return lines


def _entry_quality_lines(row: dict[str, Any]) -> list[str]:
    raw_quality = row.get("entry_quality")
    quality = raw_quality if isinstance(raw_quality, dict) else {}
    if not quality:
        return []
    raw_override = quality.get("override")
    override = raw_override if isinstance(raw_override, dict) else {}
    return [
        "Entry quality:",
        f"- allowed={_value(quality.get('allowed'))}",
        f"- timing_type={_value(quality.get('timing_type'))}",
        f"- direction_signal_age={_value(quality.get('direction_signal_age'))}",
        f"- reason={_value(quality.get('reason'))}",
        f"- override={_value(override.get('reason'))}",
    ]


def _market_plan_lines(row: dict[str, Any]) -> list[str]:
    raw_plan = row.get("market_plan_permission")
    plan = raw_plan if isinstance(raw_plan, dict) else {}
    if not plan:
        return []
    raw_nearest = plan.get("nearest_zone")
    nearest = raw_nearest if isinstance(raw_nearest, dict) else {}
    lines = [
        "Market-plan permission:",
        f"- allowed={_value(plan.get('allowed'))}",
        f"- alignment={_value(plan.get('alignment'))}",
        f"- bias={_value(plan.get('bias'))}",
    ]
    if nearest:
        lines.extend(
            [
                f"- nearest_zone={_value(nearest.get('name'))}",
                f"- zone_from={_value(nearest.get('from'))}",
                f"- zone_to={_value(nearest.get('to'))}",
                f"- entry_in_zone={_value(nearest.get('entry_in_zone'))}",
            ]
        )
    return lines


def _entry_location_lines(row: dict[str, Any]) -> list[str]:
    raw_location = row.get("entry_location_permission")
    location = raw_location if isinstance(raw_location, dict) else {}
    if not location:
        return []
    return [
        "Entry-location permission:",
        f"- allowed={_value(location.get('allowed'))}",
        f"- location_type={_value(location.get('location_type'))}",
    ]


def _failed_checks(row: dict[str, Any]) -> list[str]:
    raw_checks = row.get("checks")
    raw_gates = row.get("gates")
    checks = raw_checks if isinstance(raw_checks, dict) else raw_gates if isinstance(raw_gates, dict) else {}
    return [key for key, value in checks.items() if value is False]


def _rows(result: Any) -> list[dict[str, Any]]:
    row_payload = result.row
    if isinstance(row_payload, dict):
        rows = row_payload.get("rows")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


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


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _value(value: Any) -> str:
    return "--" if value is None else str(value)
