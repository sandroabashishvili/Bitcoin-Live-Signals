"""File: permission_text.py
Folder: platform_v2/futures/services/simulation
Created date: 2026-06-01
Last updated date: 2026-06-02
Author: Codex
Purpose: Human-readable permission explanations for Futures simulation.
"""

from __future__ import annotations


def human_permission_text(*, reason: str, checks: dict[str, bool]) -> str:
    if reason == "allowed":
        return "Entry allowed. All risk checks passed."
    reason_map = {
        "signal_block": "No actionable futures signal right now.",
        "short_execution_disabled": "Legacy SHORT block from the pre-permission phase.",
        "manual_block": "Manual entry block is active.",
        "capital_block": "Available balance is below the minimum required level.",
        "exposure_block": "Exposure limit reached for current futures settings.",
        "position_slots_block": "Maximum open positions limit reached.",
        "direction_position_slots_block": "Maximum open positions limit reached for this direction.",
        "liquidation_buffer_block": "Stop loss is too close to the estimated liquidation zone.",
        "duplicate_block": "Existing same-direction position detected. Duplicate entry blocked.",
        "cooldown_block": "Same-direction cooldown window is active after previous entry.",
        "proximity_block": "Current entry is too close to the last same-direction entry price.",
        "entry_quality_block": "Entry timing is late or exhausted; direction alone is not enough for a clean entry!",
        "flip_confirmation_pending": "First SHORT direction flip detected. Waiting for the next closed 15-minute candle to confirm it.",
        "long_entry_location_block": "LONG entry is too extended into resistance for a clean entry!",
        "short_market_plan_zone_block": "SHORT entry is outside the current market-plan working zone!",
        "no_data": "No data yet. Waiting for enough candles to evaluate a setup.",
    }
    failed = [name for name, ok in checks.items() if not ok]
    failed_text = ", ".join(failed) if failed else "unknown"
    return f"{reason_map.get(reason, 'Entry denied by risk policy.')} Failed checks: {failed_text}."
