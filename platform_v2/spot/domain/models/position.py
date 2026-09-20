"""File: position.py
Folder: platform_v2/spot/domain/models
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Position-side domain models for SmartSignalHub V2.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .signal import SignalSide


class PositionStatus(str, Enum):
    """Supported position lifecycle states."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"


class ExitReason(str, Enum):
    """Supported normalized exit reasons."""

    TP_HIT = "tp_hit"
    PROFIT_LOCK_HIT = "profit_lock_hit"
    SL_HIT = "sl_hit"
    FORCE_CLOSE = "force_close"
    MANUAL = "manual"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ExecutionSetup:
    """Execution-time setup derived from a real entry price.

    Args:
        entry_price: Real execution entry price.
        stop_loss: Stop-loss level for the opened position.
        take_profit: Take-profit level for the opened position.
        rr_ratio: Risk-reward ratio.
        position_size: Capital allocated to the position.
        mode: SL/TP mode identifier.
    """

    entry_price: float
    stop_loss: float
    take_profit: float
    rr_ratio: float
    position_size: float
    mode: str = "unknown"


@dataclass(frozen=True)
class PositionRecord:
    """Normalized position record used across V2.

    Args:
        position_id: Stable position identifier across lifecycle updates.
        symbol: Instrument symbol.
        timeframe: Signal timeframe that opened the position.
        side: Position direction.
        status: Current position status.
        execution: Execution-time setup.
        opened_at: Open timestamp in readable form.
        closed_at: Close timestamp in readable form when available.
        exit_price: Real exit price when available.
        exit_reason: Normalized close reason.
        pnl: Gross pnl value.
        net_pnl: Net pnl value after fees/slippage.
        unrealized_pnl: Unrealized pnl while position is open.
        was_force_closed: Whether the close was forced by risk logic.
        force_close_reason: Optional force-close detail.
        exit_check_timeframe: Candle timeframe used to confirm the exit.
        exit_trigger_candle_close_ms: Close timestamp of the candle that confirmed the exit.
        exit_trigger_price: Exact TP/SL or force-close trigger price.
        exit_trigger_type: Normalized trigger tag used by runtime/reporting.
    """

    position_id: str
    symbol: str
    timeframe: str
    side: SignalSide
    status: PositionStatus
    execution: ExecutionSetup
    opened_at: str
    opened_at_ms: int | None = None
    signal_candle_close_time: str | None = None
    decision_time: str | None = None
    signal_reference_price: float | None = None
    execution_quote_source: str | None = None
    closed_at: str | None = None
    exit_price: float | None = None
    exit_reason: ExitReason = ExitReason.UNKNOWN
    pnl: float | None = None
    net_pnl: float | None = None
    unrealized_pnl: float | None = None
    was_force_closed: bool = False
    force_close_reason: str | None = None
    exit_check_timeframe: str | None = None
    exit_trigger_candle_close_ms: int | None = None
    exit_trigger_price: float | None = None
    exit_trigger_type: str | None = None
    strategy_version: str = "unknown"
    source_market: str = "spot"
    source_strategy_version: str | None = None
    position_management: dict | None = None

    @property
    def is_open(self) -> bool:
        """Return whether the position is still open.

        Returns:
            bool: True when the position status is OPEN.
        """

        return self.status == PositionStatus.OPEN

    @property
    def is_closed(self) -> bool:
        """Return whether the position has been closed.

        Returns:
            bool: True when the position status is CLOSED.
        """

        return self.status == PositionStatus.CLOSED
