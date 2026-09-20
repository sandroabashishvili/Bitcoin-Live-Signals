"""Pure permission helpers shared by portfolio research replays."""

from __future__ import annotations

from typing import Any

from platform_v2.futures.config import settings as futures_settings
from platform_v2.futures.domain.entry_timing import (
    FRESH_OR_EARLY_TIMINGS,
    EntryTimingContext,
    classify_entry_timing,
)
from platform_v2.spot.config import settings as spot_settings
from platform_v2.spot.services.analytics.entry_location_classifier import SpotEntryLocationClassifier
from platform_v2.tools.research.replay.historical_component_replay import _float
from platform_v2.tools.research.replay.portfolio_replay_state import OpenPosition


def spot_permission_reason(
    *,
    price: float,
    snapshot: Any,
    open_positions: list[OpenPosition],
    realized_net_pnl: float,
    timestamp_ms: int,
) -> str:
    exposure = sum(position.margin for position in open_positions)
    open_entry_fees = sum(position.entry_fee for position in open_positions)
    available = float(spot_settings.DEFAULT_STARTING_BALANCE) + realized_net_pnl - exposure - open_entry_fees
    if available < float(spot_settings.MIN_REQUIRED_BALANCE):
        return "capital_block"
    if exposure + float(spot_settings.DEFAULT_POSITION_SIZE) > float(spot_settings.MAX_OPEN_EXPOSURE):
        return "exposure_block"
    if any(abs(position.entry - price) < 0.0001 for position in open_positions):
        return "duplicate_block"
    if open_positions:
        latest = max(open_positions, key=lambda position: position.entry_timestamp_ms)
        if timestamp_ms < latest.entry_timestamp_ms + int(spot_settings.DEFAULT_COOLDOWN_SECONDS * 1000):
            return "cooldown_block"
        distance_pct = abs(price - latest.entry) / latest.entry * 100.0
        if distance_pct <= float(spot_settings.DEFAULT_PROXIMITY_PCT):
            return "proximity_block"
        if any((price - position.entry) / position.entry <= float(spot_settings.WEAK_OPEN_POSITION_PCT) for position in open_positions):
            return "weak_open_position_block"
    location = SpotEntryLocationClassifier.classify(entry_price=price, snapshot=snapshot.__dict__)
    if str(location.get("type") or "").upper() in {
        str(value).upper() for value in spot_settings.BUY_ENTRY_BLOCKED_LOCATIONS
    }:
        return "buy_entry_location_block"
    return "allowed"


def gate_count(side: str, components: dict[str, float]) -> int:
    side = side.upper()
    thresholds = {
        "mtf": float(futures_settings.MTF_RAW_GATE_MIN),
        "regime": float(futures_settings.REGIME_RAW_GATE_MIN),
        "trend": float(futures_settings.TREND_RAW_MIN),
        "momentum": float(
            futures_settings.SHORT_MOMENTUM_RAW_GATE_MIN
            if side == "SHORT"
            else futures_settings.MOMENTUM_RAW_GATE_MIN
        ),
        "orderbook": float(futures_settings.ORDERBOOK_RAW_GATE_MIN),
        "structure": float(
            futures_settings.SHORT_STRUCTURE_RAW_GATE_MIN
            if side == "SHORT"
            else futures_settings.LONG_STRUCTURE_RAW_GATE_MIN
        ),
    }
    return sum(_float(components.get(name)) >= threshold for name, threshold in thresholds.items())


def timing_context(*, side: str, prior_sides: list[str]) -> EntryTimingContext:
    return classify_entry_timing(side=side, prior_sides=prior_sides)


def short_market_plan_ok(
    *,
    entry_price: float,
    plan: dict[str, Any] | None,
    timing_type_name: str,
    passed_gate_count: int,
    score: float,
) -> bool:
    if not plan:
        return True
    short_plan = plan.get("short_plan")
    if not isinstance(short_plan, dict):
        return True
    zones = [zone for zone in short_plan.get("zones", []) if isinstance(zone, dict)]
    if not zones:
        return True
    zone = min(zones, key=lambda item: abs(_float(item.get("center")) - entry_price))
    zone_from = _float(zone.get("from"))
    zone_to = _float(zone.get("to"))
    if zone_from <= entry_price <= zone_to:
        return True
    location = plan.get("location") if isinstance(plan.get("location"), dict) else {}
    swing_low_distance = location.get("distance_to_swing_low_atr")
    if swing_low_distance is None:
        return False
    return bool(
        entry_price < zone_from
        and timing_type_name in FRESH_OR_EARLY_TIMINGS
        and _float(swing_low_distance) > 0.3
        and (passed_gate_count >= 3 or score >= 10.5)
    )
