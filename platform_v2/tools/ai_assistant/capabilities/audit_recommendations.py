"""Audit recommendation summaries from existing runtime/research reports."""

from __future__ import annotations

from typing import Any

from platform_v2.tools.ai_assistant.intents import AssistantIntent
from platform_v2.tools.ai_assistant.runtime_readers import family_rows

from .artifact_index import latest_files_by_area
from .contracts import CapabilityAnswer


def answer_audit_recommendations(intent: AssistantIntent | None = None) -> CapabilityAnswer:
    market = intent.market if intent and intent.market in {"futures", "spot"} else "futures"
    if market == "spot":
        return _answer_spot_audit_recommendations()
    report = _latest_row("futures", "futures_trade_audit_reports")
    tuning = _latest_row("futures", "futures_tuning_audit_reports")
    gate = _latest_row("futures", "futures_trade_gate_effectiveness_reports")
    research = latest_files_by_area(limit=5).get("research_replay", [])
    lines = ["Audit recommendations snapshot"]
    if report:
        lines.append("Futures trade audit report:")
        lines.append(f"- sample_size={_value(report.get('sample_size'))}")
        lines.append(f"- sample_status={_value(report.get('sample_status'))}")
        lines.append(f"- recommendation={_value(report.get('recommendation'))}")
        watchlist = report.get("watchlist") if isinstance(report.get("watchlist"), list) else []
        if watchlist:
            lines.append("Watchlist:")
            lines.extend(f"- {item}" for item in watchlist[:5])
    if tuning:
        lines.append("Futures tuning audit:")
        lines.append(f"- recommendation={_value(tuning.get('recommendation') or tuning.get('status'))}")
        lines.append(f"- sample_size={_value(tuning.get('sample_size'))}")
    if gate:
        lines.append("Futures gate effectiveness:")
        lines.append(f"- date={_value(gate.get('date'))}")
        lines.append(f"- sample_size={_value(gate.get('sample_size'))}")
    if research:
        lines.append("Latest research/replay artifacts:")
        lines.extend(f"- {path}" for path in research)
    if not any((report, tuning, gate, research)):
        lines.append("- No audit/research artifacts found.")
    lines.append("Verdict: use these as evidence snapshots only; do not change trading rules until sample-size thresholds are met.")
    return CapabilityAnswer("audit_recommendations", "\n".join(lines))


def _answer_spot_audit_recommendations() -> CapabilityAnswer:
    signals = family_rows("spot", "signals")
    metrics = family_rows("spot", "metrics")
    latest_metrics = {}
    if metrics.row and isinstance(metrics.row.get("rows"), list) and metrics.row["rows"]:
        latest_metrics = metrics.row["rows"][-1]
    lines = [
        "Spot audit recommendations snapshot",
        f"Signal rows: {signals.count}",
        f"Metrics rows: {metrics.count}",
    ]
    if latest_metrics:
        lines.append(f"Trades opened since start: {_value(latest_metrics.get('trades_opened_since_start'))}")
        lines.append(f"Buy signals since start: {_value(latest_metrics.get('buy_signals_since_start'))}")
        lines.append(f"No-signal rows since start: {_value(latest_metrics.get('no_signal_since_start'))}")
        lines.append(f"Signal-to-trade conversion: {_value(latest_metrics.get('signal_to_trade_conversion'))}")
    lines.append("Recommendation: Spot has no trade/audit sample yet; focus on signal gate diagnostics before changing trading rules.")
    lines.append(f"Source: {signals.source}")
    if metrics.source:
        lines.append(f"Source: {metrics.source}")
    return CapabilityAnswer("audit_recommendations", "\n".join(lines), tuple(source for source in (signals.source, metrics.source) if source))


def _latest_row(market: str, family: str) -> dict[str, Any]:
    result = family_rows(market, family)
    if result.row and isinstance(result.row.get("rows"), list) and result.row["rows"]:
        row = result.row["rows"][-1]
        return row if isinstance(row, dict) else {}
    return {}


def _value(value: Any) -> str:
    return "--" if value is None else str(value)
