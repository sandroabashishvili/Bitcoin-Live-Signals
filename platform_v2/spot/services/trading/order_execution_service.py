"""File: order_execution_service.py
Folder: platform_v2/spot/services
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Build and submit normalized V2 order requests through an exchange adapter.
"""

from __future__ import annotations

from uuid import uuid4

from platform_v2.spot.domain.models.order import OrderRequest, OrderResult, OrderSide, OrderType
from platform_v2.spot.domain.models.signal import SignalDecision, SignalSide
from platform_v2.spot.infrastructure.brokers.exchange_adapter import ExchangeAdapter
from platform_v2.spot.infrastructure.brokers.paper_execution_adapter import PaperExecutionAdapter
from platform_v2.shared.backend.time import utc_now_ms


class OrderExecutionService:
    """Convert a V2 signal into a normalized order request and execute it."""

    def __init__(self, exchange_adapter: ExchangeAdapter | None = None) -> None:
        self._exchange_adapter = exchange_adapter or PaperExecutionAdapter()

    def execute_market_order(
        self,
        *,
        signal: SignalDecision,
        quantity: float,
        entry_price: float,
        dry_run: bool = True,
    ) -> OrderResult:
        """Submit a market order for an allowed signal."""

        if entry_price <= 0:
            raise ValueError(f"entry_price must be > 0, got {entry_price!r}")

        request = OrderRequest(
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            side=self._map_side(signal.side),
            order_type=OrderType.MARKET,
            quantity=quantity,
            client_order_id=uuid4().hex,
            requested_at_ms=utc_now_ms(),
            price=entry_price,
            dry_run=dry_run,
        )
        return self._exchange_adapter.submit_order(request)

    @staticmethod
    def _map_side(side: SignalSide) -> OrderSide:
        """Map signal side to order side."""

        if side == SignalSide.BUY:
            return OrderSide.BUY
        if side == SignalSide.SELL:
            return OrderSide.SELL
        raise ValueError("Cannot execute an order for NO_SIGNAL")
