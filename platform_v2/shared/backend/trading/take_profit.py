"""Take-profit calculation logic."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .sl_tp import SlTpInputs, TakeProfitResult


def compute_take_profit(inputs: SlTpInputs, *, risk: float) -> TakeProfitResult:
    """Build adaptive take profit with explicit clamp priority."""

    is_long = inputs.side.lower() == "long"
    entry = float(inputs.entry)
    atr = max(float(inputs.atr or 0.0), 1e-9)
    debug: list[str] = []

    conf, rrr = _resolve_rrr(inputs)
    debug.append(f"RRR from confidence={conf:.2f} -> {rrr:.2f}")
    base_take_profit = _base_take_profit(entry=entry, risk=risk, rrr=rrr, is_long=is_long)
    debug.append(f"Base TP from risk -> {base_take_profit:.2f}")
    take_profit = base_take_profit
    source = "base_rrr"

    for candidate in _clamp_candidates(inputs=inputs, entry=entry, current_take_profit=take_profit, is_long=is_long):
        clamped = _clamp_to_level(
            level=candidate.level,
            label=candidate.label,
            entry=entry,
            take_profit=take_profit,
            risk=risk,
            atr=atr,
            level_buffer_atr=inputs.level_buffer_atr,
            is_long=is_long,
            min_effective_rrr_after_clamp=inputs.min_effective_rrr_after_clamp,
            debug=debug,
        )
        if clamped is not None:
            take_profit = clamped
            source = candidate.label
            break

    expanded = _expand_too_close_target(
        take_profit=take_profit,
        entry=entry,
        atr=atr,
        rrr=rrr,
        risk=risk,
        is_long=is_long,
    )
    if expanded != take_profit:
        take_profit = expanded
        source = "expanded_rrr"
        debug.append("TP too close -> expanded")

    return TakeProfitResult(
        take_profit=float(take_profit),
        rr_ratio=float(_effective_rrr(entry=entry, take_profit=take_profit, risk=risk, is_long=is_long)),
        source=source,
        debug=tuple(debug),
    )


@dataclass(frozen=True)
class _ClampCandidate:
    label: str
    level: float


def _resolve_rrr(inputs: SlTpInputs) -> tuple[float, float]:
    conf = 0.55 if inputs.confidence is None else float(inputs.confidence)
    conf = max(0.0, min(1.0, conf))
    rrr = inputs.min_rrr + (inputs.max_rrr - inputs.min_rrr) * conf
    return conf, max(inputs.min_rrr, min(inputs.max_rrr, rrr))


def _base_take_profit(*, entry: float, risk: float, rrr: float, is_long: bool) -> float:
    return entry + (rrr * risk) if is_long else entry - (rrr * risk)


def _effective_rrr(*, entry: float, take_profit: float, risk: float, is_long: bool) -> float:
    reward = (take_profit - entry) if is_long else (entry - take_profit)
    return reward / risk if risk > 0 else 0.0


def _clamp_candidates(
    *,
    inputs: SlTpInputs,
    entry: float,
    current_take_profit: float,
    is_long: bool,
) -> list[_ClampCandidate]:
    candidates: list[_ClampCandidate] = []
    resistance = inputs.resistance_level
    if resistance is not None:
        candidates.append(_ClampCandidate(label="resistance_level", level=float(resistance)))

    liquidity = inputs.liquidity_zone
    if liquidity is not None and abs(entry - float(liquidity)) <= float(inputs.liquidity_tolerance):
        candidates.append(_ClampCandidate(label="liquidity_zone", level=float(liquidity)))

    if inputs.use_psych_levels:
        psych_level = _nearest_psych_level(
            entry=entry,
            take_profit=current_take_profit,
            is_long=is_long,
            steps=inputs.psych_steps or [100.0, 250.0, 500.0, 1000.0],
        )
        if psych_level is not None:
            candidates.append(_ClampCandidate(label="psych_level", level=psych_level))
    return candidates


def _nearest_psych_level(*, entry: float, take_profit: float, is_long: bool, steps: list[float]) -> float | None:
    levels = _psych_levels_near(entry, steps)
    if is_long:
        candidates = [level for level in levels if entry < level < take_profit]
    else:
        candidates = [level for level in levels if take_profit < level < entry]
    if not candidates:
        return None
    return min(candidates, key=lambda value: abs(value - entry))


def _clamp_to_level(
    *,
    level: float,
    label: str,
    entry: float,
    take_profit: float,
    risk: float,
    atr: float,
    level_buffer_atr: float,
    is_long: bool,
    min_effective_rrr_after_clamp: float,
    debug: list[str],
) -> float | None:
    buffer = level_buffer_atr * atr
    if is_long:
        if not (level > entry and level < take_profit):
            return None
        candidate = level - buffer
    else:
        if not (level < entry and level > take_profit):
            return None
        candidate = level + buffer

    if _effective_rrr(entry=entry, take_profit=candidate, risk=risk, is_long=is_long) < min_effective_rrr_after_clamp:
        debug.append(f"Rejected {label}: clamp too tight")
        return None

    debug.append(f"TP clamped to {label} {level:.2f} -> {candidate:.2f}")
    return candidate


def _expand_too_close_target(
    *,
    take_profit: float,
    entry: float,
    atr: float,
    rrr: float,
    risk: float,
    is_long: bool,
) -> float:
    if is_long and take_profit <= entry + (0.25 * atr):
        return entry + max(0.6 * atr, rrr * risk)
    if (not is_long) and take_profit >= entry - (0.25 * atr):
        return entry - max(0.6 * atr, rrr * risk)
    return take_profit


def _psych_levels_near(price: float, steps: list[float]) -> list[float]:
    levels: list[float] = []
    for step in steps:
        if step <= 0:
            continue
        base = math.floor(price / step) * step
        for offset in range(-2, 3):
            level = base + (offset * step)
            if level > 0:
                levels.append(level)
    return sorted(set(levels))
