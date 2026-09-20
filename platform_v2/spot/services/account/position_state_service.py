"""File: position_state_service.py
Folder: platform_v2/spot/services
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Read current position state from runtime position records.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from platform_v2.spot.config import settings
from platform_v2.spot.domain.models.position import ExecutionSetup, ExitReason, PositionRecord, PositionStatus
from platform_v2.spot.domain.models.signal import SignalSide
from platform_v2.shared.backend.runtime_store.spot import POSITIONS_FAMILY, load_family_documents


class PositionStateService:
    """Load the latest known state for runtime positions."""

    def load_latest_positions(
        self,
        *,
        lookback_days: int | None = settings.DEFAULT_LOOKBACK_DAYS,
        as_of_date_iso: str | None = None,
    ) -> list[PositionRecord]:
        """Return the latest known state for every seen position id."""

        if as_of_date_iso is None:
            as_of_date = datetime.now(tz=timezone.utc).date()
        else:
            as_of_date = datetime.strptime(as_of_date_iso, "%Y-%m-%d").date()

        earliest_date = (as_of_date - timedelta(days=lookback_days - 1)) if lookback_days else None
        latest_by_id: dict[str, PositionRecord] = {}
        for date_iso, rows in load_family_documents(POSITIONS_FAMILY):
            try:
                document_date = datetime.strptime(date_iso, "%Y-%m-%d").date()
            except ValueError:
                continue
            if document_date > as_of_date or (earliest_date is not None and document_date < earliest_date):
                continue
            if not isinstance(rows, list):
                continue
            for row in rows:
                position = self._parse_position_row(row)
                if position is None:
                    continue
                latest_by_id[position.position_id] = position

        return list(latest_by_id.values())

    def load_open_positions(
        self,
        *,
        lookback_days: int | None = settings.DEFAULT_LOOKBACK_DAYS,
        as_of_date_iso: str | None = None,
    ) -> list[PositionRecord]:
        """Return the current open positions after latest-state deduplication."""

        positions = self.load_latest_positions(
            lookback_days=lookback_days,
            as_of_date_iso=as_of_date_iso,
        )
        return [position for position in positions if position.is_open]

    @staticmethod
    def _parse_position_row(row: object) -> PositionRecord | None:
        """Parse one runtime position row into a normalized PositionRecord."""

        if not isinstance(row, dict):
            return None

        execution = row.get("execution")
        if not isinstance(execution, dict):
            return None

        try:
            return PositionRecord(
                position_id=PositionStateService._string_value(row, "position_id"),
                symbol=PositionStateService._string_value(row, "symbol"),
                timeframe=PositionStateService._string_value(row, "timeframe"),
                side=SignalSide(PositionStateService._enum_value(row, "side", SignalSide.BUY.value)),
                status=PositionStatus(
                    PositionStateService._enum_value(row, "status", PositionStatus.OPEN.value)
                ),
                execution=PositionStateService._parse_execution(execution),
                opened_at=PositionStateService._string_value(row, "opened_at"),
                opened_at_ms=PositionStateService._optional_int(row, "opened_at_ms"),
                signal_candle_close_time=PositionStateService._optional_string(
                    row, "signal_candle_close_time"
                ),
                decision_time=PositionStateService._optional_string(row, "decision_time"),
                signal_reference_price=PositionStateService._optional_float(
                    row, "signal_reference_price"
                ),
                execution_quote_source=PositionStateService._optional_string(
                    row, "execution_quote_source"
                ),
                closed_at=PositionStateService._optional_string(row, "closed_at"),
                exit_price=PositionStateService._optional_float(row, "exit_price"),
                exit_reason=ExitReason(
                    PositionStateService._enum_value(
                        row,
                        "exit_reason",
                        ExitReason.UNKNOWN.value,
                    )
                ),
                pnl=PositionStateService._optional_float(row, "pnl"),
                net_pnl=PositionStateService._optional_float(row, "net_pnl"),
                unrealized_pnl=PositionStateService._optional_float(row, "unrealized_pnl"),
                was_force_closed=bool(row.get("was_force_closed", False)),
                force_close_reason=PositionStateService._optional_string(row, "force_close_reason"),
                exit_check_timeframe=PositionStateService._optional_string(
                    row,
                    "exit_check_timeframe",
                ),
                exit_trigger_candle_close_ms=PositionStateService._optional_int(
                    row,
                    "exit_trigger_candle_close_ms",
                ),
                exit_trigger_price=PositionStateService._optional_float(row, "exit_trigger_price"),
                exit_trigger_type=PositionStateService._optional_string(row, "exit_trigger_type"),
                strategy_version=str(row.get("strategy_version") or "unknown"),
                source_market=str(row.get("source_market") or "spot"),
                source_strategy_version=PositionStateService._optional_string(row, "source_strategy_version"),
                position_management=(dict(row["position_management"])
                                     if isinstance(row.get("position_management"), dict) else None),
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_execution(execution: dict[object, object]) -> ExecutionSetup:
        return ExecutionSetup(
            entry_price=PositionStateService._float_from_mapping(execution, "entry_price"),
            stop_loss=PositionStateService._float_from_mapping(execution, "stop_loss"),
            take_profit=PositionStateService._float_from_mapping(execution, "take_profit"),
            rr_ratio=PositionStateService._float_from_mapping(execution, "rr_ratio"),
            position_size=PositionStateService._float_from_mapping(execution, "position_size"),
            mode=str(execution.get("mode") or "unknown"),
        )

    @staticmethod
    def _float_from_mapping(mapping: dict[object, object], key: str) -> float:
        return PositionStateService._coerce_float(mapping.get(key, 0.0))

    @staticmethod
    def _optional_float(mapping: dict[object, object], key: str) -> float | None:
        value = mapping.get(key)
        if value is None:
            return None
        return PositionStateService._coerce_float(value)

    @staticmethod
    def _coerce_float(value: Any) -> float:
        return float(value or 0.0)

    @staticmethod
    def _optional_int(mapping: dict[object, object], key: str) -> int | None:
        value: Any = mapping.get(key)
        if value is None:
            return None
        return int(value)

    @staticmethod
    def _string_value(mapping: dict[object, object], key: str) -> str:
        return str(mapping.get(key) or "")

    @staticmethod
    def _optional_string(mapping: dict[object, object], key: str) -> str | None:
        value = mapping.get(key)
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _enum_value(mapping: dict[object, object], key: str, default: str) -> str:
        return str(mapping.get(key) or default)
