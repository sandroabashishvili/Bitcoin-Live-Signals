"""Direction-normalized indicator features attached to replayed entries."""

from __future__ import annotations

from typing import Any


def entry_features(*, snapshot: Any, side: str) -> dict[str, float | None]:
    is_long = str(side).upper() in {"BUY", "LONG"}
    price = _number(getattr(snapshot, "price", None))
    atr = _number(getattr(snapshot, "atr", None))
    macd = _number(getattr(snapshot, "macd", None))
    macd_signal = _number(getattr(snapshot, "macd_signal", None))
    plus_di = _number(getattr(snapshot, "plus_di", None))
    minus_di = _number(getattr(snapshot, "minus_di", None))
    swing_high = _number(getattr(snapshot, "swing_high", None))
    swing_low = _number(getattr(snapshot, "swing_low", None))
    resistance = _number(getattr(snapshot, "resistance_level", None))
    liquidity = _number(getattr(snapshot, "liquidity_zone", None))
    directional_di = _delta(plus_di, minus_di, is_long=is_long)
    directional_macd = _delta(macd, macd_signal, is_long=is_long)
    if is_long:
        entry_from_swing = _distance(price, swing_low, atr)
        room_to_swing = _distance(swing_high, price, atr)
        room_to_nearest_structure = _nearest_positive_distance(
            price=price,
            levels=(swing_high, resistance, liquidity),
            atr=atr,
            is_long=True,
        )
    else:
        entry_from_swing = _distance(swing_high, price, atr)
        room_to_swing = _distance(price, swing_low, atr)
        room_to_nearest_structure = _nearest_positive_distance(
            price=price,
            levels=(swing_low, liquidity),
            atr=atr,
            is_long=False,
        )
    return {
        "rsi": _number(getattr(snapshot, "rsi", None)),
        "adx": _number(getattr(snapshot, "adx", None)),
        "atr_growth_20": _number(getattr(snapshot, "atr_growth_20", None)),
        "directional_di_delta": directional_di,
        "directional_macd_spread_atr": (
            directional_macd / atr
            if directional_macd is not None and atr is not None and atr > 0
            else None
        ),
        "entry_from_swing_atr": entry_from_swing,
        "room_to_opposite_swing_atr": room_to_swing,
        "room_to_nearest_structure_atr": room_to_nearest_structure,
    }


def exit_geometry_features(
    *,
    entry: float,
    stop_loss: float,
    take_profit: float,
    atr: float | None,
) -> dict[str, float | None]:
    """Return direction-neutral SL/TP distances and effective reward-to-risk."""

    risk = abs(float(entry) - float(stop_loss))
    reward = abs(float(take_profit) - float(entry))
    numeric_atr = _number(atr)
    return {
        "stop_distance_atr": (
            risk / numeric_atr if numeric_atr is not None and numeric_atr > 0 else None
        ),
        "target_distance_atr": (
            reward / numeric_atr if numeric_atr is not None and numeric_atr > 0 else None
        ),
        "effective_rr": reward / risk if risk > 0 else None,
    }


def _distance(first: float | None, second: float | None, atr: float | None) -> float | None:
    if first is None or second is None or atr is None or atr <= 0:
        return None
    return (first - second) / atr


def _nearest_positive_distance(
    *,
    price: float | None,
    levels: tuple[float | None, ...],
    atr: float | None,
    is_long: bool,
) -> float | None:
    if price is None or atr is None or atr <= 0:
        return None
    distances = [
        ((level - price) if is_long else (price - level)) / atr
        for level in levels
        if level is not None and ((level > price) if is_long else (level < price))
    ]
    return min(distances) if distances else None


def _delta(first: float | None, second: float | None, *, is_long: bool) -> float | None:
    if first is None or second is None:
        return None
    return first - second if is_long else second - first


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
