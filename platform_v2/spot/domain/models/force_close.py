"""File: force_close.py
Folder: platform_v2/spot/domain/models
Created date: 2026-03-31
Last updated date: 2026-03-31
Author: Codex
Purpose: Normalized force-close event model for SmartSignalHub V2 runtime logs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ForceCloseEvent:
    """Normalized runtime event for one market-based forced close."""

    timestamp: str
    reason: str
    trigger_position_id: str
    trigger_unrealized_pnl: float
    trigger_unrealized_pct: float
    closed_position_id: str
    symbol: str
    timeframe: str
    closed_entry_price: float
    closed_exit_price: float
    closed_net_pnl: float
