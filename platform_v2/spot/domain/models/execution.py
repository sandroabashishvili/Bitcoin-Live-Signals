"""File: execution.py
Folder: platform_v2/spot/domain/models
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Execution and permission-side domain models for SmartSignalHub V2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .position import ExecutionSetup, PositionRecord
from .signal import SignalDecision, TheoreticalSetup


class PermissionStatus(str, Enum):
    """Supported permission outcomes."""

    ALLOWED = "ALLOWED"
    DENIED = "DENIED"


class DenialReason(str, Enum):
    """Normalized denial reasons."""

    MANUAL_BLOCK = "manual_block"
    CAPITAL_BLOCK = "capital_block"
    EXPOSURE_BLOCK = "exposure_block"
    DUPLICATE_BLOCK = "duplicate_block"
    COOLDOWN_BLOCK = "cooldown_block"
    PROXIMITY_BLOCK = "proximity_block"
    WEAK_OPEN_POSITION_BLOCK = "weak_open_position_block"
    BUY_ENTRY_LOCATION_BLOCK = "buy_entry_location_block"
    EXECUTION_QUOTE_UNAVAILABLE = "execution_quote_unavailable"
    ENTRY_QUALITY_BLOCK = "entry_quality_block"
    POSITION_SLOTS_BLOCK = "position_slots_block"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PermissionChecks:
    """Detailed gate results from the permission layer.

    Args:
        signal_is_actionable: Whether the signal is actionable at all.
        manual_block: Manual block state.
        capital: Capital check result.
        exposure: Exposure check result.
        duplicate: Duplicate-position check result.
        cooldown: Cooldown check result.
        proximity: Proximity check result.
        weak_open_position: Weak-open-position check result.
    """

    signal_is_actionable: bool = False
    manual_block: bool = True
    capital: bool = True
    exposure: bool = True
    duplicate: bool = True
    cooldown: bool = True
    proximity: bool = True
    weak_open_position: bool = True
    buy_entry_location: bool = True
    execution_quote: bool = True
    entry_quality: bool = True
    position_slots: bool = True


@dataclass(frozen=True)
class PermissionContext:
    """Runtime context used while evaluating permission rules.

    Args:
        available_balance: Available balance at decision time.
        current_open_exposure: Current open exposure.
        open_positions_count: Number of open positions.
        entry_price: Current execution candidate price.
        last_entry_price: Last opened entry price when available.
        proximity_pct: Active proximity threshold.
        timestamp: Human-readable timestamp.
    """

    available_balance: float | None = None
    current_open_exposure: float | None = None
    open_positions_count: int | None = None
    entry_price: float | None = None
    last_entry_price: float | None = None
    proximity_pct: float | None = None
    timestamp: str | None = None


@dataclass(frozen=True)
class PermissionDecision:
    """Permission-layer result for a signal.

    Args:
        status: Permission status.
        reason: Main allow/deny reason.
        checks: Individual permission checks.
        context: Permission context snapshot.
    """

    status: PermissionStatus
    reason: str
    checks: PermissionChecks = field(default_factory=PermissionChecks)
    context: PermissionContext = field(default_factory=PermissionContext)

    @property
    def is_allowed(self) -> bool:
        """Return whether the signal passed permission checks.

        Returns:
            bool: True when the decision is ALLOWED.
        """

        return self.status == PermissionStatus.ALLOWED


@dataclass(frozen=True)
class DeniedEntryRecord:
    """Normalized denied-entry record for analytics and review.

    Args:
        signal: Source signal decision.
        permission: Permission result.
        live_entry_price: Current price seen during the denied attempt.
        denial_reason: Normalized denial reason.
        theoretical_setup: Theoretical setup attached to the signal.
    """

    signal: SignalDecision
    permission: PermissionDecision
    live_entry_price: float
    denial_reason: DenialReason = DenialReason.UNKNOWN
    theoretical_setup: TheoreticalSetup | None = None


@dataclass(frozen=True)
class ExecutionAttempt:
    """Execution attempt created after signal and permission evaluation.

    Args:
        signal: Source signal decision.
        permission: Permission result.
        live_entry_price: Current entry candidate price.
        execution_setup: Real execution setup when allowed.
        position: Opened position when the attempt succeeded.
    """

    signal: SignalDecision
    permission: PermissionDecision
    live_entry_price: float
    execution_setup: ExecutionSetup | None = None
    position: PositionRecord | None = None

    @property
    def opened_position(self) -> bool:
        """Return whether this attempt produced an opened position.

        Returns:
            bool: True when a position record exists.
        """

        return self.position is not None
