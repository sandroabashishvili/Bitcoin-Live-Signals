"""File: permission_decision_service.py
Folder: platform_v2/spot/services
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Build normalized permission decisions for V2 execution flow.
"""

from __future__ import annotations

from datetime import datetime, timezone

from platform_v2.spot.config import settings
from platform_v2.spot.domain.models.execution import (
    DenialReason,
    PermissionChecks,
    PermissionContext,
    PermissionDecision,
    PermissionStatus,
)
from platform_v2.spot.domain.models.signal import SignalDecision, SignalSide


class PermissionDecisionService:
    """Evaluate whether a signal may proceed toward execution."""

    def __init__(
        self,
        min_required_balance: float = settings.MIN_REQUIRED_BALANCE,
        max_open_positions: int = settings.MAX_OPEN_POSITIONS,
        max_open_exposure: float = settings.MAX_OPEN_EXPOSURE,
        default_position_size: float = settings.DEFAULT_POSITION_SIZE,
        default_proximity_pct: float = settings.DEFAULT_PROXIMITY_PCT,
    ) -> None:
        """Initialize baseline permission thresholds."""

        self._min_required_balance = min_required_balance
        self._max_open_positions = max_open_positions
        self._max_open_exposure = max_open_exposure
        self._default_position_size = default_position_size
        self._default_proximity_pct = default_proximity_pct

    def evaluate(
        self,
        signal: SignalDecision,
        live_entry_price: float,
        *,
        available_balance: float | None = None,
        current_open_exposure: float | None = None,
        open_positions_count: int = 0,
        last_entry_price: float | None = None,
        manual_block: bool = False,
        cooldown_active: bool = False,
        duplicate_active: bool = False,
        weak_open_position_active: bool = False,
        buy_entry_location_ok: bool = True,
        proximity_pct: float | None = None,
        timestamp_text: str | None = None,
    ) -> PermissionDecision:
        """Build a normalized permission decision for one signal."""

        if proximity_pct is None:
            proximity_pct = self._default_proximity_pct
        if timestamp_text is None:
            timestamp_text = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        signal_is_actionable = signal.side != SignalSide.NO_SIGNAL
        capital_ok = available_balance is None or available_balance >= self._min_required_balance
        projected_exposure = (current_open_exposure or 0.0) + self._default_position_size
        exposure_ok = projected_exposure <= self._max_open_exposure
        duplicate_ok = not duplicate_active
        cooldown_ok = not cooldown_active
        weak_open_position_ok = not (settings.WEAK_OPEN_POSITION_BLOCK_ENABLED and weak_open_position_active)
        proximity_ok = self._passes_proximity(
            live_entry_price=live_entry_price,
            last_entry_price=last_entry_price,
            proximity_pct=proximity_pct,
        )

        checks = PermissionChecks(
            position_slots=open_positions_count < self._max_open_positions,
            signal_is_actionable=signal_is_actionable,
            manual_block=not manual_block,
            capital=capital_ok,
            exposure=exposure_ok,
            duplicate=duplicate_ok,
            cooldown=cooldown_ok,
            proximity=proximity_ok,
            weak_open_position=weak_open_position_ok,
            buy_entry_location=buy_entry_location_ok,
        )
        context = PermissionContext(
            available_balance=available_balance,
            current_open_exposure=current_open_exposure,
            open_positions_count=open_positions_count,
            entry_price=live_entry_price,
            last_entry_price=last_entry_price,
            proximity_pct=proximity_pct,
            timestamp=timestamp_text,
        )

        denial_reason = self._pick_denial_reason(
            signal_is_actionable=signal_is_actionable,
            manual_block=manual_block,
            capital_ok=capital_ok,
            exposure_ok=exposure_ok,
            duplicate_ok=duplicate_ok,
            cooldown_ok=cooldown_ok,
            proximity_ok=proximity_ok,
            weak_open_position_ok=weak_open_position_ok,
            buy_entry_location_ok=buy_entry_location_ok,
        )
        if denial_reason is None:
            if not checks.position_slots:
                return PermissionDecision(status=PermissionStatus.DENIED,
                    reason=DenialReason.POSITION_SLOTS_BLOCK.value, checks=checks, context=context)
            return PermissionDecision(
                status=PermissionStatus.ALLOWED,
                reason="allowed",
                checks=checks,
                context=context,
            )

        return PermissionDecision(
            status=PermissionStatus.DENIED,
            reason=denial_reason.value,
            checks=checks,
            context=context,
        )

    @staticmethod
    def _passes_proximity(
        *,
        live_entry_price: float,
        last_entry_price: float | None,
        proximity_pct: float,
    ) -> bool:
        """Return whether the live price is sufficiently far from the last entry."""

        if last_entry_price is None or last_entry_price <= 0 or live_entry_price <= 0:
            return True

        distance_pct = abs(live_entry_price - last_entry_price) / last_entry_price * 100.0
        return distance_pct > proximity_pct

    @staticmethod
    def _pick_denial_reason(
        *,
        signal_is_actionable: bool,
        manual_block: bool,
        capital_ok: bool,
        exposure_ok: bool,
        duplicate_ok: bool,
        cooldown_ok: bool,
        proximity_ok: bool,
        weak_open_position_ok: bool,
        buy_entry_location_ok: bool,
    ) -> DenialReason | None:
        """Pick the first normalized denial reason from the current check states."""

        if not signal_is_actionable:
            return DenialReason.UNKNOWN
        if manual_block:
            return DenialReason.MANUAL_BLOCK
        if not capital_ok:
            return DenialReason.CAPITAL_BLOCK
        if not exposure_ok:
            return DenialReason.EXPOSURE_BLOCK
        if not duplicate_ok:
            return DenialReason.DUPLICATE_BLOCK
        if not cooldown_ok:
            return DenialReason.COOLDOWN_BLOCK
        if not proximity_ok:
            return DenialReason.PROXIMITY_BLOCK
        if not weak_open_position_ok:
            return DenialReason.WEAK_OPEN_POSITION_BLOCK
        if not buy_entry_location_ok:
            return DenialReason.BUY_ENTRY_LOCATION_BLOCK
        return None
