"""Spot-owned rules copied on 2026-09-10; no Futures runtime dependency."""
from __future__ import annotations

from platform_v2.spot.config import long_strategy_settings as settings


class SpotLongStructureScoreService:
    """Keep structure and ATR-distance scoring separate from other components."""

    @classmethod
    def long_score(cls, snapshot, price: float, atr_spike_block: bool) -> float:
        if atr_spike_block:
            return 0.0
        distance_from_low_atr = cls.distance_from_lower_atr(
            price,
            snapshot.swing_low,
            snapshot.atr,
        )
        room_to_high_atr = cls.distance_to_upper_atr(
            price,
            snapshot.swing_high,
            snapshot.atr,
        )
        if distance_from_low_atr is None or room_to_high_atr is None:
            return 0.0

        score = 0.0
        if (
            settings.STRUCTURE_LONG_LOW_DISTANCE_EARLY_ATR_MIN
            <= distance_from_low_atr
            < settings.STRUCTURE_LONG_LOW_DISTANCE_HEALTHY_ATR_MIN
        ):
            score += 1.0
        elif (
            settings.STRUCTURE_LONG_LOW_DISTANCE_EXTENSION_ATR_MIN
            <= distance_from_low_atr
            < settings.STRUCTURE_LONG_LOW_DISTANCE_BLOWOFF_ATR_MIN
        ):
            score += 0.8
        elif (
            settings.STRUCTURE_LONG_LOW_DISTANCE_MID_ATR_MIN
            <= distance_from_low_atr
            < settings.STRUCTURE_LONG_LOW_DISTANCE_EXTENSION_ATR_MIN
        ):
            score += 0.2
        elif (
            settings.STRUCTURE_LONG_LOW_DISTANCE_HEALTHY_ATR_MIN
            <= distance_from_low_atr
            < settings.STRUCTURE_LONG_LOW_DISTANCE_MID_ATR_MIN
        ):
            score += 0.1

        if (
            settings.STRUCTURE_LONG_SWING_HIGH_ROOM_MIN_ATR
            <= room_to_high_atr
            < settings.STRUCTURE_LONG_SWING_HIGH_ROOM_EXTENDED_ATR
        ):
            score += 0.8
        elif 0.5 <= room_to_high_atr < settings.STRUCTURE_LONG_SWING_HIGH_ROOM_MIN_ATR:
            score += 0.1
        elif room_to_high_atr < 0.5:
            score -= 0.8
        elif room_to_high_atr >= settings.STRUCTURE_LONG_SWING_HIGH_ROOM_EXTENDED_ATR:
            score += 0.1

        if bool(snapshot.bounce_confirmed):
            score += 0.2
        return round(max(0.0, min(3.0, score)), 2)

    @classmethod
    def short_score(cls, snapshot, price: float, atr_spike_block: bool) -> float:
        if atr_spike_block:
            return 0.0
        distance_from_high_atr = cls.distance_from_upper_atr(
            price,
            snapshot.swing_high,
            snapshot.atr,
        )
        room_to_low_atr = cls.distance_to_lower_atr(
            price,
            snapshot.swing_low,
            snapshot.atr,
        )
        if distance_from_high_atr is None or room_to_low_atr is None:
            return 0.0

        score = 0.0
        if (
            settings.STRUCTURE_SHORT_HIGH_DISTANCE_HEALTHY_ATR_MIN
            <= distance_from_high_atr
            < settings.STRUCTURE_SHORT_HIGH_DISTANCE_LATE_ATR_MIN
        ):
            score += 1.3
        elif (
            settings.STRUCTURE_SHORT_HIGH_DISTANCE_LATE_ATR_MIN
            <= distance_from_high_atr
            < settings.STRUCTURE_SHORT_HIGH_DISTANCE_EXHAUSTED_ATR_MIN
        ):
            score += 1.0
        elif (
            settings.STRUCTURE_SHORT_HIGH_DISTANCE_EARLY_ATR_MIN
            <= distance_from_high_atr
            < settings.STRUCTURE_SHORT_HIGH_DISTANCE_HEALTHY_ATR_MIN
        ):
            score += 0.4
        elif 0.5 <= distance_from_high_atr < settings.STRUCTURE_SHORT_HIGH_DISTANCE_EARLY_ATR_MIN:
            score += 0.2
        elif distance_from_high_atr >= settings.STRUCTURE_SHORT_HIGH_DISTANCE_EXHAUSTED_ATR_MIN:
            score += 0.2

        if settings.STRUCTURE_SHORT_SWING_LOW_ROOM_DANGER_ATR <= room_to_low_atr < 1.0:
            score += 0.6
        elif (
            settings.STRUCTURE_SHORT_SWING_LOW_ROOM_HEALTHY_ATR
            <= room_to_low_atr
            < settings.STRUCTURE_SHORT_SWING_LOW_ROOM_LATE_ATR
        ):
            score += 0.6
        elif (
            settings.STRUCTURE_SHORT_SWING_LOW_ROOM_LATE_ATR
            <= room_to_low_atr
            < settings.STRUCTURE_SHORT_SWING_LOW_ROOM_EXTENDED_ATR
        ):
            score += 0.4
        elif 1.0 <= room_to_low_atr < settings.STRUCTURE_SHORT_SWING_LOW_ROOM_HEALTHY_ATR:
            score += 0.1
        elif room_to_low_atr < settings.STRUCTURE_SHORT_SWING_LOW_ROOM_DANGER_ATR:
            score -= 0.8

        if bool(snapshot.extras.get("rejection_confirmed")):
            score += 0.2
        return round(max(0.0, min(3.0, score)), 2)

    @staticmethod
    def distance_from_lower_atr(
        price: float,
        lower: float | None,
        atr: float | None,
    ) -> float | None:
        if lower is None or atr is None or atr <= 0:
            return None
        return (price - lower) / atr

    @staticmethod
    def distance_to_lower_atr(
        price: float,
        lower: float | None,
        atr: float | None,
    ) -> float | None:
        if lower is None or atr is None or atr <= 0:
            return None
        return (price - lower) / atr

    @staticmethod
    def distance_from_upper_atr(
        price: float,
        upper: float | None,
        atr: float | None,
    ) -> float | None:
        if upper is None or atr is None or atr <= 0:
            return None
        return (upper - price) / atr

    @staticmethod
    def distance_to_upper_atr(
        price: float,
        upper: float | None,
        atr: float | None,
    ) -> float | None:
        if upper is None or atr is None or atr <= 0:
            return None
        return (upper - price) / atr
