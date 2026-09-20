"""File: signal_runtime_service.py
Folder: platform_v2/spot/services
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Orchestrate market context, signal building, and runtime persistence.
"""

from __future__ import annotations

from dataclasses import dataclass

from platform_v2.spot.config import settings
from platform_v2.spot.domain.models.market_context import MarketContext
from platform_v2.spot.domain.models.signal import SignalDecision
from platform_v2.spot.services.market.market_context_service import MarketContextService
from platform_v2.spot.services.ops.runtime_write_service import write_signal_record
from platform_v2.spot.services.signal.independent_long_signal_service import IndependentLongSignalService
from platform_v2.shared.backend.runtime_store.spot import SIGNALS_FAMILY, load_family_rows_all


@dataclass(frozen=True)
class SignalRuntimeResult:
    """Bundle the built market context and signal decision for one cycle."""

    context: MarketContext
    signal: SignalDecision


class SignalRuntimeService:
    """Run the minimal V2 signal pipeline for one symbol and timeframe."""

    def __init__(
        self,
        market_context_service: MarketContextService | None = None,
        signal_decision_service: IndependentLongSignalService | None = None,
    ) -> None:
        """Initialize runtime dependencies."""

        self._market_context_service = market_context_service or MarketContextService()
        self._signal_decision_service = signal_decision_service or IndependentLongSignalService()

    def run_for_symbol(
        self,
        symbol: str,
        timeframe: str,
        date_iso: str,
        candle_limit: int = settings.DEFAULT_CANDLE_LIMIT,
    ) -> SignalDecision | None:
        """Build and persist a signal decision for one symbol and timeframe."""

        result = self.run_with_context(
            symbol=symbol,
            timeframe=timeframe,
            date_iso=date_iso,
            candle_limit=candle_limit,
        )
        return result.signal if result is not None else None

    def run_with_context(
        self,
        symbol: str,
        timeframe: str,
        date_iso: str,
        candle_limit: int = settings.DEFAULT_CANDLE_LIMIT,
    ) -> SignalRuntimeResult | None:
        """Build market context, persist the signal, and return both."""

        context = self._market_context_service.build_context(
            symbol=symbol,
            timeframe=timeframe,
            candle_limit=candle_limit,
        )
        if context is None:
            return None

        prior = [row for row in load_family_rows_all(SIGNALS_FAMILY)
                 if row.get('symbol') == symbol and row.get('timeframe') == timeframe
                 and row.get('strategy_version') == settings.STRATEGY_VERSION
                 and int(row.get('timestamp_ms') or 0) < context.latest_candle.close_time_ms]
        decision = self._signal_decision_service.build_signal(context, prior_signals=prior)
        write_signal_record(date_iso=date_iso, signal=decision)
        return SignalRuntimeResult(context=context, signal=decision)
