"""Narrow, versioned SHORT stop-loss policy shared by simulation and replay."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShortStopCapDecision:
    stop_loss: float
    applied: bool
    baseline_stop_atr: float | None = None


def apply_short_stop_cap(
    *,
    side: str,
    entry: float,
    stop_loss: float,
    atr: float | None,
    band_min_atr: float,
    band_max_atr: float,
    cap_atr: float,
) -> ShortStopCapDecision:
    """Cap only valid SHORT stops inside the declared ATR band."""

    normalized_side = str(side).upper()
    numeric_atr = float(atr or 0.0)
    numeric_entry = float(entry)
    numeric_stop = float(stop_loss)
    if normalized_side not in {"SHORT", "SELL"} or numeric_atr <= 0 or numeric_stop <= numeric_entry:
        return ShortStopCapDecision(stop_loss=numeric_stop, applied=False)

    baseline_stop_atr = (numeric_stop - numeric_entry) / numeric_atr
    if float(band_min_atr) <= baseline_stop_atr < float(band_max_atr):
        return ShortStopCapDecision(
            stop_loss=numeric_entry + (float(cap_atr) * numeric_atr),
            applied=True,
            baseline_stop_atr=baseline_stop_atr,
        )
    return ShortStopCapDecision(
        stop_loss=numeric_stop,
        applied=False,
        baseline_stop_atr=baseline_stop_atr,
    )
