"""Central fee policy helpers for deterministic paper trading."""

from __future__ import annotations

from collections.abc import Iterable

from platform_v2.spot.config import settings
from platform_v2.spot.domain.models.position import PositionRecord


class FeeService:
    """Single source of truth for entry/exit fee calculations."""

    @staticmethod
    def entry_fee_for_notional(notional: float) -> float:
        return max(0.0, float(notional or 0.0)) * settings.ENTRY_FEE_PCT

    @staticmethod
    def exit_fee_for_notional(notional: float) -> float:
        return max(0.0, float(notional or 0.0)) * settings.EXIT_FEE_PCT

    @classmethod
    def total_round_trip_fees_for_notional(cls, notional: float) -> float:
        return cls.entry_fee_for_notional(notional) + cls.exit_fee_for_notional(notional)

    @classmethod
    def net_pnl_from_gross(cls, *, notional: float, gross_pnl: float) -> float:
        return float(gross_pnl or 0.0) - cls.total_round_trip_fees_for_notional(notional)

    @classmethod
    def open_entry_fees_total(cls, positions: Iterable[PositionRecord]) -> float:
        return sum(cls.entry_fee_for_notional(position.execution.position_size) for position in positions)

    @staticmethod
    def gross_pnl_value(position: PositionRecord) -> float:
        value = position.pnl if position.pnl is not None else position.net_pnl
        return float(value or 0.0)

    @staticmethod
    def net_pnl_value(position: PositionRecord) -> float:
        value = position.net_pnl if position.net_pnl is not None else position.pnl
        return float(value or 0.0)

    @classmethod
    def realized_fees_for_position(cls, position: PositionRecord) -> float:
        return cls.gross_pnl_value(position) - cls.net_pnl_value(position)

    @classmethod
    def realized_fees_total(cls, positions: Iterable[PositionRecord]) -> float:
        return sum(cls.realized_fees_for_position(position) for position in positions)
