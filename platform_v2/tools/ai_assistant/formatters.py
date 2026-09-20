"""Answer formatting for deterministic assistant facts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .runtime_readers import RuntimeResult


GATE_ORDER = ("mtf", "regime", "momentum", "trend", "orderbook", "structure")


def format_signal(result: RuntimeResult) -> str:
    row = result.row
    if row is None:
        return _missing(result)

    raw_gates = row.get("gates")
    gates = raw_gates if isinstance(raw_gates, dict) else {}
    passed = [gate for gate in GATE_ORDER if gates.get(gate) is True]
    failed = [gate for gate in GATE_ORDER if gates.get(gate) is False]
    direction_scores = row.get("direction_scores")
    mtf_signals = row.get("mtf_signals")
    raw_setup = row.get("theoretical_setup")
    setup = raw_setup if isinstance(raw_setup, dict) else {}

    lines = [
        f"{_market_label(result.market)} latest signal",
        f"Time: {_event_time(row)}",
        f"Symbol: {_value(row.get('symbol'))} {row.get('timeframe', '')}".rstrip(),
        f"Side: {_value(row.get('side'))}",
        f"Score: {_value(row.get('score'))}/{_value(row.get('threshold'))}",
    ]
    if isinstance(direction_scores, dict):
        lines.append(
            "Direction scores: "
            + ", ".join(f"{key}={value}" for key, value in direction_scores.items())
        )
    lines.extend(
        [
            f"Passed gates: {_list_or_none(passed)}",
            f"Failed gates: {_list_or_none(failed)}",
        ]
    )
    if isinstance(mtf_signals, dict):
        lines.append(
            "MTF: "
            + ", ".join(f"{key}={value}" for key, value in mtf_signals.items())
        )
    if "permission_status" in row:
        lines.append(f"Entry status: {_value(row.get('permission_status'))}")
        lines.append(f"Permission reason: {_value(row.get('permission_reason'))}")
    if setup:
        lines.append(
            "Setup: "
            f"entry={_value(setup.get('entry_price'))}, "
            f"TP={_value(setup.get('take_profit'))}, "
            f"SL={_value(setup.get('stop_loss'))}, "
            f"R:R={_value(setup.get('rr_ratio'))}"
        )
    lines.append(f"Source: {result.source}")
    return "\n".join(lines)


def format_position(result: RuntimeResult) -> str:
    row = result.row
    if row is None:
        return _missing(result)

    lines = [
        f"{_market_label(result.market)} latest position",
        f"Position ID: {_value(row.get('position_id'))}",
        f"Status: {_value(row.get('status'))}",
        f"Side: {_value(row.get('side'))}",
        f"Opened: {_value(row.get('opened_at'))}",
        f"Entry: {_value(row.get('entry_price'))}",
    ]
    if row.get("status") == "OPEN":
        lines.extend(
            [
                f"Mark: {_value(row.get('mark_price'))}",
                f"Unrealized PnL: {_value(row.get('unrealized_pnl'))}",
                f"ROE %: {_value(row.get('roe_pct'))}",
                f"TP: {_value(row.get('tp_price'))}",
                f"SL: {_value(row.get('sl_price'))}",
            ]
        )
    else:
        lines.extend(
            [
                f"Closed: {_value(row.get('closed_at'))}",
                f"Outcome/reason: {_value(row.get('outcome') or row.get('exit_reason'))}",
                f"Net PnL: {_value(row.get('net_pnl'))}",
            ]
        )
    lines.append(f"Source: {result.source}")
    return "\n".join(lines)


def format_position_pnl(result: RuntimeResult) -> str:
    row = result.row
    if row is None:
        return _missing(result)

    pnl = row.get("unrealized_pnl") if row.get("status") == "OPEN" else row.get("net_pnl")
    pnl_float = _float_or_zero(pnl)
    state = "მოგებაშია" if pnl_float > 0 else "მინუსშია" if pnl_float < 0 else "ნულთანაა"
    pnl_label = "Unrealized PnL" if row.get("status") == "OPEN" else "Net PnL"

    lines = [
        f"{_market_label(result.market)} latest position is {state}.",
        f"Position ID: {_value(row.get('position_id'))}",
        f"Status: {_value(row.get('status'))}",
        f"Side: {_value(row.get('side'))}",
        f"{pnl_label}: {_value(pnl)}",
        f"ROE %: {_value(row.get('roe_pct'))}",
        f"Entry: {_value(row.get('entry_price'))}",
    ]
    if row.get("status") == "OPEN":
        lines.append(f"Mark: {_value(row.get('mark_price'))}")
    lines.append(f"Source: {result.source}")
    return "\n".join(lines)


def format_spot_silence(result: RuntimeResult) -> str:
    row = result.row
    if row is None:
        return _missing(result)

    raw_gates = row.get("gates")
    gates = raw_gates if isinstance(raw_gates, dict) else {}
    failed = [gate for gate in GATE_ORDER if gates.get(gate) is False]
    passed = [gate for gate in GATE_ORDER if gates.get(gate) is True]
    raw_reasons = row.get("reasons")
    reasons = raw_reasons if isinstance(raw_reasons, list) else []
    blocker_reasons = [
        str(reason)
        for reason in reasons
        if any(token in str(reason).casefold() for token in ("cannot", "requires", "needs", "failed"))
    ]

    lines = [
        "Spot is quiet because latest BUY did not become actionable.",
        f"Time: {_event_time(row)}",
        f"Side: {_value(row.get('side'))}",
        f"Score: {_value(row.get('score'))}/{_value(row.get('threshold'))}",
        f"Passed gates: {_list_or_none(passed)}",
        f"Failed gates: {_list_or_none(failed)}",
    ]
    raw_mtf_signals = row.get("mtf_signals")
    if isinstance(raw_mtf_signals, dict):
        lines.append(
            "MTF: "
            + ", ".join(f"{key}={value}" for key, value in raw_mtf_signals.items())
        )
    if blocker_reasons:
        lines.append("Main reasons:")
        lines.extend(f"- {reason}" for reason in blocker_reasons[:4])
    lines.append(f"Source: {result.source}")
    return "\n".join(lines)


def format_denied_entry(result: RuntimeResult) -> str:
    row = result.row
    if row is None:
        return _missing(result)

    checks_source = row.get("permission_checks") or row.get("checks")
    checks = checks_source if isinstance(checks_source, dict) else {}
    failed_checks = [key for key, passed in checks.items() if passed is False]
    lines = [
        f"{_market_label(result.market)} latest denied entry",
        f"Time: {_event_time(row)}",
        f"Signal side: {_value(row.get('signal_side') or row.get('side'))}",
        f"Reason: {_value(row.get('reason') or row.get('permission_reason'))}",
        f"Main blocker: {_value(row.get('main_blocker') or row.get('permission_reason') or row.get('reason'))}",
        f"Failed checks: {_list_or_none(failed_checks)}",
        f"Source: {result.source}",
    ]
    return "\n".join(lines)


def format_diagnostics(result: RuntimeResult) -> str:
    row = result.row
    if row is None:
        return "Diagnostics report not found."

    raw_summary = row.get("summary")
    raw_counts = row.get("counts")
    raw_severity_counts = row.get("severity_counts")
    raw_issue_counts = row.get("issue_counts")
    summary = raw_summary if isinstance(raw_summary, dict) else {}
    counts = raw_counts if isinstance(raw_counts, dict) else {}
    severity_counts = raw_severity_counts if isinstance(raw_severity_counts, dict) else {}
    issue_counts = raw_issue_counts if isinstance(raw_issue_counts, dict) else {}
    findings_total = row.get("findings_total")
    status = row.get("status") or summary.get("status") or row.get("result")
    if status is None and findings_total is not None:
        status = "clean" if findings_total == 0 else "findings"
    lines = [
        "Latest diagnostics report",
        f"Status: {_value(status)}",
        f"Generated: {_value(row.get('generated_at'))}",
        f"Profile: {_value(row.get('profile'))}",
        f"Findings: {_value(findings_total)}",
        f"Severity counts: {_value(severity_counts or counts or summary)}",
        f"Issue counts: {_value(issue_counts)}",
        f"Source: {result.source}",
    ]
    return "\n".join(lines)


def format_overview(results: list[RuntimeResult]) -> str:
    sections: list[str] = []
    for result in results:
        if result.family.endswith("signals") or result.family == "signals":
            sections.append(format_signal(result))
        elif result.family.endswith("positions") or result.family == "positions":
            sections.append(format_position(result))
    return "\n\n".join(sections)


def _missing(result: RuntimeResult) -> str:
    return f"{_market_label(result.market)} {result.family}: no rows found. Source: {result.source}"


def _event_time(row: dict[str, Any]) -> str:
    readable = row.get("decision_time") or row.get("candle_close_time") or row.get("time_readable")
    if readable:
        return _value(readable)
    timestamp = row.get("timestamp_ms")
    if timestamp is None:
        return "--"
    try:
        timestamp_int = int(timestamp)
    except (TypeError, ValueError):
        return _value(timestamp)
    return datetime.fromtimestamp(timestamp_int / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def _value(value: Any) -> str:
    if value is None:
        return "--"
    return str(value)


def _float_or_zero(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _list_or_none(values: list[str]) -> str:
    return ", ".join(values) if values else "none"


def _market_label(market: str) -> str:
    if market == "futures":
        return "Futures"
    if market == "spot":
        return "Spot"
    return "System"
