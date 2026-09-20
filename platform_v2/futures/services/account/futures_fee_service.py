"""Fee helpers for futures simulation."""

from __future__ import annotations

from platform_v2.futures.config import settings


class FuturesFeeService:
    """Compute futures entry/exit and round-trip fees from notional size."""

    MAKER = "MAKER"
    TAKER = "TAKER"

    @classmethod
    def fee_rate_for_role(cls, role: str) -> float:
        normalized = str(role or "").upper()
        if normalized == cls.MAKER:
            return settings.MAKER_FEE_PCT
        return settings.TAKER_FEE_PCT

    @classmethod
    def fee_for_notional(cls, *, notional: float, role: str) -> float:
        return max(0.0, float(notional or 0.0)) * cls.fee_rate_for_role(role)

    @staticmethod
    def entry_fee_for_notional(notional: float) -> float:
        return max(0.0, float(notional or 0.0)) * settings.ENTRY_FEE_PCT

    @staticmethod
    def exit_fee_for_notional(notional: float) -> float:
        return max(0.0, float(notional or 0.0)) * settings.EXIT_FEE_PCT

    @classmethod
    def exit_fee_for_notional_and_reason(cls, *, notional: float, exit_reason: str) -> float:
        return cls.fee_for_notional(
            notional=notional,
            role=cls.exit_fee_role_for_reason(exit_reason),
        )

    @classmethod
    def exit_fee_role_for_reason(cls, exit_reason: str) -> str:
        normalized = str(exit_reason or "").upper()
        if normalized in {
            "TP_HIT", "SL_HIT", "PROFIT_LOCK_HIT", "TP", "SL", "TAKE_PROFIT", "STOP_LOSS"
        }:
            return cls.MAKER
        return cls.TAKER

    @classmethod
    def total_round_trip_fees_for_notional(cls, notional: float) -> float:
        return cls.entry_fee_for_notional(notional) + cls.exit_fee_for_notional(notional)

    @classmethod
    def total_round_trip_fees_for_exit_reason(cls, *, notional: float, exit_reason: str) -> float:
        return cls.entry_fee_for_notional(notional) + cls.exit_fee_for_notional_and_reason(
            notional=notional,
            exit_reason=exit_reason,
        )

    @classmethod
    def net_pnl_from_gross(cls, *, notional: float, gross_pnl: float) -> float:
        return float(gross_pnl or 0.0) - cls.total_round_trip_fees_for_notional(notional)

    @classmethod
    def net_pnl_from_gross_for_exit_reason(
        cls,
        *,
        notional: float,
        gross_pnl: float,
        exit_reason: str,
    ) -> float:
        return float(gross_pnl or 0.0) - cls.total_round_trip_fees_for_exit_reason(
            notional=notional,
            exit_reason=exit_reason,
        )
