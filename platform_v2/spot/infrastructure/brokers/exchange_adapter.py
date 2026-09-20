"""File: exchange_adapter.py
Folder: platform_v2/spot/infrastructure/brokers
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Abstract execution adapter boundary for V2 exchange integrations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ...domain.models.order import OrderRequest, OrderResult


class ExchangeAdapter(ABC):
    """Abstract adapter that executes normalized V2 order requests."""

    @abstractmethod
    def submit_order(self, request: OrderRequest) -> OrderResult:
        """Submit one normalized order request and return a normalized result."""
