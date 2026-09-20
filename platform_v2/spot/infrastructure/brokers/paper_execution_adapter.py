"""File: paper_execution_adapter.py
Folder: platform_v2/spot/infrastructure/brokers
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Dry-run execution adapter for V2 order flow validation.
"""

from __future__ import annotations

from ...domain.models.order import OrderFill, OrderRequest, OrderResult, OrderStatus
from ...services.account.fee_service import FeeService
from .exchange_adapter import ExchangeAdapter


class PaperExecutionAdapter(ExchangeAdapter):
    """Simulate immediate fills without touching a real exchange."""

    def submit_order(self, request: OrderRequest) -> OrderResult:
        """Fill a dry-run order immediately at the provided request price."""

        if request.price is None or float(request.price) <= 0:
            raise ValueError(f"PaperExecutionAdapter requires positive request.price, got {request.price!r}")
        fill_price = float(request.price)
        fee_paid = FeeService.entry_fee_for_notional(request.quantity)
        fee_asset = "USDT" if request.symbol.endswith("USDT") else None
        return OrderResult(
            request=request,
            status=OrderStatus.FILLED,
            exchange_order_id=f"paper:{request.client_order_id}",
            fill=OrderFill(
                fill_price=fill_price,
                fill_quantity=request.quantity,
                filled_at_ms=request.requested_at_ms,
                fee_paid=fee_paid,
                fee_asset=fee_asset,
            ),
        )
