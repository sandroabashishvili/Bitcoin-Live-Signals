"""File: position_runtime_service.py
Folder: platform_v2/spot/services
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Build and persist opened position records for V2 runtime flow.
"""

from __future__ import annotations

from datetime import datetime, timezone

from platform_v2.spot.config import settings
from platform_v2.spot.domain.models.market_context import MarketContext
from platform_v2.spot.domain.models.position import PositionRecord, PositionStatus
from platform_v2.spot.domain.models.signal import SignalDecision
from platform_v2.shared.backend.runtime_store.spot import POSITIONS_FAMILY, load_family_rows_all
from platform_v2.spot.services.trading.execution_setup_service import ExecutionSetupService
from platform_v2.spot.services.ops.runtime_write_service import write_position_record
from platform_v2.spot.services.account.profit_lock import build_profit_lock


POSITION_ID_PREFIX = "SPOT"


class PositionRuntimeService:
    """Create and persist opened position records from allowed signals."""

    def __init__(self, execution_setup_service: ExecutionSetupService | None = None) -> None:
        """Initialize execution setup dependency."""

        self._execution_setup_service = execution_setup_service or ExecutionSetupService()

    def build_and_persist(
        self,
        *,
        date_iso: str,
        signal: SignalDecision,
        live_entry_price: float,
        market_context: MarketContext | None = None,
        position_size: float = settings.DEFAULT_POSITION_SIZE,
        opened_at: str | None = None,
        opened_at_ms: int | None = None,
        signal_candle_close_time: str | None = None,
        decision_time: str | None = None,
        signal_reference_price: float | None = None,
        execution_quote_source: str | None = None,
    ) -> PositionRecord:
        """Build and persist one opened position record."""

        if opened_at is None:
            opened_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        execution_setup = self._execution_setup_service.build_setup(
            signal,
            live_entry_price=live_entry_price,
            position_size=position_size,
            market_context=market_context,
        )
        position = PositionRecord(
            position_id=self._next_position_id(),
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            side=signal.side,
            status=PositionStatus.OPEN,
            execution=execution_setup,
            opened_at=opened_at,
            opened_at_ms=opened_at_ms,
            signal_candle_close_time=signal_candle_close_time,
            decision_time=decision_time,
            signal_reference_price=signal_reference_price,
            execution_quote_source=execution_quote_source,
            unrealized_pnl=0.0,
            strategy_version=signal.strategy_version,
            source_market=signal.source_market,
            source_strategy_version=signal.source_strategy_version,
            position_management=(build_profit_lock(execution_setup)
                                 if signal.profit_lock_enabled else None),
        )
        write_position_record(date_iso=date_iso, position=position)
        return position

    @staticmethod
    def _next_position_id() -> str:
        """Return the next human-readable Spot position identifier."""

        rows = load_family_rows_all(POSITIONS_FAMILY)
        seen_ids = {
            str(row.get("position_id") or "").strip()
            for row in rows
            if str(row.get("position_id") or "").strip()
        }
        prefix = f"{POSITION_ID_PREFIX}-"
        prefixed_numbers: list[int] = []
        for position_id in seen_ids:
            if not position_id.startswith(prefix):
                continue
            suffix = position_id[len(prefix) :]
            if suffix.isdigit():
                prefixed_numbers.append(int(suffix))
        if prefixed_numbers:
            next_number = max(prefixed_numbers) + 1
        else:
            next_number = len(seen_ids) + 1
        return f"{POSITION_ID_PREFIX}-{next_number:06d}"
