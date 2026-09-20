"""Research-only SL/TP adjustments for explicit candidate profiles."""

from __future__ import annotations

from dataclasses import dataclass

from platform_v2.futures.domain.short_stop_policy import apply_short_stop_cap
from platform_v2.tools.research.replay.candidate_profiles import CandidateProfile


@dataclass(frozen=True)
class ExitLevels:
    stop_loss: float
    take_profit: float
    applied_policy: str | None = None
    reasons: tuple[str, ...] = ()


def adjust_exit_levels(
    *,
    profile: CandidateProfile,
    side: str,
    entry: float,
    stop_loss: float,
    take_profit: float,
    atr: float | None,
) -> ExitLevels:
    """Apply declared exit policies without mutating live SL/TP services."""

    levels = ExitLevels(stop_loss=float(stop_loss), take_profit=float(take_profit))
    for policy_id in profile.exit_policy_ids:
        levels = _apply_policy(
            policy_id=policy_id,
            levels=levels,
            side=side,
            entry=float(entry),
            atr=float(atr or 0.0),
        )
    return levels


def _apply_policy(
    *,
    policy_id: str,
    levels: ExitLevels,
    side: str,
    entry: float,
    atr: float,
) -> ExitLevels:
    if str(side).upper() != "SHORT" or atr <= 0:
        return levels

    risk_atr = abs(levels.stop_loss - entry) / atr
    reward = abs(entry - levels.take_profit)
    effective_rr = reward / abs(levels.stop_loss - entry) if levels.stop_loss != entry else 0.0

    if policy_id == "short_mid_stop_cap_25_atr":
        cap = apply_short_stop_cap(
            side=side,
            entry=entry,
            stop_loss=levels.stop_loss,
            atr=atr,
            band_min_atr=2.5,
            band_max_atr=3.5,
            cap_atr=2.5,
        )
        if cap.applied:
            return ExitLevels(
                stop_loss=cap.stop_loss,
                take_profit=levels.take_profit,
                applied_policy=policy_id,
                reasons=(f"baseline_stop_atr={cap.baseline_stop_atr:.4f}",),
            )
        return levels
    if policy_id == "short_mid_stop_floor_35_atr":
        if 2.5 <= risk_atr < 3.5:
            return ExitLevels(
                stop_loss=entry + (3.5 * atr),
                take_profit=levels.take_profit,
                applied_policy=policy_id,
                reasons=(f"baseline_stop_atr={risk_atr:.4f}",),
            )
        return levels
    if policy_id == "short_rr_20_22_target_18":
        if 2.0 <= effective_rr < 2.2:
            risk = abs(levels.stop_loss - entry)
            return ExitLevels(
                stop_loss=levels.stop_loss,
                take_profit=entry - (1.8 * risk),
                applied_policy=policy_id,
                reasons=(f"baseline_effective_rr={effective_rr:.4f}",),
            )
        return levels
    raise ValueError(f"Unknown exit candidate policy: {policy_id}")
