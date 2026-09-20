"""File: order.py
Folder: platform_v2/spot/domain/models
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Core exchange-order models for the V2 execution boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OrderSide(StrEnum):
    """Directional side for an exchange order."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    """Supported order types for the first V2 execution layer."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(StrEnum):
    """Normalized order lifecycle status."""

    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"


@dataclass(frozen=True)
class OrderRequest:
    """Execution request sent from V2 services to an exchange adapter."""

    symbol: str
    timeframe: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    client_order_id: str
    requested_at_ms: int
    price: float | None = None
    dry_run: bool = True


@dataclass(frozen=True)
class OrderFill:
    """Normalized fill information returned by an exchange adapter."""

    fill_price: float
    fill_quantity: float
    filled_at_ms: int
    fee_paid: float = 0.0
    fee_asset: str | None = None


@dataclass(frozen=True)
class OrderResult:
    """Execution result returned by an exchange adapter."""

    request: OrderRequest
    status: OrderStatus
    exchange_order_id: str | None = None
    fill: OrderFill | None = None
    rejection_reason: str | None = None

    @property
    def is_filled(self) -> bool:
        """Return True when the order reached FILLED state."""

        return self.status == OrderStatus.FILLED and self.fill is not None
