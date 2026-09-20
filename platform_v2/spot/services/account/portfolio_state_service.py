"""File: portfolio_state_service.py
Folder: platform_v2/spot/services
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Build current portfolio state from runtime position records.
"""

from __future__ import annotations

from platform_v2.spot.config import settings
from platform_v2.spot.domain.models.portfolio_state import PortfolioState
from platform_v2.spot.services.account.fee_service import FeeService
from platform_v2.spot.services.account.position_state_service import PositionStateService


class PortfolioStateService:
    """Read recent runtime position files and summarize current open state."""

    def __init__(self, position_state_service: PositionStateService | None = None) -> None:
        """Initialize runtime position state dependency."""

        self._position_state_service = position_state_service or PositionStateService()

    def build_state(
        self,
        *,
        starting_balance: float = settings.DEFAULT_STARTING_BALANCE,
        lookback_days: int | None = settings.DEFAULT_LOOKBACK_DAYS,
        as_of_date_iso: str | None = None,
    ) -> PortfolioState:
        """Build current portfolio state from latest open positions."""

        positions = self._position_state_service.load_latest_positions(
            lookback_days=lookback_days,
            as_of_date_iso=as_of_date_iso,
        )
        open_positions = [position for position in positions if position.is_open]
        closed_positions = [position for position in positions if position.is_closed]

        current_open_exposure = 0.0
        last_entry_price = None
        for position in open_positions:
            current_open_exposure += position.execution.position_size
            if position.execution.entry_price > 0:
                last_entry_price = position.execution.entry_price

        open_entry_fees = FeeService.open_entry_fees_total(open_positions)
        closed_net_pnl = sum(FeeService.net_pnl_value(position) for position in closed_positions)
        available_balance = starting_balance + closed_net_pnl - current_open_exposure - open_entry_fees
        if available_balance < 0:
            available_balance = 0.0

        return PortfolioState(
            available_balance=available_balance,
            current_open_exposure=current_open_exposure,
            open_positions_count=len(open_positions),
            last_entry_price=last_entry_price,
        )
