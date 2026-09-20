"""Research-only, restartable closed-bar trailing exits for either direction.

No production imports. Callers supply only indicators known by the bar close.
Levels calculated on this bar cannot trigger until the next bar.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class TrailingPolicy:
    atr_multiple: float = 2.0
    activation_r: float = 1.0
    extend_target: bool = False
    max_extension_fraction: float = 0.5


def new_state(*, side: str, entry: float, stop: float, target: float) -> dict:
    direction = {"LONG": 1, "SHORT": -1}[side]
    if not (entry > 0 and stop > 0 and target > 0
            and direction * (entry-stop) > 0 and direction * (target-entry) > 0):
        raise ValueError("Invalid directional exit levels")
    return dict(side=side, entry=entry, original_stop=stop, original_target=target,
                stop=stop, target=target, extreme=entry, active=False,
                last_close_ms=None, last_target_signal_ms=None, exit=None)


def advance(state: dict, bar: dict, *, atr: float | None,
            policy: TrailingPolicy, signal_close_ms: int | None = None,
            direction_score: float | None = None, threshold: float = 8.5) -> dict | None:
    if policy.atr_multiple <= 0 or policy.activation_r <= 0 or policy.max_extension_fraction < 0:
        raise ValueError("Invalid trailing policy")
    close_ms = int(bar['close_time'])
    if state['exit'] is not None:
        return state['exit']
    last = state['last_close_ms']
    if last is not None and close_ms <= last:
        return None
    if last is not None and close_ms != last + 60000:
        raise ValueError("Missing monitoring candles")
    if signal_close_ms is not None and signal_close_ms > close_ms:
        raise ValueError("Future signal supplied")
    d = 1 if state['side'] == 'LONG' else -1
    stop, target = state['stop'], state['target']
    lo, hi, op = float(bar['low']), float(bar['high']), float(bar['open'])
    stop_hit = lo <= stop if d == 1 else hi >= stop
    target_hit = hi >= target if d == 1 else lo <= target
    state['last_close_ms'] = close_ms
    if stop_hit or target_hit:
        # Stop-market gaps worsen fills; targets do not receive price improvement.
        price = (min(stop, op) if d == 1 else max(stop, op)) if stop_hit else target
        outcome = 'TRAIL_STOP' if stop_hit and state['active'] else 'SL' if stop_hit else 'TP'
        state['exit'] = dict(timestamp_ms=close_ms, price=price, outcome=outcome,
                             ambiguous=stop_hit and target_hit)
        return state['exit']
    state['extreme'] = max(state['extreme'], hi) if d == 1 else min(state['extreme'], lo)
    risk = abs(state['entry']-state['original_stop'])
    progress = d*(state['extreme']-state['entry'])
    if progress >= policy.activation_r*risk and atr is not None and atr > 0:
        state['active'] = True
        proposed = state['extreme']-d*policy.atr_multiple*atr
        state['stop'] = max(stop, proposed) if d == 1 else min(stop, proposed)
        # Only closed 15m signal observations can extend the target, once each.
        if (policy.extend_target and signal_close_ms is not None
                and (signal_close_ms+1) % 900000 == 0
                and signal_close_ms == close_ms
                and state['last_target_signal_ms'] != signal_close_ms
                and direction_score is not None and direction_score >= threshold):
            reward = abs(state['original_target']-state['entry'])
            extension = min(policy.max_extension_fraction*reward,
                            max(0.0, progress-policy.activation_r*risk))
            proposed_target = state['original_target']+d*extension
            state['target'] = max(target, proposed_target) if d == 1 else min(target, proposed_target)
            state['last_target_signal_ms'] = signal_close_ms
    return None
