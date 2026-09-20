"""File: explanations.py
Folder: platform_v2/futures/dashboard/overview_futures/py
Created date: 2026-05-25
Last updated date: 2026-06-02
Author: Codex
Purpose: Explanation builders for Futures Overview metric details.
"""

from __future__ import annotations

from typing import Any

from platform_v2.futures.dashboard.explanation_system import ExplanationItem, load_explanation_map


def build_overview_explanations(payload: dict[str, Any]) -> dict[str, ExplanationItem]:
    items = dict(load_explanation_map())
    denied_entry = payload.get("latest_denied_entry") or {}
    order = payload.get("latest_order") or {}
    signal = payload.get("latest_signal") or {}

    base_item = items.get("overview.primary_signal.entry_status")
    title = base_item.title if base_item else "Entry Status"
    summary = (
        base_item.summary
        if base_item
        else "Shows whether the latest BUY setup opened, was denied, or never became actionable."
    )
    details = (
        base_item.details
        if base_item
        else (
            "Opened means an order was actually filled and turned into a live position.",
            "Denied means the signal passed strategy logic but failed at least one execution permission rule!",
            "Blocked by Logic means market conditions were not ready for an actionable entry before execution permission was checked.",
            "No Action means there was no live trade event to execute or reject.",
        )
    )

    if denied_entry:
        raw_reason = str(
            denied_entry.get("denial_reason")
            or denied_entry.get("reason")
            or (denied_entry.get("permission") or {}).get("reason")
            or "unknown"
        )
        reason_text = _blocker_label(raw_reason)
        summary = f"Latest entry was denied by the execution layer. Main reason: {reason_text}."
    elif order.get("status") == "FILLED":
        summary = "Latest entry status is Opened because the most recent Futures setup became a filled order."
    elif str(signal.get("side") or "").upper() == "NO_SIGNAL":
        summary = "The latest setup is blocked by strategy logic before execution permission is even considered."
    else:
        summary = "No trade was opened or denied on the latest visible setup."

    items["overview.primary_signal.entry_status"] = ExplanationItem(
        key="overview.primary_signal.entry_status",
        title=title,
        summary=summary,
        details=details,
        severity=base_item.severity if base_item else "neutral",
        cta_label=base_item.cta_label if base_item else None,
        cta_href=base_item.cta_href if base_item else None,
        secondary_cta_label=base_item.secondary_cta_label if base_item else None,
        secondary_cta_href=base_item.secondary_cta_href if base_item else None,
    )
    return {key: item for key, item in items.items() if key.startswith("overview.")}


def _blocker_label(reason: str) -> str:
    label_map = {
        "entry_quality_block": "Entry timing blocked",
        "flip_confirmation_pending": "SHORT flip awaiting confirmation",
        "entry_history_gap": "Waiting for next candle after history gap",
        "short_entry_location_unconfirmed": "Mature SHORT needs a clean current entry zone",
        "long_entry_location_block": "Long into resistance",
        "short_market_plan_zone_block": "Outside short zone",
        "proximity_block": "Too close to recent entry",
        "cooldown_block": "Cooldown active",
        "signal_block": "No actionable setup",
        "capital_block": "Capital limit",
        "exposure_block": "Exposure limit",
        "position_slots_block": "Position limit",
        "direction_position_slots_block": "Direction limit",
        "duplicate_block": "Duplicate position",
        "liquidation_buffer_block": "Liquidation buffer",
        "manual_block": "Manual block",
        "no_data": "Missing data",
    }
    return label_map.get(reason, reason.replace("_", " ").title())
