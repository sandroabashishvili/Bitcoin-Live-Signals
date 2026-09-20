"""Strategy audit capability for gates, blockers, and signal pressure."""

from __future__ import annotations

from typing import Any

from platform_v2.tools.ai_assistant.runtime_readers import latest_daily_summary, latest_family_row

from .contracts import CapabilityAnswer


def answer_strategy_audit(market: str | None = None) -> CapabilityAnswer:
    markets = [market] if market in ("futures", "spot") else ["futures", "spot"]
    return CapabilityAnswer("strategy_audit", "\n\n".join(_format_strategy(selected) for selected in markets))


def _format_strategy(market: str) -> str:
    if market == "futures":
        report = latest_family_row("futures", "futures_strategy_gate_effectiveness_reports")
        summary = latest_daily_summary("futures")
    else:
        report = latest_family_row("spot", "daily_summaries")
        summary = report

    lines = [f"{market.title()} strategy audit"]
    lines.extend(_format_summary_blockers(summary.row))
    if market == "futures":
        lines.extend(_format_futures_gate_report(report.row))
    else:
        lines.append("Spot gate effectiveness report is not available in the current assistant reader yet.")
    lines.append(f"Source: {report.source or summary.source}")
    return "\n".join(lines)


def _format_summary_blockers(row: dict[str, Any] | None) -> list[str]:
    if not row:
        return ["Daily summary: no row found."]
    raw_permission_reasons = row.get("permission_reasons")
    raw_denied_reasons = row.get("denied_reasons")
    raw_blocker_counts = row.get("blocker_counts")
    permission_reasons = raw_permission_reasons if isinstance(raw_permission_reasons, dict) else {}
    denied_reasons = raw_denied_reasons if isinstance(raw_denied_reasons, dict) else {}
    blocker_counts = raw_blocker_counts if isinstance(raw_blocker_counts, dict) else {}
    lines = [
        f"Cycles: {_value(row.get('total_cycles'))}, OK: {_value(row.get('ok_cycles'))}, skipped: {_value(row.get('skipped_cycles'))}",
        f"Opened orders: {_value(row.get('opened_orders'))}, denied entries: {_value(row.get('denied_entries'))}",
    ]
    if permission_reasons:
        lines.append("Top permission reasons:")
        lines.extend(f"- {key}: {value}" for key, value in _top_items(permission_reasons, 5))
    if denied_reasons:
        lines.append("Top denied reasons:")
        lines.extend(f"- {key}: {value}" for key, value in _top_items(denied_reasons, 5))
    if blocker_counts:
        lines.append("Top blocker/gate counts:")
        lines.extend(f"- {key}: {value}" for key, value in _top_items(blocker_counts, 6))
    return lines


def _format_futures_gate_report(row: dict[str, Any] | None) -> list[str]:
    if not row:
        return ["Gate effectiveness report: no row found."]
    raw_activity = row.get("signal_activity_summary")
    raw_evaluation = row.get("strategy_logic_evaluation")
    activity = raw_activity if isinstance(raw_activity, dict) else {}
    evaluation = raw_evaluation if isinstance(raw_evaluation, dict) else {}
    lines = [
        f"Signal activity: total={_value(activity.get('total_signals'))}, short={_value(activity.get('short_signals'))}, no_signal={_value(activity.get('no_signal'))}, theoretical win_rate={_value(activity.get('signal_win_rate'))}",
    ]
    short_rows = []
    for key in ("short_primary_rows", "short_confirmation_rows"):
        raw_rows = evaluation.get(key)
        rows = raw_rows if isinstance(raw_rows, list) else []
        short_rows.extend(row for row in rows if isinstance(row, dict))
    if short_rows:
        lines.append("Best SHORT gate rows by win rate:")
        sorted_rows = sorted(short_rows, key=lambda item: float(item.get("win_rate") or 0), reverse=True)
        for item in sorted_rows[:4]:
            lines.append(
                f"- {item.get('gate')}: participated={item.get('participated')}, win_rate={item.get('win_rate')}, tp={item.get('tp')}, sl={item.get('sl')}, open={item.get('open')}"
            )
    return lines


def _top_items(values: dict[str, Any], limit: int) -> list[tuple[str, Any]]:
    return sorted(values.items(), key=lambda item: float(item[1] or 0), reverse=True)[:limit]


def _value(value: Any) -> str:
    return "--" if value is None else str(value)
