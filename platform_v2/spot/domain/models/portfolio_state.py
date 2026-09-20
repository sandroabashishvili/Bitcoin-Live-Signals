"""File: portfolio_state.py
Folder: platform_v2/spot/domain/models
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Portfolio-state domain models for SmartSignalHub V2.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioState:
    """Normalized portfolio state used by permission and execution layers.

    Args:
        available_balance: Capital currently available for new entries.
        current_open_exposure: Sum of open position sizes.
        open_positions_count: Number of open positions.
        last_entry_price: Latest known open entry price when available.
    """

    available_balance: float
    current_open_exposure: float
    open_positions_count: int
    last_entry_price: float | None = None
