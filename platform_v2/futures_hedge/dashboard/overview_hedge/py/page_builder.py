"""Build Futures Hedge overview page from Hedge runtime ledgers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from platform_v2.futures_hedge.config import default_profile, settings
from platform_v2.shared.backend.runtime_store.hedge import (
    HEDGE_BASKET_SNAPSHOTS_FAMILY,
    HEDGE_DAILY_SUMMARIES_FAMILY,
    HEDGE_ENTRIES_FAMILY,
    HEDGE_EQUITY_TIMELINE_FAMILY,
    load_family_rows_all,
)
from platform_v2.futures_hedge.services.replay import FuturesHedgeReplayService
from platform_v2.shared.frontend.components import normalize_generated_html

from .renderer import FuturesHedgeOverviewRenderer


class FuturesHedgeOverviewPageService:
    """Generate a static HTML Futures Hedge overview page."""

    _TARGET_DIR = Path(__file__).resolve().parents[1]
    _TARGET_PATH = _TARGET_DIR / "index.html"

    def build_and_store(self) -> Path:
        report = self._load_or_build_report_from_ledgers()
        html_text = normalize_generated_html(FuturesHedgeOverviewRenderer().render(report))
        self._TARGET_DIR.mkdir(parents=True, exist_ok=True)
        self._TARGET_PATH.write_text(html_text, encoding="utf-8")
        return self._TARGET_PATH

    def _load_or_build_report_from_ledgers(self) -> dict[str, Any]:
        entries = load_family_rows_all(HEDGE_ENTRIES_FAMILY)
        basket_snapshots = load_family_rows_all(HEDGE_BASKET_SNAPSHOTS_FAMILY)
        equity_timeline = load_family_rows_all(HEDGE_EQUITY_TIMELINE_FAMILY)
        daily_summaries = load_family_rows_all(HEDGE_DAILY_SUMMARIES_FAMILY)
        if not daily_summaries:
            return FuturesHedgeReplayService().build_report()

        latest_summary = max(daily_summaries, key=lambda row: str(row.get("date") or ""))
        if not isinstance(latest_summary.get("long_basket"), dict) or not isinstance(
            latest_summary.get("short_basket"), dict
        ):
            return FuturesHedgeReplayService().build_report()
        entries.sort(key=self._timestamp_ms, reverse=True)
        equity_history = basket_snapshots or equity_timeline
        equity_stats = self._equity_timeline_stats(equity_history)
        long_basket = latest_summary.get("long_basket") or {}
        short_basket = latest_summary.get("short_basket") or {}

        final_snapshot = {
            "cash_usdt": latest_summary.get("cash_usdt"),
            "equity_usdt": latest_summary.get("equity_usdt"),
            "estimated_close_equity_usdt": latest_summary.get("estimated_close_equity_usdt"),
            "starting_capital_usdt": latest_summary.get("starting_capital_usdt"),
            "available_capital_usdt": latest_summary.get("available_capital_usdt"),
            "used_margin_usdt": latest_summary.get("used_margin_usdt"),
            "unrealized_pnl_usdt": latest_summary.get("unrealized_pnl_usdt"),
            "realized_pnl_usdt": latest_summary.get("realized_pnl_usdt"),
            "total_fees_usdt": latest_summary.get("total_fees_usdt"),
            "reset_count": latest_summary.get("reset_count", 0),
            "long_basket": long_basket,
            "short_basket": short_basket,
        }
        return {
            "system": "futures_hedge",
            "mode": latest_summary.get("mode") or "paper_replay",
            "generated_at": latest_summary.get("generated_at"),
            "profile": default_profile().to_dict(),
            "source": {
                "entry_family": settings.SOURCE_POSITION_EVENTS_FAMILY,
                "entry_rule": "event == OPENED",
                "entry_fields_used": ["position_id", "side", "timestamp_ms", "time_readable", "entry_price"],
                "candles_source": "smartsignalhub_market_data.sqlite3 / binance futures candles",
                "source_boundary": "Futures supplies entry permission only; Hedge owns capital, sizing, leverage, margin, fees, and reset rules.",
                "dashboard_data_source": "smartsignalhub_trading.sqlite3 / hedge families",
            },
            "source_counts": {
                "opened_futures_events": latest_summary.get("opened_futures_events", len(entries)),
                "hedge_entries_accepted": latest_summary.get("hedge_entries_accepted", len(entries)),
                "hedge_entries_skipped": latest_summary.get("hedge_entries_skipped", 0),
            },
            "final_mark_price": latest_summary.get("final_mark_price"),
            "decision_summary": {
                "can_open_next_entry": latest_summary.get("can_open_next_entry"),
                "next_entry_required_capital_usdt": self._next_entry_required_capital(),
                "available_capital_usdt": latest_summary.get("available_capital_usdt"),
                "entries_until_capital_exhaustion_estimate": latest_summary.get(
                    "entries_until_capital_exhaustion_estimate"
                ),
                "net_exposure_side": latest_summary.get("net_exposure_side"),
                "net_exposure_usdt": latest_summary.get("net_exposure_usdt"),
                "margin_used_pct": latest_summary.get("margin_used_pct"),
                "worst_basket_roe_pct": latest_summary.get("worst_basket_roe_pct"),
                "distance_to_danger_zone_pct": latest_summary.get("distance_to_danger_zone_pct"),
                "side_imbalance_side": latest_summary.get("side_imbalance_side"),
                "side_imbalance_ratio": latest_summary.get("side_imbalance_ratio"),
                "liquidation_risk": latest_summary.get("liquidation_risk"),
                "if_closed_now_equity_usdt": latest_summary.get("estimated_close_equity_usdt"),
                "reset_rule": "Reset only when the next Hedge entry cannot be opened from Hedge capital.",
                "mark_price": latest_summary.get("final_mark_price"),
            },
            "final_snapshot": final_snapshot,
            "entries": entries,
            "equity_chart_rows": self._equity_chart_rows(equity_history),
            "basket_chart_rows": basket_snapshots,
            "max_drawdown_pct": equity_stats.get("max_drawdown_pct", latest_summary.get("max_drawdown_pct")),
            "peak_equity_usdt": equity_stats.get("peak_equity_usdt", latest_summary.get("peak_equity_usdt")),
            "lowest_equity_usdt": equity_stats.get("lowest_equity_usdt", latest_summary.get("lowest_equity_usdt")),
            "max_open_profit_usdt": latest_summary.get("max_open_profit_usdt"),
            "max_runup_pct": latest_summary.get("max_runup_pct"),
            "limitations": [
                "No liquidation model yet.",
                "No funding fees yet.",
                "No slippage model yet.",
                "Dashboard reads Hedge runtime/data ledgers; replay artifact is no longer the primary page source.",
            ],
        }

    @staticmethod
    def _timestamp_ms(row: dict[str, Any]) -> int:
        try:
            return int(row.get("timestamp_ms") or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _next_entry_required_capital() -> float:
        profile = default_profile()
        return round(profile.position_margin_usdt + (profile.position_notional_usdt * profile.entry_fee_pct), 4)

    @staticmethod
    def _equity_timeline_stats(rows: list[dict[str, Any]]) -> dict[str, float]:
        values = [FuturesHedgeOverviewPageService._as_float(row.get("equity_usdt")) for row in rows]
        values = [value for value in values if value > 0]
        if not values:
            return {}
        starting_capital = float(default_profile().starting_capital_usdt)
        lowest = min(values)
        peak = max(values)
        max_drawdown = 0.0
        if starting_capital > 0:
            max_drawdown = max(0.0, (starting_capital - lowest) / starting_capital * 100.0)
        return {
            "peak_equity_usdt": round(peak, 2),
            "lowest_equity_usdt": round(lowest, 2),
            "max_drawdown_pct": round(max_drawdown, 4),
        }

    @classmethod
    def _equity_chart_rows(cls, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        starting_capital = float(default_profile().starting_capital_usdt)
        chart_rows: list[dict[str, Any]] = []
        for row in rows:
            equity = cls._as_float(row.get("equity_usdt"))
            timestamp_ms = cls._timestamp_ms(row)
            if equity <= 0 or timestamp_ms <= 0:
                continue
            chart_rows.append(
                {
                    "datetime": datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).isoformat(),
                    "timestamp": row.get("time_readable"),
                    "starting_capital": starting_capital,
                    "equity": round(equity, 4),
                }
            )
        chart_rows.sort(key=lambda item: str(item.get("datetime") or ""))
        return chart_rows

    @staticmethod
    def _as_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0
