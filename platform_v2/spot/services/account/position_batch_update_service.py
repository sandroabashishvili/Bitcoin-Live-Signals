"""File: position_batch_update_service.py
Folder: platform_v2/spot/services
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Update all currently open positions against the latest closed candle.
"""

from __future__ import annotations

from datetime import UTC, datetime

from platform_v2.spot.config import settings
from platform_v2.spot.domain.models.force_close import ForceCloseEvent
from platform_v2.spot.domain.models.position import PositionRecord
from platform_v2.spot.infrastructure.market_data.candle_repository import CandleRepository, JsonCandleRepository
from platform_v2.spot.services.account.position_state_service import PositionStateService
from platform_v2.spot.services.account.position_update_service import PositionUpdateService
from platform_v2.spot.services.ops.runtime_write_service import (
    write_force_close_record,
    write_position_record,
)


class PositionBatchUpdateService:
    """Refresh all currently open positions from latest closed candles."""

    def __init__(
        self,
        candle_repository: CandleRepository | None = None,
        position_state_service: PositionStateService | None = None,
        position_update_service: PositionUpdateService | None = None,
    ) -> None:
        """Initialize batch update dependencies."""

        self._candle_repository = candle_repository or JsonCandleRepository()
        self._position_state_service = position_state_service or PositionStateService()
        self._position_update_service = position_update_service or PositionUpdateService()
        self._exit_monitoring_timeframe = settings.EXIT_MONITORING_TIMEFRAME

    def run(
        self,
        *,
        date_iso: str,
        lookback_days: int | None = settings.DEFAULT_LOOKBACK_DAYS,
    ) -> list[PositionRecord]:
        """Update all currently open positions and persist changed states."""

        updated_positions: list[PositionRecord] = []
        open_positions = self._position_state_service.load_open_positions(
            lookback_days=lookback_days,
            as_of_date_iso=date_iso,
        )

        for position in open_positions:
            candles = self._candle_repository.get_closed_candles(
                symbol=position.symbol,
                timeframe=self._exit_monitoring_timeframe,
            )
            relevant_candles = self._candles_after_position_open(position, candles)
            if not relevant_candles:
                continue

            updated = self._position_update_service.update_from_candles(position, relevant_candles)
            if updated != position:
                write_position_record(date_iso=date_iso, position=updated)
                updated_positions.append(updated)

        forced_positions = self._apply_minus_rule_force_closes(
            date_iso=date_iso,
            original_open_positions=open_positions,
            already_updated_positions=updated_positions,
        )
        updated_positions.extend(forced_positions)
        return updated_positions

    def _apply_minus_rule_force_closes(
        self,
        *,
        date_iso: str,
        original_open_positions: list[PositionRecord],
        already_updated_positions: list[PositionRecord],
    ) -> list[PositionRecord]:
        """Force-close profitable peer positions when minus-rule is triggered."""

        if not settings.PEER_FORCE_CLOSE_ENABLED:
            return []

        latest_by_id: dict[str, PositionRecord] = {
            position.position_id: position for position in original_open_positions
        }
        for position in already_updated_positions:
            latest_by_id[position.position_id] = position

        current_open_positions = [
            position for position in latest_by_id.values() if position.is_open
        ]
        if not current_open_positions:
            return []

        latest_candle = self._latest_closed_candle_for_positions(current_open_positions)
        if latest_candle is None:
            return []

        trigger_position = next(
            (
                position
                for position in current_open_positions
                if self._position_unrealized_pct(position) <= settings.WEAK_OPEN_POSITION_PCT
            ),
            None,
        )
        if trigger_position is None:
            return []

        forced_positions: list[PositionRecord] = []
        closed_at = str(latest_candle.close_time_ms)
        close_price = latest_candle.close_price
        trigger_unrealized_pnl = float(trigger_position.unrealized_pnl or 0.0)
        trigger_unrealized_pct = self._position_unrealized_pct(trigger_position)

        for position in current_open_positions:
            if position.position_id == trigger_position.position_id:
                continue
            if float(position.unrealized_pnl or 0.0) <= 0.0:
                continue

            forced = self._position_update_service.force_close(
                position,
                close_price=close_price,
                closed_at=closed_at,
                reason_text="minus_rule",
            )
            write_position_record(date_iso=date_iso, position=forced)
            write_force_close_record(
                date_iso=date_iso,
                force_close_event=ForceCloseEvent(
                    timestamp=closed_at,
                    reason="minus_rule",
                    trigger_position_id=trigger_position.position_id,
                    trigger_unrealized_pnl=trigger_unrealized_pnl,
                    trigger_unrealized_pct=trigger_unrealized_pct,
                    closed_position_id=forced.position_id,
                    symbol=forced.symbol,
                    timeframe=forced.timeframe,
                    closed_entry_price=forced.execution.entry_price,
                    closed_exit_price=float(forced.exit_price or close_price),
                    closed_net_pnl=float(forced.net_pnl or forced.pnl or 0.0),
                ),
            )
            forced_positions.append(forced)

        return forced_positions

    def _latest_closed_candle_for_positions(
        self,
        positions: list[PositionRecord],
    ):
        latest_candle = None
        for position in positions:
            candles = self._candle_repository.get_closed_candles(
                symbol=position.symbol,
                timeframe=self._exit_monitoring_timeframe,
            )
            relevant_candles = self._candles_after_position_open(position, candles)
            if not relevant_candles:
                continue
            candle = relevant_candles[-1]
            if latest_candle is None or candle.close_time_ms > latest_candle.close_time_ms:
                latest_candle = candle
        return latest_candle

    def _candles_after_position_open(
        self,
        position: PositionRecord,
        candles: list,
    ) -> list:
        opened_at_ms = position.opened_at_ms or self._timestamp_to_ms(position.opened_at)
        # Do not evaluate the high/low of a candle that began before the entry;
        # that range includes price action the position never experienced.
        return [candle for candle in candles if candle.open_time_ms >= opened_at_ms]

    @staticmethod
    def _timestamp_to_ms(value: str) -> int:
        text = str(value).strip()
        if text.isdigit():
            return int(text)
        try:
            dt = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        except ValueError:
            return 0
        return int(dt.timestamp() * 1000) + 999

    @staticmethod
    def _position_unrealized_pct(position: PositionRecord) -> float:
        notional = position.execution.position_size
        unrealized = float(position.unrealized_pnl or 0.0)
        if notional <= 0:
            return 0.0
        return unrealized / notional
