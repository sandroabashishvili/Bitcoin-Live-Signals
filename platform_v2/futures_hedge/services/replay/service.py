"""Read-only replay service for the independent Futures Hedge subsystem."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from platform_v2.shared.backend.persistence import read_market_series_safely
from platform_v2.shared.backend.runtime_store.futures import load_family_rows_all as load_futures_family_rows_all
from platform_v2.futures_hedge.config import FuturesHedgeProfile, default_profile
from platform_v2.futures_hedge.config import settings
from platform_v2.shared.backend.runtime_store.hedge import (
    HEDGE_BASKET_SNAPSHOTS_FAMILY,
    HEDGE_DAILY_SUMMARIES_FAMILY,
    HEDGE_ENTRIES_FAMILY,
    HEDGE_EQUITY_TIMELINE_FAMILY,
    HEDGE_RESET_EVENTS_FAMILY,
    daily_json_path,
    replace_family_rows,
    load_family_rows_all as load_hedge_family_rows_all,
    write_json,
)
from platform_v2.futures_hedge.services.portfolio import HedgeAccount, build_entry_from_trigger


class FuturesHedgeReplayService:
    """Replay Hedge basket accounting from confirmed Futures OPENED events."""

    def __init__(self, *, profile: FuturesHedgeProfile | None = None) -> None:
        self._profile = profile or default_profile()

    def build_report(self) -> dict[str, Any]:
        triggers = self._load_entry_triggers()
        latest_mark = self._latest_mark_price(triggers)
        account = HedgeAccount(profile=self._profile)
        accepted_entries: list[dict[str, Any]] = []
        basket_snapshots: list[dict[str, Any]] = []
        equity_points: list[dict[str, Any]] = []

        for trigger in triggers:
            entry = build_entry_from_trigger(trigger=trigger, profile=self._profile)
            if entry is None:
                continue
            mark_price = entry.entry_price
            if not account.can_open(entry=entry, mark_price=mark_price):
                if account.used_margin_usdt > 0:
                    account.reset(
                        mark_price=mark_price,
                        timestamp_ms=entry.timestamp_ms,
                        time_readable=entry.time_readable,
                        reason="capital_required_before_next_entry",
                    )
            if not account.can_open(entry=entry, mark_price=mark_price):
                account.skipped_entries.append(
                    {
                        "source_position_id": entry.source_position_id,
                        "timestamp_ms": entry.timestamp_ms,
                        "time_readable": entry.time_readable,
                        "side": entry.side,
                        "entry_price": round(entry.entry_price, 2),
                        "reason": "insufficient_hedge_capital",
                    }
                )
                continue

            account.add_entry(entry)
            entry_sequence = len(accepted_entries) + 1
            accepted_entries.append(
                {
                    "hedge_entry_id": f"HEDGE-{entry_sequence:06d}",
                    "source_position_id": entry.source_position_id,
                    "timestamp_ms": entry.timestamp_ms,
                    "time_readable": entry.time_readable,
                    "side": entry.side,
                    "entry_price": round(entry.entry_price, 2),
                    "margin_usdt": round(entry.margin_usdt, 2),
                    "notional_usdt": round(entry.notional_usdt, 2),
                    "quantity": round(entry.quantity, 8),
                    "leverage": self._profile.leverage,
                    "entry_fee_usdt": round(entry.entry_fee_usdt, 4),
                    "source_family": settings.SOURCE_POSITION_EVENTS_FAMILY,
                }
            )
            snapshot = account.snapshot(mark_price=mark_price)
            basket_snapshots.append(
                {
                    "snapshot_id": f"HEDGE-SNAPSHOT-{entry_sequence:06d}",
                    "hedge_entry_id": f"HEDGE-{entry_sequence:06d}",
                    "source_position_id": entry.source_position_id,
                    "timestamp_ms": entry.timestamp_ms,
                    "time_readable": entry.time_readable,
                    "mark_price": round(mark_price, 2),
                    "cash_usdt": snapshot["cash_usdt"],
                    "equity_usdt": snapshot["equity_usdt"],
                    "estimated_close_equity_usdt": snapshot["estimated_close_equity_usdt"],
                    "available_capital_usdt": snapshot["available_capital_usdt"],
                    "used_margin_usdt": snapshot["used_margin_usdt"],
                    "unrealized_pnl_usdt": snapshot["unrealized_pnl_usdt"],
                    "reset_count": snapshot["reset_count"],
                    "long_basket": snapshot["long_basket"],
                    "short_basket": snapshot["short_basket"],
                }
            )
            equity_points.append(
                {
                    "timestamp_ms": entry.timestamp_ms,
                    "time_readable": entry.time_readable,
                    "mark_price": round(mark_price, 2),
                    "equity_usdt": snapshot["equity_usdt"],
                    "available_capital_usdt": snapshot["available_capital_usdt"],
                    "used_margin_usdt": snapshot["used_margin_usdt"],
                }
            )

        final_snapshot = account.snapshot(mark_price=latest_mark)
        decision_summary = self._build_decision_summary(
            final_snapshot=final_snapshot,
            latest_mark=latest_mark,
        )
        current_equity_point = self._build_current_equity_point(
            final_snapshot=final_snapshot,
            decision_summary=decision_summary,
            latest_mark=latest_mark,
            accepted_entries_count=len(accepted_entries),
            skipped_entries_count=len(account.skipped_entries),
        )
        performance_points = self._merged_cycle_equity_points(current_equity_point)
        peak_equity = self._peak_equity_usdt(performance_points)
        lowest_equity = self._lowest_equity_usdt(performance_points, fallback=self._profile.starting_capital_usdt)
        max_open_profit = self._max_open_profit_usdt(
            peak_equity=peak_equity,
            starting_capital=self._profile.starting_capital_usdt,
        )
        return {
            "system": "futures_hedge",
            "mode": "paper_replay",
            "generated_at": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%SZ"),
            "profile": self._profile.to_dict(),
            "source": {
                "entry_family": settings.SOURCE_POSITION_EVENTS_FAMILY,
                "entry_rule": "event == OPENED",
                "entry_fields_used": ["position_id", "side", "timestamp_ms", "time_readable", "entry_price"],
                "candles_source": "smartsignalhub_market_data.sqlite3 / binance futures candles",
                "source_boundary": "Futures supplies entry permission only; Hedge owns capital, sizing, leverage, margin, fees, and reset rules.",
            },
            "source_counts": {
                "opened_futures_events": len(triggers),
                "hedge_entries_accepted": len(accepted_entries),
                "hedge_entries_skipped": len(account.skipped_entries),
            },
            "final_mark_price": round(latest_mark, 2),
            "decision_summary": decision_summary,
            "final_snapshot": final_snapshot,
            "max_drawdown_pct": self._max_drawdown_pct(
                points=performance_points,
                starting_capital=self._profile.starting_capital_usdt,
            ),
            "peak_equity_usdt": peak_equity,
            "lowest_equity_usdt": lowest_equity,
            "max_open_profit_usdt": max_open_profit,
            "max_runup_pct": self._max_runup_pct(
                max_open_profit=max_open_profit,
                starting_capital=self._profile.starting_capital_usdt,
            ),
            "accepted_entries": accepted_entries,
            "basket_snapshots": basket_snapshots,
            "reset_events": account.reset_events,
            "skipped_entries": account.skipped_entries,
            "equity_points": performance_points,
            "current_equity_point": current_equity_point,
            "limitations": [
                "Liquidation Risk is a first-pass ROE-based visibility label, not an exchange liquidation model.",
                "No funding fees yet.",
                "No slippage model yet.",
                "Peak and lowest capital are read from Hedge-owned cycle equity timeline snapshots.",
                "This replay does not modify Futures runtime files.",
            ],
        }

    def build_and_store(self) -> Path:
        report = self.build_report()
        self._write_runtime_ledgers(report=report)
        generated_date = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        # This is a virtual compatibility path. The daily summary is stored in
        # SQLite and JSON is produced only through an explicit export.
        return daily_json_path(HEDGE_DAILY_SUMMARIES_FAMILY, generated_date)

    def _write_runtime_ledgers(self, *, report: dict[str, Any]) -> None:
        generated_date = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        source_counts = report.get("source_counts") or {}
        final_snapshot = report.get("final_snapshot") or {}
        decision_summary = report.get("decision_summary") or {}
        daily_summary = {
            "date": generated_date,
            "system": "futures_hedge",
            "mode": report.get("mode"),
            "generated_at": report.get("generated_at"),
            "opened_futures_events": source_counts.get("opened_futures_events", 0),
            "hedge_entries_accepted": source_counts.get("hedge_entries_accepted", 0),
            "hedge_entries_skipped": source_counts.get("hedge_entries_skipped", 0),
            "reset_count": final_snapshot.get("reset_count", 0),
            "starting_capital_usdt": final_snapshot.get("starting_capital_usdt"),
            "cash_usdt": final_snapshot.get("cash_usdt"),
            "equity_usdt": final_snapshot.get("equity_usdt"),
            "estimated_close_equity_usdt": final_snapshot.get("estimated_close_equity_usdt"),
            "available_capital_usdt": final_snapshot.get("available_capital_usdt"),
            "used_margin_usdt": final_snapshot.get("used_margin_usdt"),
            "unrealized_pnl_usdt": final_snapshot.get("unrealized_pnl_usdt"),
            "realized_pnl_usdt": final_snapshot.get("realized_pnl_usdt"),
            "total_fees_usdt": final_snapshot.get("total_fees_usdt"),
            "final_mark_price": report.get("final_mark_price"),
            "max_drawdown_pct": report.get("max_drawdown_pct"),
            "peak_equity_usdt": report.get("peak_equity_usdt"),
            "lowest_equity_usdt": report.get("lowest_equity_usdt"),
            "max_open_profit_usdt": report.get("max_open_profit_usdt"),
            "max_runup_pct": report.get("max_runup_pct"),
            "can_open_next_entry": decision_summary.get("can_open_next_entry"),
            "entries_until_capital_exhaustion_estimate": decision_summary.get(
                "entries_until_capital_exhaustion_estimate"
            ),
            "net_exposure_side": decision_summary.get("net_exposure_side"),
            "net_exposure_usdt": decision_summary.get("net_exposure_usdt"),
            "margin_used_pct": decision_summary.get("margin_used_pct"),
            "worst_basket_roe_pct": decision_summary.get("worst_basket_roe_pct"),
            "distance_to_danger_zone_pct": decision_summary.get("distance_to_danger_zone_pct"),
            "side_imbalance_side": decision_summary.get("side_imbalance_side"),
            "side_imbalance_ratio": decision_summary.get("side_imbalance_ratio"),
            "liquidation_risk": decision_summary.get("liquidation_risk"),
            "long_basket": final_snapshot.get("long_basket"),
            "short_basket": final_snapshot.get("short_basket"),
        }
        replace_family_rows(HEDGE_ENTRIES_FAMILY, list(report.get("accepted_entries") or []))
        replace_family_rows(HEDGE_BASKET_SNAPSHOTS_FAMILY, list(report.get("basket_snapshots") or []))
        replace_family_rows(HEDGE_EQUITY_TIMELINE_FAMILY, list(report.get("equity_points") or []))
        reset_events = list(report.get("reset_events") or [])
        reset_paths = replace_family_rows(HEDGE_RESET_EVENTS_FAMILY, reset_events)
        if not reset_paths:
            write_json(daily_json_path(HEDGE_RESET_EVENTS_FAMILY, generated_date), [])
        replace_family_rows(HEDGE_DAILY_SUMMARIES_FAMILY, [daily_summary])

    def _load_entry_triggers(self) -> list[dict[str, Any]]:
        rows = [
            row for row in load_futures_family_rows_all(settings.SOURCE_POSITION_EVENTS_FAMILY)
            if str(row.get("event") or "").upper() == "OPENED"
        ]
        rows.sort(key=self._timestamp_ms)
        return rows

    def _latest_mark_price(self, triggers: list[dict[str, Any]]) -> float:
        candles = self._load_candles()
        for candle in reversed(candles):
            close = self._as_float(candle.get("close"))
            if close > 0:
                return close
        if not triggers:
            return 0.0
        return self._as_float(triggers[-1].get("entry_price"))

    def _build_decision_summary(self, *, final_snapshot: dict[str, Any], latest_mark: float) -> dict[str, Any]:
        profile = self._profile
        available = FuturesHedgeReplayService._as_float(final_snapshot.get("available_capital_usdt"))
        required = profile.position_margin_usdt + (profile.position_notional_usdt * profile.entry_fee_pct)
        long_notional = FuturesHedgeReplayService._as_float(
            (final_snapshot.get("long_basket") or {}).get("notional_usdt")
        )
        short_notional = FuturesHedgeReplayService._as_float(
            (final_snapshot.get("short_basket") or {}).get("notional_usdt")
        )
        net_exposure = long_notional - short_notional
        long_basket = final_snapshot.get("long_basket") or {}
        short_basket = final_snapshot.get("short_basket") or {}
        if net_exposure > 0:
            net_side = "LONG"
        elif net_exposure < 0:
            net_side = "SHORT"
        else:
            net_side = "FLAT"
        return {
            "can_open_next_entry": available >= required,
            "next_entry_required_capital_usdt": round(required, 4),
            "available_capital_usdt": round(available, 2),
            "entries_until_capital_exhaustion_estimate": int(available // required) if required > 0 else 0,
            "net_exposure_side": net_side,
            "net_exposure_usdt": round(abs(net_exposure), 2),
            "long_notional_usdt": round(long_notional, 2),
            "short_notional_usdt": round(short_notional, 2),
            "margin_used_pct": self._margin_used_pct(final_snapshot=final_snapshot),
            "worst_basket_roe_pct": self._worst_basket_roe_pct(
                long_roe_pct=self._as_float(long_basket.get("roe_pct")),
                short_roe_pct=self._as_float(short_basket.get("roe_pct")),
            ),
            "distance_to_danger_zone_pct": self._distance_to_danger_zone_pct(
                long_roe_pct=self._as_float(long_basket.get("roe_pct")),
                short_roe_pct=self._as_float(short_basket.get("roe_pct")),
            ),
            "side_imbalance_side": self._side_imbalance_side(
                long_notional=long_notional,
                short_notional=short_notional,
            ),
            "side_imbalance_ratio": self._side_imbalance_ratio(
                long_notional=long_notional,
                short_notional=short_notional,
            ),
            "liquidation_risk": self._liquidation_risk_label(
                long_roe_pct=self._as_float(long_basket.get("roe_pct")),
                short_roe_pct=self._as_float(short_basket.get("roe_pct")),
            ),
            "if_closed_now_equity_usdt": final_snapshot.get("estimated_close_equity_usdt"),
            "if_closed_now_return_pct": final_snapshot.get("estimated_close_return_pct"),
            "reset_rule": "Reset only when the next Hedge entry cannot be opened from Hedge capital.",
            "mark_price": round(float(latest_mark or 0.0), 2),
        }

    def _build_current_equity_point(
        self,
        *,
        final_snapshot: dict[str, Any],
        decision_summary: dict[str, Any],
        latest_mark: float,
        accepted_entries_count: int,
        skipped_entries_count: int,
    ) -> dict[str, Any]:
        timestamp_ms, time_readable = self._latest_timeline_timestamp()
        return {
            "point_type": "cycle_snapshot",
            "timestamp_ms": timestamp_ms,
            "time_readable": time_readable,
            "mark_price": round(latest_mark, 2),
            "equity_usdt": final_snapshot.get("equity_usdt"),
            "estimated_close_equity_usdt": final_snapshot.get("estimated_close_equity_usdt"),
            "available_capital_usdt": final_snapshot.get("available_capital_usdt"),
            "used_margin_usdt": final_snapshot.get("used_margin_usdt"),
            "unrealized_pnl_usdt": final_snapshot.get("unrealized_pnl_usdt"),
            "realized_pnl_usdt": final_snapshot.get("realized_pnl_usdt"),
            "total_fees_usdt": final_snapshot.get("total_fees_usdt"),
            "reset_count": final_snapshot.get("reset_count", 0),
            "hedge_entries_accepted": accepted_entries_count,
            "hedge_entries_skipped": skipped_entries_count,
            "net_exposure_side": decision_summary.get("net_exposure_side"),
            "net_exposure_usdt": decision_summary.get("net_exposure_usdt"),
            "side_imbalance_side": decision_summary.get("side_imbalance_side"),
            "side_imbalance_ratio": decision_summary.get("side_imbalance_ratio"),
            "margin_used_pct": decision_summary.get("margin_used_pct"),
            "worst_basket_roe_pct": decision_summary.get("worst_basket_roe_pct"),
            "distance_to_danger_zone_pct": decision_summary.get("distance_to_danger_zone_pct"),
            "liquidation_risk": decision_summary.get("liquidation_risk"),
        }

    def _merged_cycle_equity_points(self, current_point: dict[str, Any]) -> list[dict[str, Any]]:
        cycle_points = [
            row for row in load_hedge_family_rows_all(HEDGE_EQUITY_TIMELINE_FAMILY)
            if row.get("point_type") == "cycle_snapshot"
            and self._as_float(row.get("mark_price")) > 0
        ]
        merged: dict[str, dict[str, Any]] = {}
        candidate_points = [*cycle_points]
        if self._as_float(current_point.get("mark_price")) > 0:
            candidate_points.append(current_point)
        for row in candidate_points:
            key = str(row.get("timestamp_ms") or "")
            if not key:
                continue
            merged[key] = row
        return [merged[key] for key in sorted(merged, key=lambda value: int(value))]

    def _latest_timeline_timestamp(self) -> tuple[int, str]:
        for candle in reversed(self._load_candles()):
            timestamp_ms = self._candle_timestamp_ms(candle)
            if timestamp_ms <= 0:
                continue
            time_readable = str(candle.get("close_time_readable") or candle.get("time_readable") or "")
            if not time_readable:
                time_readable = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M:%SZ")
            return timestamp_ms, time_readable
        now = datetime.now(tz=UTC)
        return int(now.timestamp() * 1000), now.strftime("%Y-%m-%d %H:%M:%SZ")

    def _margin_used_pct(self, *, final_snapshot: dict[str, Any]) -> float:
        equity = self._as_float(final_snapshot.get("equity_usdt"))
        used_margin = self._as_float(final_snapshot.get("used_margin_usdt"))
        if equity <= 0:
            return 0.0
        return round(used_margin / equity * 100.0, 4)

    @staticmethod
    def _worst_basket_roe_pct(*, long_roe_pct: float, short_roe_pct: float) -> float:
        return round(min(long_roe_pct, short_roe_pct, 0.0), 4)

    @staticmethod
    def _distance_to_danger_zone_pct(*, long_roe_pct: float, short_roe_pct: float) -> float:
        worst_roe = min(long_roe_pct, short_roe_pct, 0.0)
        return round(max(0.0, 80.0 + worst_roe), 4)

    @staticmethod
    def _side_imbalance_side(*, long_notional: float, short_notional: float) -> str:
        if long_notional <= 0 and short_notional <= 0:
            return "FLAT"
        if long_notional > short_notional:
            return "LONG"
        if short_notional > long_notional:
            return "SHORT"
        return "BALANCED"

    @staticmethod
    def _side_imbalance_ratio(*, long_notional: float, short_notional: float) -> float:
        larger = max(long_notional, short_notional)
        smaller = min(long_notional, short_notional)
        if larger <= 0:
            return 0.0
        if smaller <= 0:
            return 999.0
        return round(larger / smaller, 4)

    @staticmethod
    def _liquidation_risk_label(*, long_roe_pct: float, short_roe_pct: float) -> str:
        worst_roe = min(long_roe_pct, short_roe_pct, 0.0)
        if worst_roe <= -80.0:
            return "HIGH"
        if worst_roe <= -50.0:
            return "MEDIUM"
        if worst_roe <= -25.0:
            return "ELEVATED"
        return "LOW"

    @staticmethod
    def _load_candles() -> list[dict[str, Any]]:
        return read_market_series_safely(
            venue="binance",
            asset_class="crypto",
            market_type="futures",
            dataset="candles",
            symbol=settings.DEFAULT_SYMBOL,
            timeframe=settings.DEFAULT_TIMEFRAME,
        )

    @staticmethod
    def _max_drawdown_pct(*, points: list[dict[str, Any]], starting_capital: float) -> float:
        if starting_capital <= 0:
            return 0.0
        max_drawdown = 0.0
        for point in points:
            equity = FuturesHedgeReplayService._as_float(point.get("equity_usdt"))
            drawdown = max(0.0, (starting_capital - equity) / starting_capital * 100.0)
            max_drawdown = max(max_drawdown, drawdown)
        return round(max_drawdown, 4)

    @staticmethod
    def _peak_equity_usdt(points: list[dict[str, Any]]) -> float:
        peak = 0.0
        for point in points:
            equity = FuturesHedgeReplayService._as_float(point.get("equity_usdt"))
            if equity > peak:
                peak = equity
        return round(peak, 2)

    @staticmethod
    def _lowest_equity_usdt(points: list[dict[str, Any]], *, fallback: float) -> float:
        lowest: float | None = None
        for point in points:
            equity = FuturesHedgeReplayService._as_float(point.get("equity_usdt"))
            if equity <= 0:
                continue
            lowest = equity if lowest is None else min(lowest, equity)
        return round(lowest if lowest is not None else fallback, 2)

    @staticmethod
    def _max_open_profit_usdt(*, peak_equity: float, starting_capital: float) -> float:
        return round(max(0.0, peak_equity - starting_capital), 2)

    @staticmethod
    def _max_runup_pct(*, max_open_profit: float, starting_capital: float) -> float:
        if starting_capital <= 0:
            return 0.0
        return round(max_open_profit / starting_capital * 100.0, 4)

    @staticmethod
    def _timestamp_ms(row: dict[str, Any]) -> int:
        try:
            return int(row.get("timestamp_ms") or row.get("opened_at_ms") or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _candle_timestamp_ms(row: dict[str, Any]) -> int:
        try:
            return int(row.get("close_time") or row.get("timestamp") or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _as_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0
