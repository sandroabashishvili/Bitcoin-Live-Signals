"""File: entry_audit_service.py
Folder: platform_v2/futures/services/analytics/trade_audit
Created date: 2026-04-28
Last updated date: 2026-05-01
Author: Codex
Purpose: Build closed-trade Futures entry attribution rows for tuning.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from platform_v2.shared.backend.runtime_store.futures import (
    MARKET_PLANS_FAMILY,
    POSITION_EVENTS_FAMILY,
    SIGNALS_FAMILY,
    TRADE_ENTRY_AUDITS_FAMILY,
    daily_json_path,
    load_family_rows,
    load_family_rows_all,
)
from platform_v2.shared.backend.runtime_store.futures import write_json
from platform_v2.futures.storage import indicator_snapshot_file_path, load_json_list

from .entry_location_classifier import EntryLocationClassifier
from .entry_timing_classifier import EntryTimingClassifier


class FuturesTradeEntryAuditService:
    """Persist a per-closed-trade audit row without changing trading rules."""

    _SNAPSHOT_KEYS = (
        "timestamp_ms",
        "datetime",
        "price",
        "rsi",
        "macd",
        "macd_signal",
        "macd_trend",
        "ema9",
        "ema50",
        "ema200",
        "ema50_slope",
        "vwap",
        "vwap_signal",
        "adx",
        "atr",
        "atr_spike",
        "plus_di",
        "minus_di",
        "adx_slope",
        "atr_growth_20",
        "swing_low",
        "swing_high",
        "resistance_level",
        "liquidity_zone",
        "bounce_confirmed",
    )

    def build_and_store(self, *, date_iso: str) -> Path:
        rows = self.build_rows(date_iso=date_iso)
        return write_json(daily_json_path(TRADE_ENTRY_AUDITS_FAMILY, date_iso), rows)

    def build_rows(self, *, date_iso: str) -> list[dict[str, Any]]:
        positions = load_family_rows_all(POSITION_EVENTS_FAMILY)
        signals = load_family_rows_all(SIGNALS_FAMILY)
        market_plans = load_family_rows_all(MARKET_PLANS_FAMILY)
        signals_sorted = sorted(signals, key=lambda row: int(row.get("timestamp_ms") or 0))
        market_plans_sorted = sorted(market_plans, key=lambda row: int(row.get("timestamp_ms") or 0))
        signal_by_ts_side = self._index_signals(signals_sorted)
        opened_by_id, _ = self._split_positions(positions)
        _, closed_rows = self._split_positions(load_family_rows(POSITION_EVENTS_FAMILY, date_iso))
        audit_rows: list[dict[str, Any]] = []

        for closed in closed_rows:
            position_id = str(closed.get("position_id") or "")
            opened = opened_by_id.get(position_id, {})
            audit_rows.append(
                self._build_audit_row(
                    closed=closed,
                    opened=opened,
                    signal_by_ts_side=signal_by_ts_side,
                    signals_sorted=signals_sorted,
                    market_plans_sorted=market_plans_sorted,
                    position_id=position_id,
                )
            )

        audit_rows.sort(key=lambda row: int(row.get("close_timestamp_ms") or 0))
        return audit_rows

    def _build_audit_row(
        self,
        *,
        closed: dict[str, Any],
        opened: dict[str, Any],
        signal_by_ts_side: dict[tuple[int, str], dict[str, Any]],
        signals_sorted: list[dict[str, Any]],
        market_plans_sorted: list[dict[str, Any]],
        position_id: str,
    ) -> dict[str, Any]:
        side = str(closed.get("side") or opened.get("side") or "").upper()
        entry_ts = int(opened.get("timestamp_ms") or closed.get("opened_at_ms") or 0)
        signal = self._entry_signal(
            opened=opened, closed=closed, side=side,
            entry_ts=entry_ts, signal_by_ts_side=signal_by_ts_side,
        )
        signal_ts = int(signal.get("timestamp_ms") or entry_ts)
        snapshot = self._entry_snapshot(
            symbol=str(closed.get("symbol") or opened.get("symbol") or "BTCUSDT"),
            timeframe=str(closed.get("timeframe") or opened.get("timeframe") or "15m"),
            entry_ts=signal_ts,
        )
        prior_sides = self._prior_signal_sides(signals=signals_sorted, entry_ts=signal_ts)
        timing_context = EntryTimingClassifier.context(side=side, prior_sides=prior_sides)
        recorded_timing = signal.get("entry_quality") or {}
        entry_price = self._as_float(opened.get("entry_price") or closed.get("entry_price"))
        atr = self._as_float(snapshot.get("atr"))
        ema50 = self._as_float(snapshot.get("ema50"))
        vwap = self._as_float(snapshot.get("vwap"))
        entry_location = EntryLocationClassifier.classify(
            side=side,
            entry_price=entry_price,
            snapshot=snapshot,
        )
        entry_market_plan = self._entry_market_plan(
            market_plans=market_plans_sorted,
            entry_ts=entry_ts,
            entry_price=entry_price,
            side=side,
        )

        return {
            "position_id": position_id,
            "side": side,
            "outcome": str(closed.get("outcome") or closed.get("exit_reason") or "UNKNOWN"),
            "entry_time": opened.get("time_readable") or opened.get("opened_at"),
            "close_time": closed.get("time_readable") or closed.get("closed_at"),
            "entry_timestamp_ms": entry_ts,
            "entry_signal_timestamp_ms": signal.get("timestamp_ms"),
            "entry_signal_match_status": "MATCHED" if signal else "MISSING",
            "close_timestamp_ms": int(closed.get("timestamp_ms") or 0),
            "entry_price": entry_price,
            "exit_price": self._as_float(closed.get("exit_price")),
            "net_pnl": self._as_float(closed.get("net_pnl")),
            "rr_ratio": self._as_float(opened.get("rr_ratio") or closed.get("rr_ratio")),
            "entry_timing_type": recorded_timing.get("timing_type", timing_context.timing_type),
            "entry_direction_signal_age": recorded_timing.get("direction_signal_age", timing_context.direction_signal_age),
            "entry_prior_actionable_side": recorded_timing.get("prior_actionable_side", timing_context.prior_actionable_side),
            "entry_location_type": entry_location["type"],
            "distance_from_ema50_atr": self._distance_atr(entry_price, ema50, atr),
            "distance_from_vwap_atr": self._distance_atr(entry_price, vwap, atr),
            "entry_location": entry_location,
            "entry_market_plan_alignment": entry_market_plan.get("alignment"),
            "entry_market_plan": entry_market_plan,
            "entry_market_plan_permission": signal.get("market_plan_permission"),
            "entry_signal": self._compact_signal(signal),
            "entry_snapshot": self._compact_snapshot(snapshot),
        }

    @staticmethod
    def _entry_signal(
        *, opened: dict[str, Any], closed: dict[str, Any], side: str,
        entry_ts: int, signal_by_ts_side: dict[tuple[int, str], dict[str, Any]],
    ) -> dict[str, Any]:
        # Execution time differs from the decision candle. Never guess the
        # nearest signal: use recorded lineage, then legacy exact entry time.
        for row in (opened, closed):
            exact_ts = row.get("signal_timestamp_ms")
            if exact_ts:
                match = signal_by_ts_side.get((int(exact_ts), side))
                if match:
                    return match
            text = row.get("signal_candle_close_time")
            if row is opened:
                text = text or row.get("candle_close_time")
            if not text:
                continue
            try:
                parsed = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                second_ms = int(parsed.timestamp()) * 1000
            except (ValueError, OverflowError):
                continue
            matches = [value for (ts, direction), value in signal_by_ts_side.items()
                       if direction == side and second_ms <= ts < second_ms + 1000]
            if len(matches) == 1:
                return matches[0]
        return signal_by_ts_side.get((entry_ts, side), {})

    def _entry_market_plan(
        self,
        *,
        market_plans: list[dict[str, Any]],
        entry_ts: int,
        entry_price: float | None,
        side: str,
    ) -> dict[str, Any]:
        plan = self._nearest_prior_plan(market_plans=market_plans, entry_ts=entry_ts)
        if not plan:
            return {"alignment": "NO_PLAN"}

        side_plan = plan.get("long_plan") if side == "LONG" else plan.get("short_plan")
        if not isinstance(side_plan, dict):
            return {
                "alignment": "NO_SIDE_PLAN",
                "plan_timestamp_ms": plan.get("timestamp_ms"),
                "bias": plan.get("bias"),
            }

        nearest_zone = self._nearest_plan_zone(entry_price=entry_price, zones=side_plan.get("zones"))
        in_zone = bool(nearest_zone.get("entry_in_zone"))
        return {
            "alignment": "IN_ZONE" if in_zone else "OUTSIDE_ZONE",
            "plan_timestamp_ms": plan.get("timestamp_ms"),
            "bias": plan.get("bias"),
            "side_plan_status": side_plan.get("status"),
            "plan_location": plan.get("location"),
            "nearest_zone": nearest_zone,
        }

    @staticmethod
    def _nearest_prior_plan(*, market_plans: list[dict[str, Any]], entry_ts: int) -> dict[str, Any]:
        prior: dict[str, Any] = {}
        for row in market_plans:
            timestamp_ms = int(row.get("timestamp_ms") or 0)
            if timestamp_ms > entry_ts:
                break
            prior = row
        return prior

    def _nearest_plan_zone(self, *, entry_price: float | None, zones: Any) -> dict[str, Any]:
        if entry_price is None or not isinstance(zones, list):
            return {}
        zone_rows = [zone for zone in zones if isinstance(zone, dict)]
        if not zone_rows:
            return {}
        nearest = min(zone_rows, key=lambda zone: self._zone_distance(entry_price=entry_price, zone=zone))
        zone_from = self._as_float(nearest.get("from"))
        zone_to = self._as_float(nearest.get("to"))
        entry_in_zone = zone_from is not None and zone_to is not None and zone_from <= entry_price <= zone_to
        return {
            "name": nearest.get("name"),
            "from": zone_from,
            "to": zone_to,
            "center": self._as_float(nearest.get("center")),
            "entry_in_zone": entry_in_zone,
        }

    def _zone_distance(self, *, entry_price: float, zone: dict[str, Any]) -> float:
        center = self._as_float(zone.get("center"))
        if center is None:
            return 0.0
        return abs(center - entry_price)

    @staticmethod
    def _index_signals(signals: list[dict[str, Any]]) -> dict[tuple[int, str], dict[str, Any]]:
        indexed: dict[tuple[int, str], dict[str, Any]] = {}
        for row in signals:
            ts = int(row.get("timestamp_ms") or 0)
            side = str(row.get("side") or row.get("selected_direction") or "").upper()
            if ts > 0 and side:
                indexed[(ts, side)] = row
        return indexed

    @staticmethod
    def _split_positions(
        positions: list[dict[str, Any]],
    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
        opened_by_id: dict[str, dict[str, Any]] = {}
        closed_rows: list[dict[str, Any]] = []
        for row in positions:
            position_id = str(row.get("position_id") or "")
            if not position_id:
                continue
            event = str(row.get("event") or "").upper()
            status = str(row.get("status") or "").upper()
            if event == "OPENED":
                opened_by_id[position_id] = row
            elif status == "OPEN" and position_id not in opened_by_id:
                opened_by_id[position_id] = row
            if event == "CLOSED" or status == "CLOSED":
                closed_rows.append(row)
        return opened_by_id, closed_rows

    @staticmethod
    def _row_date(row: dict[str, Any]) -> str:
        text = str(row.get("time_readable") or row.get("closed_at") or "")
        if len(text) >= 10:
            return text[:10]
        timestamp_ms = int(row.get("timestamp_ms") or 0)
        if timestamp_ms > 0:
            return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        return ""

    @staticmethod
    def _prior_signal_sides(*, signals: list[dict[str, Any]], entry_ts: int) -> list[str]:
        return [
            str(row.get("side") or row.get("selected_direction") or "")
            for row in signals
            if int(row.get("timestamp_ms") or 0) < entry_ts
        ]

    def _entry_snapshot(self, *, symbol: str, timeframe: str, entry_ts: int) -> dict[str, Any]:
        path = indicator_snapshot_file_path(symbol, timeframe)
        rows = load_json_list(path)
        if not rows:
            return {}
        for row in reversed(rows):
            if int(row.get("timestamp_ms") or row.get("close_time_ms") or 0) == entry_ts:
                return row
        prior = [
            row
            for row in rows
            if int(row.get("timestamp_ms") or row.get("close_time_ms") or 0) <= entry_ts
        ]
        return prior[-1] if prior else {}

    @classmethod
    def _compact_snapshot(cls, snapshot: dict[str, Any]) -> dict[str, Any]:
        return {key: snapshot.get(key) for key in cls._SNAPSHOT_KEYS if key in snapshot}

    @staticmethod
    def _compact_signal(signal: dict[str, Any]) -> dict[str, Any]:
        if not signal:
            return {}
        return {
            "strategy_version": signal.get("strategy_version"),
            "side": signal.get("side"),
            "score": signal.get("score"),
            "threshold": signal.get("threshold"),
            "gates": signal.get("gates"),
            "direction_scores": signal.get("direction_scores"),
            "direction_gates": signal.get("direction_gates"),
            "direction_component_scores": signal.get("direction_component_scores"),
            "mtf_signals": signal.get("mtf_signals"),
            "permission_status": signal.get("permission_status"),
            "permission_reason": signal.get("permission_reason"),
        }

    @staticmethod
    def _distance_atr(price: float | None, reference: float | None, atr: float | None) -> float | None:
        if price is None or reference is None or atr is None or atr <= 0:
            return None
        return round((price - reference) / atr, 4)

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
