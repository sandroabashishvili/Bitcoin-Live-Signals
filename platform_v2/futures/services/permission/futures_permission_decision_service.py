"""Futures entry permission checks aligned with spot-style policy."""

from __future__ import annotations

from dataclasses import dataclass

from platform_v2.futures.config import settings


@dataclass(frozen=True)
class FuturesPermissionDecision:
    allowed: bool
    reason: str
    checks: dict[str, bool]


class FuturesPermissionDecisionService:
    """Evaluate whether a directional signal may open a new futures position."""

    def __init__(
        self,
        *,
        min_required_balance: float = settings.MIN_REQUIRED_BALANCE,
        max_open_exposure: float = settings.MAX_OPEN_EXPOSURE,
        default_proximity_pct: float = settings.DEFAULT_PROXIMITY_PCT,
    ) -> None:
        self._min_required_balance = min_required_balance
        self._max_open_exposure = max_open_exposure
        self._default_proximity_pct = default_proximity_pct

    def evaluate(
        self,
        *,
        signal_side: str,
        entry_price: float,
        order_notional_usdt: float,
        available_balance: float,
        current_open_exposure: float,
        last_entry_price: float | None,
        stop_loss: float | None = None,
        leverage: int = settings.DEFAULT_LEVERAGE,
        manual_block: bool = False,
        cooldown_active: bool = False,
        duplicate_active: bool = False,
        entry_quality_ok: bool = True,
        entry_quality_reason: str = "entry_quality_block",
        long_entry_location_ok: bool = True,
        short_market_plan_ok: bool = True,
        current_open_positions: int = 0,
        current_direction_open_positions: int = 0,
        proximity_pct: float | None = None,
    ) -> FuturesPermissionDecision:
        signal_is_actionable = signal_side != "NO_SIGNAL"
        capital_ok = available_balance >= self._min_required_balance
        exposure_ok = (current_open_exposure + order_notional_usdt) <= self._max_open_exposure
        position_slots_ok = current_open_positions < settings.MAX_OPEN_POSITIONS
        direction_position_slots_ok = (
            current_direction_open_positions < settings.MAX_OPEN_POSITIONS_PER_DIRECTION
        )
        liquidation_buffer_ok = self._passes_liquidation_buffer(
            signal_side=signal_side,
            entry_price=entry_price,
            stop_loss=stop_loss,
            leverage=leverage,
        )
        duplicate_ok = not duplicate_active
        proximity_ok = self._passes_proximity(
            entry_price=entry_price,
            last_entry_price=last_entry_price,
            proximity_pct=(proximity_pct if proximity_pct is not None else self._default_proximity_pct),
        )
        cooldown_ok = not cooldown_active
        manual_ok = not manual_block

        checks = {
            "signal_is_actionable": signal_is_actionable,
            "manual_block": manual_ok,
            "capital": capital_ok,
            "exposure": exposure_ok,
            "position_slots": position_slots_ok,
            "direction_position_slots": direction_position_slots_ok,
            "liquidation_buffer": liquidation_buffer_ok,
            "duplicate": duplicate_ok,
            "cooldown": cooldown_ok,
            "proximity": proximity_ok,
            "entry_quality": entry_quality_ok,
            "long_entry_location": long_entry_location_ok,
            "short_market_plan_zone": short_market_plan_ok,
        }

        reason = self._pick_reason(
            signal_is_actionable=signal_is_actionable,
            manual_ok=manual_ok,
            capital_ok=capital_ok,
            exposure_ok=exposure_ok,
            position_slots_ok=position_slots_ok,
            direction_position_slots_ok=direction_position_slots_ok,
            liquidation_buffer_ok=liquidation_buffer_ok,
            duplicate_ok=duplicate_ok,
            cooldown_ok=cooldown_ok,
            proximity_ok=proximity_ok,
            entry_quality_ok=entry_quality_ok,
            entry_quality_reason=entry_quality_reason,
            long_entry_location_ok=long_entry_location_ok,
            short_market_plan_ok=short_market_plan_ok,
        )
        return FuturesPermissionDecision(allowed=reason == "allowed", reason=reason, checks=checks)

    @staticmethod
    def _passes_liquidation_buffer(
        *,
        signal_side: str,
        entry_price: float,
        stop_loss: float | None,
        leverage: int,
    ) -> bool:
        side = str(signal_side or "").upper()
        if side == "NO_SIGNAL":
            return True
        if side == "BUY":
            side = "LONG"
        elif side == "SELL":
            side = "SHORT"
        if side not in {"LONG", "SHORT"}:
            return True
        if entry_price <= 0 or stop_loss is None or stop_loss <= 0:
            return False
        effective_leverage = max(1, int(leverage or settings.DEFAULT_LEVERAGE))
        inverse_leverage = 1.0 / effective_leverage
        maintenance = settings.MAINTENANCE_MARGIN_PCT
        buffer_pct = settings.LIQUIDATION_BUFFER_PCT
        if side == "SHORT":
            liquidation_price = entry_price * (1.0 + inverse_leverage - maintenance)
            return stop_loss < (liquidation_price * (1.0 - buffer_pct))
        liquidation_price = entry_price * (1.0 - inverse_leverage + maintenance)
        return stop_loss > (liquidation_price * (1.0 + buffer_pct))

    @staticmethod
    def _passes_proximity(*, entry_price: float, last_entry_price: float | None, proximity_pct: float) -> bool:
        if last_entry_price is None or last_entry_price <= 0 or entry_price <= 0:
            return True
        distance_pct = abs(entry_price - last_entry_price) / last_entry_price * 100.0
        return distance_pct > proximity_pct

    @staticmethod
    def _pick_reason(
        *,
        signal_is_actionable: bool,
        manual_ok: bool,
        capital_ok: bool,
        exposure_ok: bool,
        position_slots_ok: bool,
        direction_position_slots_ok: bool,
        liquidation_buffer_ok: bool,
        duplicate_ok: bool,
        cooldown_ok: bool,
        proximity_ok: bool,
        entry_quality_ok: bool,
        entry_quality_reason: str,
        long_entry_location_ok: bool,
        short_market_plan_ok: bool,
    ) -> str:
        if not signal_is_actionable:
            return "signal_block"
        if not manual_ok:
            return "manual_block"
        if not capital_ok:
            return "capital_block"
        if not exposure_ok:
            return "exposure_block"
        if not position_slots_ok:
            return "position_slots_block"
        if not direction_position_slots_ok:
            return "direction_position_slots_block"
        if not liquidation_buffer_ok:
            return "liquidation_buffer_block"
        if not entry_quality_ok:
            return str(entry_quality_reason or "entry_quality_block")
        if not long_entry_location_ok:
            return "long_entry_location_block"
        if not short_market_plan_ok:
            return "short_market_plan_zone_block"
        if not duplicate_ok:
            return "duplicate_block"
        if not cooldown_ok:
            return "cooldown_block"
        if not proximity_ok:
            return "proximity_block"
        return "allowed"
