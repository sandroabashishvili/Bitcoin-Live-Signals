"""File: service.py
Folder: platform_v2/futures/services/analytics/market_plan
Created date: 2026-05-01
Last updated date: 2026-05-14
Author: Codex
Purpose: Build read-only Futures market plans with working zones for audit and review.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from platform_v2.shared.backend.runtime_store.futures import MARKET_PLANS_FAMILY, upsert_runtime_row
from platform_v2.futures.storage import indicator_snapshot_file_path, load_json_list


class FuturesMarketPlanService:
    """Create trader-style LONG/SHORT working zones without changing execution."""

    MICRO_WINDOW = "5m last 24-48 candles"
    PRIMARY_WINDOW = "15m last 48-96 candles"
    CONTEXT_WINDOW = "4h last 30-60 candles"

    def build_and_store(self, *, date_iso: str, symbol: str, timeframe: str = "15m") -> Path | None:
        plan = self.build_plan(date_iso=date_iso, symbol=symbol, timeframe=timeframe)
        if not plan:
            return None
        return upsert_runtime_row(
            family_name=MARKET_PLANS_FAMILY,
            date_iso=date_iso,
            row=plan,
            match_keys=("timestamp_ms", "symbol", "timeframe"),
        )

    def build_plan(self, *, date_iso: str, symbol: str, timeframe: str = "15m") -> dict[str, Any]:
        snapshots = {
            "5m": self._latest_snapshot(symbol=symbol, timeframe="5m"),
            timeframe: self._latest_snapshot(symbol=symbol, timeframe=timeframe),
            "4h": self._latest_snapshot(symbol=symbol, timeframe="4h"),
        }
        primary = snapshots.get(timeframe) or {}
        if not primary:
            return {}

        current_price = self._as_float(primary.get("price"))
        atr = self._as_float(primary.get("atr"))
        timestamp_ms = self._as_int(primary.get("timestamp_ms") or primary.get("close_time_ms"))
        if current_price is None or timestamp_ms is None:
            return {}

        width = self._zone_width(current_price=current_price, atr=atr)
        bias = self._bias(primary=primary, higher=snapshots.get("4h") or {})
        location = self._location(primary=primary, current_price=current_price, atr=atr)

        return {
            "date": date_iso,
            "timestamp_ms": timestamp_ms,
            "datetime": primary.get("datetime"),
            "symbol": symbol,
            "timeframe": timeframe,
            "bias": bias,
            "current_price": round(current_price, 2),
            "context": {
                "micro_window": self.MICRO_WINDOW,
                "primary_window": self.PRIMARY_WINDOW,
                "higher_window": self.CONTEXT_WINDOW,
                "timeframes": self._timeframe_context(snapshots),
            },
            "location": location,
            "long_plan": self._long_plan(
                bias=bias,
                primary=primary,
                micro=snapshots.get("5m") or {},
                current_price=current_price,
                width=width,
                location=location,
            ),
            "short_plan": self._short_plan(
                bias=bias,
                primary=primary,
                micro=snapshots.get("5m") or {},
                current_price=current_price,
                width=width,
                location=location,
            ),
            "reference_levels": self._reference_levels(primary=primary, higher=snapshots.get("4h") or {}),
            "notes": [
                "Read-only market plan; execution is unchanged.",
                "Zones are ATR-width working areas, not automatic orders.",
            ],
        }

    def _long_plan(
        self,
        *,
        bias: str,
        primary: dict[str, Any],
        micro: dict[str, Any],
        current_price: float,
        width: float,
        location: dict[str, Any],
    ) -> dict[str, Any]:
        zones = self._dedupe_zones(
            [
                self._level_zone("15m VWAP retest", primary.get("vwap"), width, "15m"),
                self._level_zone("15m Kijun retest", primary.get("kijun"), width, "15m"),
                self._level_zone("15m EMA50 support", primary.get("ema50"), width, "15m"),
                self._level_zone("15m swing low support", primary.get("swing_low"), width, "15m"),
            ]
        )
        status = "WAIT_PULLBACK" if bias == "LONG" and location.get("long_entry_state") != "CLEAN" else "WATCH_CONFIRMATION"
        if bias == "SHORT":
            status = "COUNTER_TREND_ONLY"
        return {
            "status": status,
            "zones": zones,
            "confirmation": self._long_confirmation(micro=micro, primary=primary),
            "invalidations": [
                "15m closes below EMA50 without reclaim",
                "4h context turns bearish",
            ],
            "comment": self._long_comment(status=status, current_price=current_price, zones=zones),
        }

    def _short_plan(
        self,
        *,
        bias: str,
        primary: dict[str, Any],
        micro: dict[str, Any],
        current_price: float,
        width: float,
        location: dict[str, Any],
    ) -> dict[str, Any]:
        zones = self._dedupe_zones(
            [
                self._range_zone(
                    "15m resistance/liquidity rejection",
                    primary.get("resistance_level"),
                    primary.get("liquidity_zone"),
                    width,
                    "15m",
                ),
                self._level_zone("15m swing high rejection", primary.get("swing_high"), width, "15m"),
                self._level_zone("breakdown retest: 15m Kijun", primary.get("kijun"), width, "15m"),
                self._level_zone("breakdown retest: 15m VWAP", primary.get("vwap"), width, "15m"),
            ]
        )
        status = "WAIT_REJECTION_OR_BREAKDOWN" if bias == "LONG" else "WATCH_CONFIRMATION"
        if bias == "SHORT" and location.get("short_entry_state") != "CLEAN":
            status = "WAIT_BOUNCE_RETEST"
        return {
            "status": status,
            "zones": zones,
            "confirmation": self._short_confirmation(micro=micro, primary=primary),
            "invalidations": [
                "15m closes above swing high and holds",
                "5m reclaims VWAP/EMA9 after rejection attempt",
            ],
            "comment": self._short_comment(status=status, current_price=current_price, zones=zones),
        }

    def _location(self, *, primary: dict[str, Any], current_price: float, atr: float | None) -> dict[str, Any]:
        ema9_distance = self._distance_atr(current_price, self._as_float(primary.get("ema9")), atr)
        vwap_distance = self._distance_atr(current_price, self._as_float(primary.get("vwap")), atr)
        swing_high_distance = self._distance_to_upper_atr(
            current_price,
            self._as_float(primary.get("swing_high")),
            atr,
        )
        swing_low_distance = self._distance_to_lower_atr(
            current_price,
            self._as_float(primary.get("swing_low")),
            atr,
        )
        long_extended = self._above(ema9_distance, 1.2) or self._above(vwap_distance, 1.5)
        short_extended = self._below(ema9_distance, -1.2) or self._below(vwap_distance, -1.5)
        near_high = swing_high_distance is not None and 0 <= swing_high_distance <= 0.3
        near_low = swing_low_distance is not None and 0 <= swing_low_distance <= 0.3
        return {
            "ema9_distance_atr": ema9_distance,
            "vwap_distance_atr": vwap_distance,
            "distance_to_swing_high_atr": swing_high_distance,
            "distance_to_swing_low_atr": swing_low_distance,
            "long_entry_state": "EXTENDED_OR_RESISTANCE" if long_extended or near_high else "CLEAN",
            "short_entry_state": "EXTENDED_OR_SUPPORT" if short_extended or near_low else "CLEAN",
        }

    def _bias(self, *, primary: dict[str, Any], higher: dict[str, Any]) -> str:
        primary_score = self._direction_score(primary)
        higher_score = self._direction_score(higher)
        total = primary_score + higher_score
        if total >= 3:
            return "LONG"
        if total <= -3:
            return "SHORT"
        return "MIXED"

    def _direction_score(self, snapshot: dict[str, Any]) -> int:
        if not snapshot:
            return 0
        price = self._as_float(snapshot.get("price"))
        score = 0
        for key in ("ema9", "ema50", "vwap"):
            reference = self._as_float(snapshot.get(key))
            if price is None or reference is None:
                continue
            score += 1 if price >= reference else -1
        macd_trend = str(snapshot.get("macd_trend") or "").upper()
        if macd_trend == "BULLISH":
            score += 1
        elif macd_trend == "BEARISH":
            score -= 1
        return score

    def _timeframe_context(self, snapshots: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        context: dict[str, dict[str, Any]] = {}
        for timeframe, snapshot in snapshots.items():
            context[timeframe] = {
                "price": self._round(self._as_float(snapshot.get("price"))),
                "direction_score": self._direction_score(snapshot),
                "macd_trend": snapshot.get("macd_trend"),
                "vwap_signal": snapshot.get("vwap_signal"),
                "rsi": self._round(self._as_float(snapshot.get("rsi"))),
            }
        return context

    def _reference_levels(self, *, primary: dict[str, Any], higher: dict[str, Any]) -> dict[str, Any]:
        keys = ("ema9", "ema50", "vwap", "kijun", "swing_low", "swing_high", "resistance_level", "liquidity_zone")
        return {
            "primary_15m": {key: self._round(self._as_float(primary.get(key))) for key in keys},
            "higher_4h": {key: self._round(self._as_float(higher.get(key))) for key in keys},
        }

    def _long_confirmation(self, *, micro: dict[str, Any], primary: dict[str, Any]) -> list[str]:
        return [
            f"5m reclaim above VWAP/EMA9; current 5m vwap_signal={micro.get('vwap_signal')}",
            f"15m holds above Kijun/EMA50; 15m macd_trend={primary.get('macd_trend')}",
            "bounce_confirmed or higher-low on 5m before entry",
        ]

    def _short_confirmation(self, *, micro: dict[str, Any], primary: dict[str, Any]) -> list[str]:
        return [
            f"5m rejection below VWAP/EMA9; current 5m vwap_signal={micro.get('vwap_signal')}",
            f"15m loses VWAP/Kijun or rejects resistance; 15m macd_trend={primary.get('macd_trend')}",
            "lower-high on 5m or breakdown/retest before entry",
        ]

    def _long_comment(self, *, status: str, current_price: float, zones: list[dict[str, Any]]) -> str:
        nearest = self._nearest_zone(current_price=current_price, zones=zones)
        if status == "WAIT_PULLBACK":
            return f"LONG bias is active, but wait for pullback; nearest long zone is {nearest}."
        return f"LONG can be watched on confirmation; nearest long zone is {nearest}."

    def _short_comment(self, *, status: str, current_price: float, zones: list[dict[str, Any]]) -> str:
        nearest = self._nearest_zone(current_price=current_price, zones=zones)
        if status == "WAIT_REJECTION_OR_BREAKDOWN":
            return f"SHORT needs rejection or breakdown/retest; nearest short zone is {nearest}."
        return f"SHORT can be watched on confirmation; nearest short zone is {nearest}."

    def _level_zone(self, name: str, level: Any, width: float, timeframe: str) -> dict[str, Any]:
        center = self._as_float(level)
        if center is None:
            return {}
        return {
            "name": name,
            "timeframe": timeframe,
            "center": round(center, 2),
            "from": round(center - width, 2),
            "to": round(center + width, 2),
            "basis": "level +/- ATR width",
        }

    def _range_zone(self, name: str, a: Any, b: Any, width: float, timeframe: str) -> dict[str, Any]:
        first = self._as_float(a)
        second = self._as_float(b)
        if first is None and second is None:
            return {}
        values = [value for value in (first, second) if value is not None]
        low = min(values)
        high = max(values)
        return {
            "name": name,
            "timeframe": timeframe,
            "center": round((low + high) / 2.0, 2),
            "from": round(low - width, 2),
            "to": round(high + width, 2),
            "basis": "range +/- ATR width",
        }

    def _dedupe_zones(self, zones: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cleaned: list[dict[str, Any]] = []
        seen: set[tuple[str, float]] = set()
        for zone in zones:
            if not zone:
                continue
            key = (str(zone.get("name")), float(zone.get("center") or 0.0))
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(zone)
        return cleaned

    def _nearest_zone(self, *, current_price: float, zones: list[dict[str, Any]]) -> str:
        if not zones:
            return "none"
        nearest = min(zones, key=lambda zone: abs(float(zone.get("center") or current_price) - current_price))
        return f"{nearest.get('name')} {nearest.get('from')}-{nearest.get('to')}"

    def _latest_snapshot(self, *, symbol: str, timeframe: str) -> dict[str, Any]:
        rows = load_json_list(indicator_snapshot_file_path(symbol, timeframe))
        return rows[-1] if rows else {}

    @staticmethod
    def _zone_width(*, current_price: float, atr: float | None) -> float:
        atr_width = (atr or 0.0) * 0.25
        pct_width = current_price * 0.001
        return max(atr_width, pct_width)

    @staticmethod
    def _distance_atr(price: float, reference: float | None, atr: float | None) -> float | None:
        if reference is None or atr is None or atr <= 0:
            return None
        return round((price - reference) / atr, 4)

    @staticmethod
    def _distance_to_upper_atr(price: float, upper: float | None, atr: float | None) -> float | None:
        if upper is None or atr is None or atr <= 0:
            return None
        return round((upper - price) / atr, 4)

    @staticmethod
    def _distance_to_lower_atr(price: float, lower: float | None, atr: float | None) -> float | None:
        if lower is None or atr is None or atr <= 0:
            return None
        return round((price - lower) / atr, 4)

    @staticmethod
    def _above(value: float | None, threshold: float) -> bool:
        return value is not None and value >= threshold

    @staticmethod
    def _below(value: float | None, threshold: float) -> bool:
        return value is not None and value <= threshold

    @staticmethod
    def _round(value: float | None) -> float | None:
        return round(value, 2) if value is not None else None

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

    @staticmethod
    def _as_int(value: Any) -> int | None:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return None
