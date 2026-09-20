"""File: indicator_snapshot.py
Folder: platform_v2/spot/domain/models
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Indicator snapshot domain model for SmartSignalHub V2.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IndicatorSnapshot:
    """Normalized indicator snapshot used before signal decisions.

    Args:
        symbol: Instrument symbol.
        timeframe: Snapshot timeframe.
        timestamp_text: Human-readable calculation timestamp.
        price: Reference price used for the snapshot.
        volume: Snapshot volume.
        rsi: Relative strength index value.
        macd: MACD value.
        macd_signal: MACD signal line.
        macd_trend: MACD trend label.
        ema9: EMA 9 value.
        ema50: EMA 50 value.
        ema200: EMA 200 value.
        ema50_slope: EMA 50 slope.
        vwap: VWAP value.
        vwap_signal: Relative VWAP label.
        adx: ADX value.
        atr: ATR value.
        atr_spike: ATR spike flag.
        tenkan: Ichimoku tenkan.
        kijun: Ichimoku kijun.
        ichimoku_signal: Ichimoku direction label.
        plus_di: Positive directional index.
        minus_di: Negative directional index.
        adx_slope: ADX slope.
        atr_growth_20: ATR growth over lookback.
        atr_spike_threshold: Dynamic ATR spike threshold.
        swing_low: Structure support reference.
        swing_high: Structure resistance reference.
        resistance_level: Nearest overhead resistance reference.
        liquidity_zone: Nearest liquidity-style overhead zone.
        liquidity_tolerance: Acceptable distance for liquidity clamp usage.
        bounce_confirmed: Whether the recent candles confirm a bounce from support.
        avg_volume_10: Average volume over the recent 10 candles.
        extras: Additional snapshot fields not promoted yet.
    """

    symbol: str
    timeframe: str
    timestamp_text: str
    price: float
    volume: float | None = None
    rsi: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_trend: str | None = None
    ema9: float | None = None
    ema50: float | None = None
    ema200: float | None = None
    ema50_slope: float | None = None
    vwap: float | None = None
    vwap_signal: str | None = None
    adx: float | None = None
    atr: float | None = None
    atr_spike: bool | None = None
    tenkan: float | None = None
    kijun: float | None = None
    ichimoku_signal: str | None = None
    plus_di: float | None = None
    minus_di: float | None = None
    adx_slope: float | None = None
    atr_growth_20: float | None = None
    atr_spike_threshold: float | None = None
    swing_low: float | None = None
    swing_high: float | None = None
    resistance_level: float | None = None
    liquidity_zone: float | None = None
    liquidity_tolerance: float | None = None
    bounce_confirmed: bool | None = None
    avg_volume_10: float | None = None
    extras: dict[str, float | int | str | bool | list[float] | None] = field(default_factory=dict)
