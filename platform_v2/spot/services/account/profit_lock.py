"""Durable Spot implementation of the tested LONG 70/25 protection policy."""

from dataclasses import replace

from platform_v2.spot.domain.models.position import ExitReason, PositionStatus
from platform_v2.spot.services.account.fee_service import FeeService

POLICY = "long_profit_lock_70_25"


def build_profit_lock(setup):
    entry, target = setup.entry_price, setup.take_profit
    activation = round(entry + .70*(target-entry), 2)
    protected = round(entry + .25*(target-entry), 2)
    if not 0 < setup.stop_loss < entry < protected < activation < target:
        return None
    return {'policy': POLICY, 'activation_price': activation, 'protected_stop': protected,
            'protection_active': False, 'last_candle_close_ms': 0}


def update_managed_position(position, candles):
    management = dict(position.position_management)
    last = int(management.get('last_candle_close_ms') or 0)
    active = bool(management.get('protection_active', False))
    e = position.execution
    for candle in candles:
        if position.opened_at_ms is not None and candle.open_time_ms < position.opened_at_ms:
            continue
        if candle.close_time_ms <= last:
            continue
        stop = management['protected_stop'] if active else e.stop_loss
        exit_price = reason = None
        if candle.low_price <= stop:
            exit_price = stop
            reason = ExitReason.PROFIT_LOCK_HIT if active else ExitReason.SL_HIT
        elif candle.high_price >= e.take_profit:
            exit_price, reason = e.take_profit, ExitReason.TP_HIT
        management['last_candle_close_ms'] = candle.close_time_ms
        if reason is not None:
            gross = (exit_price-e.entry_price)*e.position_size/e.entry_price
            return replace(position, status=PositionStatus.CLOSED,
                closed_at=str(candle.close_time_ms), exit_price=exit_price, exit_reason=reason,
                pnl=gross, net_pnl=FeeService.net_pnl_from_gross(notional=e.position_size, gross_pnl=gross),
                unrealized_pnl=0., exit_check_timeframe=candle.timeframe,
                exit_trigger_candle_close_ms=candle.close_time_ms,
                exit_trigger_price=exit_price, exit_trigger_type=reason.value,
                position_management=management)
        if candle.high_price >= management['activation_price']:
            active = True
        management['protection_active'] = active
        position = replace(position, position_management=dict(management),
                           unrealized_pnl=(candle.close_price-e.entry_price)*e.position_size/e.entry_price)
    return position
