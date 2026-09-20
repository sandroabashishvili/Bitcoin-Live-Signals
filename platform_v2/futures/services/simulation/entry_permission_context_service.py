"""File: entry_permission_context_service.py
Folder: platform_v2/futures/services/simulation
Created date: 2026-06-01
Last updated date: 2026-06-01
Author: Codex
Purpose: Build Futures entry permission context for market-plan and entry-location checks.
"""

from __future__ import annotations

from typing import Any

from platform_v2.futures.config import settings
from platform_v2.futures.domain.entry_timing import FRESH_OR_EARLY_TIMINGS
from platform_v2.futures.domain.models.signal import GateSnapshot
from platform_v2.shared.backend.runtime_store.futures import MARKET_PLANS_FAMILY
from platform_v2.futures.services.analytics.trade_audit import EntryLocationClassifier
from platform_v2.futures.storage import indicator_snapshot_file_path, load_json_list

from .common import as_optional_float
from .runtime_store import FuturesSimulationRuntimeStore


class FuturesEntryPermissionContextService:
    """Build non-account permission context for a Futures entry candidate."""

    def __init__(
        self, *, runtime_store: FuturesSimulationRuntimeStore,
        short_continuation_override_enabled: bool = settings.SHORT_CONTINUATION_OVERRIDE_ENABLED,
    ) -> None:
        self._runtime_store = runtime_store
        self._short_continuation_override_enabled = short_continuation_override_enabled

    def market_plan_permission(
        self,
        *,
        signal_side: str,
        entry_price: float,
        timestamp_ms: int,
    ) -> dict[str, Any]:
        normalized_side = self._normalize_direction(signal_side)
        if normalized_side != "SHORT":
            return {"allowed": True, "alignment": "NOT_SHORT"}

        market_plans = sorted(
            self._runtime_store.load_family_rows_all(family_name=MARKET_PLANS_FAMILY),
            key=lambda row: int(row.get("timestamp_ms") or 0),
        )
        plan = self._nearest_prior_market_plan(market_plans=market_plans, timestamp_ms=timestamp_ms)
        if not plan:
            return {"allowed": True, "alignment": "NO_PLAN"}

        short_plan = plan.get("short_plan")
        if not isinstance(short_plan, dict):
            return {
                "allowed": True,
                "alignment": "NO_SIDE_PLAN",
                "plan_timestamp_ms": plan.get("timestamp_ms"),
                "bias": plan.get("bias"),
            }

        nearest_zone = self._nearest_market_plan_zone(
            entry_price=entry_price,
            zones=short_plan.get("zones"),
        )
        if not nearest_zone:
            return {
                "allowed": True,
                "alignment": "NO_ZONE",
                "plan_timestamp_ms": plan.get("timestamp_ms"),
                "bias": plan.get("bias"),
                "side_plan_status": short_plan.get("status"),
            }

        in_zone = bool(nearest_zone.get("entry_in_zone"))
        alignment = "IN_ZONE" if in_zone else "OUTSIDE_ZONE"
        return {
            "allowed": in_zone,
            "alignment": alignment,
            "plan_timestamp_ms": plan.get("timestamp_ms"),
            "bias": plan.get("bias"),
            "side_plan_status": short_plan.get("status"),
            "plan_location": plan.get("location"),
            "nearest_zone": nearest_zone,
        }

    def apply_entry_quality_override(
        self,
        *,
        signal_side: str,
        entry_quality: dict[str, Any],
        gates: GateSnapshot,
        score: float,
    ) -> dict[str, Any]:
        if bool(entry_quality.get("allowed", True)):
            return entry_quality
        normalized_side = self._normalize_direction(signal_side)
        timing_type = str(entry_quality.get("timing_type") or "").upper()
        passed_gate_count = self.passed_gate_count(gates)
        allowed = (
            normalized_side == "SHORT"
            and entry_quality.get("reason") == "entry_quality_block"
            and timing_type == "LATE_EXTENSION"
            and passed_gate_count >= 2
            and score >= 9.0
        )
        if not allowed:
            return entry_quality

        updated = dict(entry_quality)
        updated["allowed"] = True
        updated["reason"] = "late_extension_short_override"
        updated["override"] = {
            "allowed": True,
            "reason": "short_late_extension_still_confirmed",
            "timing_type": timing_type,
            "passed_gate_count": passed_gate_count,
            "score": round(score, 2),
        }
        return updated

    def apply_short_continuation_override(
        self,
        *,
        signal_side: str,
        market_plan_permission: dict[str, Any],
        entry_price: float,
        entry_quality: dict[str, Any],
        gates: GateSnapshot,
        score: float,
    ) -> dict[str, Any]:
        if not self._short_continuation_override_enabled:
            return market_plan_permission
        if bool(market_plan_permission.get("allowed", True)):
            return market_plan_permission
        normalized_side = self._normalize_direction(signal_side)
        if normalized_side != "SHORT":
            return market_plan_permission
        if str(market_plan_permission.get("alignment") or "").upper() != "OUTSIDE_ZONE":
            return market_plan_permission

        nearest_zone = market_plan_permission.get("nearest_zone")
        nearest_zone = nearest_zone if isinstance(nearest_zone, dict) else {}
        zone_from = as_optional_float(nearest_zone.get("from"))
        entry_in_zone = bool(nearest_zone.get("entry_in_zone"))
        if entry_in_zone or zone_from is None:
            return market_plan_permission

        plan_location = market_plan_permission.get("plan_location")
        plan_location = plan_location if isinstance(plan_location, dict) else {}
        swing_low_distance = as_optional_float(plan_location.get("distance_to_swing_low_atr"))
        short_entry_state = str(plan_location.get("short_entry_state") or "").upper()
        timing_type = str(entry_quality.get("timing_type") or "").upper()
        passed_gate_count = self.passed_gate_count(gates)

        below_zone = entry_price < zone_from
        continuation_allowed = (
            below_zone
            and bool(entry_quality.get("allowed", False))
            and timing_type in FRESH_OR_EARLY_TIMINGS
            and swing_low_distance is not None
            and swing_low_distance > 0.3
            and (passed_gate_count >= 3 or score >= 10.5)
        )
        if not continuation_allowed:
            return market_plan_permission

        updated = dict(market_plan_permission)
        updated["allowed"] = True
        updated["alignment"] = "OUTSIDE_ZONE_CONTINUATION_OVERRIDE"
        updated["continuation_override"] = {
            "allowed": True,
            "reason": "short_breakdown_continuation_with_support_room",
            "timing_type": timing_type,
            "passed_gate_count": passed_gate_count,
            "score": round(score, 2),
            "distance_to_swing_low_atr": swing_low_distance,
            "short_entry_state": short_entry_state,
            "entry_price": round(entry_price, 2),
            "zone_from": round(zone_from, 2),
        }
        return updated

    def entry_location_permission(
        self,
        *,
        signal_side: str,
        symbol: str,
        timeframe: str,
        entry_price: float,
    ) -> dict[str, Any]:
        normalized_side = self._normalize_direction(signal_side)
        if normalized_side != "LONG":
            return {"allowed": True, "location_type": "NOT_LONG"}

        snapshot = self._latest_indicator_snapshot(symbol=symbol, timeframe=timeframe)
        if not snapshot:
            return {"allowed": True, "location_type": "NO_SNAPSHOT"}

        location = EntryLocationClassifier.classify(
            side=normalized_side,
            entry_price=entry_price,
            snapshot=snapshot,
        )
        location_type = str(location.get("type") or "UNKNOWN").upper()
        blocked_locations = {str(value).upper() for value in settings.LONG_ENTRY_BLOCKED_LOCATIONS}
        return {
            "allowed": location_type not in blocked_locations,
            "location_type": location_type,
            "blocked_locations": sorted(blocked_locations),
            "location": location,
        }

    @staticmethod
    def passed_gate_count(gates: GateSnapshot) -> int:
        return sum(
            1
            for name in ("mtf", "regime", "momentum", "trend", "orderbook", "structure")
            if bool(getattr(gates, name, False))
        )

    @staticmethod
    def _latest_indicator_snapshot(*, symbol: str, timeframe: str) -> dict[str, Any]:
        rows = load_json_list(indicator_snapshot_file_path(symbol, timeframe))
        if not rows:
            return {}
        latest = rows[-1]
        return latest if isinstance(latest, dict) else {}

    @staticmethod
    def _nearest_prior_market_plan(
        *,
        market_plans: list[dict[str, Any]],
        timestamp_ms: int,
    ) -> dict[str, Any]:
        prior: dict[str, Any] = {}
        for row in market_plans:
            row_ts = int(row.get("timestamp_ms") or 0)
            if row_ts > timestamp_ms:
                break
            prior = row
        return prior

    def _nearest_market_plan_zone(self, *, entry_price: float, zones: Any) -> dict[str, Any]:
        if entry_price <= 0 or not isinstance(zones, list):
            return {}
        zone_rows = [zone for zone in zones if isinstance(zone, dict)]
        if not zone_rows:
            return {}
        nearest = min(
            zone_rows,
            key=lambda zone: self._market_plan_zone_distance(entry_price=entry_price, zone=zone),
        )
        zone_from = as_optional_float(nearest.get("from"))
        zone_to = as_optional_float(nearest.get("to"))
        entry_in_zone = zone_from is not None and zone_to is not None and zone_from <= entry_price <= zone_to
        return {
            "name": nearest.get("name"),
            "from": zone_from,
            "to": zone_to,
            "center": as_optional_float(nearest.get("center")),
            "entry_in_zone": entry_in_zone,
        }

    @staticmethod
    def _market_plan_zone_distance(*, entry_price: float, zone: dict[str, Any]) -> float:
        center = as_optional_float(zone.get("center"))
        if center is None:
            return 0.0
        return abs(center - entry_price)

    @staticmethod
    def _normalize_direction(direction: str) -> str:
        normalized = str(direction or "").upper()
        if normalized == "BUY":
            return "LONG"
        if normalized == "SELL":
            return "SHORT"
        return normalized
