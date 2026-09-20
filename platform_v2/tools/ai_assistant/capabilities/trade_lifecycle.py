"""Trade lifecycle reconstruction for Futures positions."""

from __future__ import annotations

import re
from typing import Any

from platform_v2.tools.ai_assistant.intents import AssistantIntent
from platform_v2.tools.ai_assistant.runtime_readers import family_rows

from .contracts import CapabilityAnswer


def answer_trade_lifecycle(intent: AssistantIntent | str) -> CapabilityAnswer:
    question = intent.question if isinstance(intent, AssistantIntent) else str(intent)
    market = intent.market if isinstance(intent, AssistantIntent) and intent.market in {"futures", "spot"} else "futures"
    position_id = _extract_position_id(question)
    position_family = "futures_positions" if market == "futures" else "positions"
    event_family = "futures_position_events" if market == "futures" else "position_events"
    audit_family = "futures_trade_entry_audits" if market == "futures" else "trade_entry_audits"
    positions = _rows(family_rows(market, position_family))
    events = _rows(family_rows(market, event_family))
    audits = _rows(family_rows(market, audit_family))
    if market == "spot" and not any((positions, events, audits)):
        return CapabilityAnswer(
            "trade_lifecycle",
            "Spot trade lifecycle: no positions/events/trade audit rows found. Spot runtime currently has signals, metrics, daily_summaries, and cycle_runs only.",
        )
    if not position_id:
        open_positions = [row for row in positions if str(row.get("status") or "").upper() == "OPEN"]
        if open_positions:
            position_id = str(open_positions[-1].get("position_id") or "")
    if not position_id:
        return CapabilityAnswer(
            "trade_lifecycle",
            f"{market.title()} trade lifecycle: no position id found and no open {market.title()} position exists.",
        )

    position_rows = [row for row in positions if str(row.get("position_id") or "") == position_id]
    event_rows = [row for row in events if str(row.get("position_id") or "") == position_id]
    audit_rows = [row for row in audits if str(row.get("position_id") or "") == position_id]
    latest = (position_rows or event_rows or audit_rows)[-1] if (position_rows or event_rows or audit_rows) else None
    if not latest:
        return CapabilityAnswer("trade_lifecycle", f"No {market.title()} lifecycle rows found for {position_id}.")

    lines = [f"{market.title()} trade lifecycle: {position_id}"]
    first_event = event_rows[0] if event_rows else position_rows[0] if position_rows else audit_rows[0]
    latest_event = event_rows[-1] if event_rows else position_rows[-1] if position_rows else audit_rows[-1]
    lines.append(f"Created/opened: {_value(first_event.get('opened_at') or first_event.get('entry_time'))}")
    lines.append(f"Side: {_value(latest.get('side'))}")
    lines.append(f"Status: {_value(latest.get('status') or latest.get('outcome'))}")
    lines.append(f"Entry: {_value(latest.get('entry_price'))}")
    lines.append(f"Current mark/exit: {_value(latest.get('mark_price') or latest.get('exit_price'))}")
    lines.append(f"Current/Net PnL: {_value(latest.get('unrealized_pnl') if latest.get('unrealized_pnl') is not None else latest.get('net_pnl'))}")
    lines.append(f"ROE %: {_value(latest.get('roe_pct'))}")
    lines.append(f"TP: {_value(latest.get('tp_price') or latest.get('take_profit'))}")
    lines.append(f"SL: {_value(latest.get('sl_price') or latest.get('stop_loss'))}")
    lines.append(f"Events found: {len(event_rows)}")
    if audit_rows:
        audit = audit_rows[-1]
        lines.append("Audit:")
        lines.append(f"- outcome={_value(audit.get('outcome'))}")
        lines.append(f"- close_time={_value(audit.get('close_time'))}")
        lines.append(f"- entry_timing={_value(audit.get('entry_timing_type'))}")
        lines.append(f"- entry_location={_value(audit.get('entry_location_type'))}")
        lines.append(f"- net_pnl={_value(audit.get('net_pnl'))}")
    lines.append("Lifecycle:")
    lines.append(f"- first_event_time={_event_time(first_event)}")
    lines.append(f"- latest_event_time={_event_time(latest_event)}")
    return CapabilityAnswer("trade_lifecycle", "\n".join(lines))


def _extract_position_id(question: str) -> str | None:
    match = re.search(r"\b(?:FUT|SPOT)-\d{6}\b", question, flags=re.IGNORECASE)
    return match.group(0).upper() if match else None


def _rows(result: Any) -> list[dict[str, Any]]:
    if result.row and isinstance(result.row.get("rows"), list):
        return [row for row in result.row["rows"] if isinstance(row, dict)]
    return []


def _event_time(row: dict[str, Any]) -> str:
    return str(row.get("decision_time") or row.get("candle_close_time") or row.get("time_readable") or row.get("entry_time") or row.get("opened_at") or "--")


def _value(value: Any) -> str:
    return "--" if value is None else str(value)
