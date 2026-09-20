"""Stop-loss calculation logic."""

from __future__ import annotations

from dataclasses import dataclass

from .sl_tp import SlTpInputs, StopLossResult


@dataclass(frozen=True)
class _StopCandidate:
    source: str
    stop_loss: float


def compute_stop_loss(inputs: SlTpInputs) -> StopLossResult:
    """Build structure-aware stop loss with explicit source priority."""

    is_long = inputs.side.lower() == "long"
    atr = max(float(inputs.atr or 0.0), 1e-9)
    entry = float(inputs.entry)
    debug: list[str] = []

    sl_mult = float(inputs.sl_atr_mult)
    sl_mult = max(inputs.min_sl_atr_mult, min(inputs.max_sl_atr_mult, sl_mult))

    if inputs.adx is not None:
        adxv = float(inputs.adx or 0.0)
        if adxv < 18:
            sl_mult = min(inputs.max_sl_atr_mult, sl_mult * 1.10)
            debug.append(f"ADX<18: widen SL mult -> {sl_mult:.2f}")
        elif adxv > 28:
            sl_mult = max(inputs.min_sl_atr_mult, sl_mult * 0.95)
            debug.append(f"ADX>28: tighten SL mult -> {sl_mult:.2f}")

    atr_fallback = _atr_stop_loss(entry=entry, atr=atr, sl_mult=sl_mult, is_long=is_long)
    debug.append(f"ATR fallback stop -> {atr_fallback:.2f}")
    structure_candidates = _build_structure_candidates(
        inputs=inputs,
        entry=entry,
        atr=atr,
        is_long=is_long,
        debug=debug,
    )
    chosen = structure_candidates[0] if structure_candidates else _StopCandidate(
        source="atr_fallback",
        stop_loss=atr_fallback,
    )
    debug.append(f"Selected stop source: {chosen.source} -> {chosen.stop_loss:.2f}")

    stop_loss = _apply_fee_buffer(
        stop_loss=chosen.stop_loss,
        fee_buffer_pct=inputs.fee_buffer_pct,
        is_long=is_long,
    )
    debug.append(f"Stop after fee buffer -> {stop_loss:.2f}")

    risk = max(abs(entry - stop_loss), 1e-9)
    return StopLossResult(
        stop_loss=float(stop_loss),
        risk=float(risk),
        source=chosen.source,
        debug=tuple(debug),
    )


def _atr_stop_loss(*, entry: float, atr: float, sl_mult: float, is_long: bool) -> float:
    if is_long:
        return entry - sl_mult * atr
    return entry + sl_mult * atr


def _build_structure_candidates(
    *,
    inputs: SlTpInputs,
    entry: float,
    atr: float,
    is_long: bool,
    debug: list[str],
) -> list[_StopCandidate]:
    candidates: list[_StopCandidate] = []
    level_priority = (
        ("swing", inputs.swing_low if is_long else inputs.swing_high, 0.20, 3.5),
        ("kijun", inputs.kijun, 0.18, 2.6),
        ("ema50", inputs.ema50, 0.15, 2.0),
    )
    for source, level, level_buffer_mult, max_distance_atr in level_priority:
        candidate = _structure_stop_candidate(
            source=source,
            level=level,
            entry=entry,
            atr=atr,
            is_long=is_long,
            level_buffer_mult=level_buffer_mult,
            max_distance_atr=max_distance_atr,
            debug=debug,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _structure_stop_candidate(
    *,
    source: str,
    level: float | None,
    entry: float,
    atr: float,
    is_long: bool,
    level_buffer_mult: float,
    max_distance_atr: float,
    debug: list[str],
) -> _StopCandidate | None:
    if level is None:
        return None

    numeric_level = float(level)
    if is_long and not (0 < numeric_level < entry):
        return None
    if (not is_long) and not (numeric_level > entry):
        return None

    distance = abs(entry - numeric_level)
    distance_atr = distance / atr if atr > 0 else 0.0
    if distance_atr > max_distance_atr:
        debug.append(f"Rejected {source}: {distance_atr:.2f} ATR away")
        return None

    offset = level_buffer_mult * atr
    stop_loss = numeric_level - offset if is_long else numeric_level + offset
    debug.append(f"Accepted {source}: level={numeric_level:.2f} stop={stop_loss:.2f} distance={distance_atr:.2f} ATR")
    return _StopCandidate(source=source, stop_loss=stop_loss)


def _apply_fee_buffer(*, stop_loss: float, fee_buffer_pct: float, is_long: bool) -> float:
    if is_long:
        return stop_loss * (1.0 - fee_buffer_pct)
    return stop_loss * (1.0 + fee_buffer_pct)
