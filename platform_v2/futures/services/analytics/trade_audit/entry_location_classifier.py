"""File: entry_location_classifier.py
Folder: platform_v2/futures/services/analytics/trade_audit
Created date: 2026-05-01
Last updated date: 2026-05-01
Author: Codex
Purpose: Classify Futures entry price location without changing execution rules.
"""

from __future__ import annotations

from typing import Any


class EntryLocationClassifier:
    """Classify whether an entry is clean, extended, or close to a key extreme."""

    EMA9_EXTENSION_ATR = 1.2
    VWAP_EXTENSION_ATR = 1.5
    EXTREME_PROXIMITY_ATR = 0.3
    LONG_RSI_EXHAUSTION = 72.0
    SHORT_RSI_EXHAUSTION = 28.0

    @classmethod
    def classify(
        cls,
        *,
        side: str,
        entry_price: float | None,
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        side = side.upper()
        atr = cls._as_float(snapshot.get("atr"))
        ema9 = cls._as_float(snapshot.get("ema9"))
        ema50 = cls._as_float(snapshot.get("ema50"))
        vwap = cls._as_float(snapshot.get("vwap"))
        rsi = cls._as_float(snapshot.get("rsi"))
        swing_high = cls._as_float(snapshot.get("swing_high"))
        swing_low = cls._as_float(snapshot.get("swing_low"))

        ema9_distance = cls._distance_atr(entry_price, ema9, atr)
        ema50_distance = cls._distance_atr(entry_price, ema50, atr)
        vwap_distance = cls._distance_atr(entry_price, vwap, atr)
        high_distance = cls._distance_to_upper_atr(entry_price, swing_high, atr)
        low_distance = cls._distance_to_lower_atr(entry_price, swing_low, atr)

        flags = cls._flags(
            side=side,
            ema9_distance=ema9_distance,
            vwap_distance=vwap_distance,
            high_distance=high_distance,
            low_distance=low_distance,
            rsi=rsi,
        )
        return {
            "type": cls._verdict(side=side, flags=flags),
            "flags": flags,
            "ema9_distance_atr": ema9_distance,
            "ema50_distance_atr": ema50_distance,
            "vwap_distance_atr": vwap_distance,
            "distance_to_swing_high_atr": high_distance,
            "distance_to_swing_low_atr": low_distance,
            "rsi": rsi,
            "thresholds": {
                "ema9_extension_atr": cls.EMA9_EXTENSION_ATR,
                "vwap_extension_atr": cls.VWAP_EXTENSION_ATR,
                "extreme_proximity_atr": cls.EXTREME_PROXIMITY_ATR,
                "long_rsi_exhaustion": cls.LONG_RSI_EXHAUSTION,
                "short_rsi_exhaustion": cls.SHORT_RSI_EXHAUSTION,
            },
        }

    @classmethod
    def _flags(
        cls,
        *,
        side: str,
        ema9_distance: float | None,
        vwap_distance: float | None,
        high_distance: float | None,
        low_distance: float | None,
        rsi: float | None,
    ) -> list[str]:
        flags: list[str] = []
        if side == "LONG":
            extended = cls._above(ema9_distance, cls.EMA9_EXTENSION_ATR) or cls._above(
                vwap_distance,
                cls.VWAP_EXTENSION_ATR,
            )
            if extended:
                flags.append("UPPER_EXTENSION")
            if cls._near_extreme(high_distance):
                flags.append("INTO_RESISTANCE")
            if rsi is not None and rsi >= cls.LONG_RSI_EXHAUSTION and extended:
                flags.append("RSI_OVERHEATED")
            return flags

        if side == "SHORT":
            extended = cls._below(ema9_distance, -cls.EMA9_EXTENSION_ATR) or cls._below(
                vwap_distance,
                -cls.VWAP_EXTENSION_ATR,
            )
            if extended:
                flags.append("LOWER_EXTENSION")
            if cls._near_extreme(low_distance):
                flags.append("INTO_SUPPORT")
            if rsi is not None and rsi <= cls.SHORT_RSI_EXHAUSTION and extended:
                flags.append("RSI_OVERSOLD")
        return flags

    @staticmethod
    def _verdict(*, side: str, flags: list[str]) -> str:
        if not flags:
            return "CLEAN"
        if side == "LONG" and "UPPER_EXTENSION" in flags and "INTO_RESISTANCE" in flags:
            return "EXTENDED_INTO_RESISTANCE"
        if side == "SHORT" and "LOWER_EXTENSION" in flags and "INTO_SUPPORT" in flags:
            return "EXTENDED_INTO_SUPPORT"
        if "RSI_OVERHEATED" in flags:
            return "OVERHEATED_EXTENSION"
        if "RSI_OVERSOLD" in flags:
            return "OVERSOLD_EXTENSION"
        if "INTO_RESISTANCE" in flags:
            return "INTO_RESISTANCE"
        if "INTO_SUPPORT" in flags:
            return "INTO_SUPPORT"
        if "UPPER_EXTENSION" in flags or "LOWER_EXTENSION" in flags:
            return "EXTENDED"
        return "CAUTION"

    @staticmethod
    def _above(value: float | None, threshold: float) -> bool:
        return value is not None and value >= threshold

    @staticmethod
    def _below(value: float | None, threshold: float) -> bool:
        return value is not None and value <= threshold

    @classmethod
    def _near_extreme(cls, value: float | None) -> bool:
        return value is not None and 0 <= value <= cls.EXTREME_PROXIMITY_ATR

    @staticmethod
    def _distance_atr(price: float | None, reference: float | None, atr: float | None) -> float | None:
        if price is None or reference is None or atr is None or atr <= 0:
            return None
        return round((price - reference) / atr, 4)

    @staticmethod
    def _distance_to_upper_atr(price: float | None, upper: float | None, atr: float | None) -> float | None:
        if price is None or upper is None or atr is None or atr <= 0:
            return None
        return round((upper - price) / atr, 4)

    @staticmethod
    def _distance_to_lower_atr(price: float | None, lower: float | None, atr: float | None) -> float | None:
        if price is None or lower is None or atr is None or atr <= 0:
            return None
        return round((price - lower) / atr, 4)

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value is None:
            return None
        parsed: float | None = None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = None
        return parsed
