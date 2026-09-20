"""Metrics aggregation for Futures simulation output."""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from typing import Any

from platform_v2.futures.config import ExecutionProfile
from platform_v2.shared.backend.runtime_store.futures import POSITION_EVENTS_FAMILY

from .common import coerce_int, utc_now_ms
from .runtime_store import FuturesSimulationRuntimeStore


class FuturesMetricsService:
    def __init__(self, runtime_store: FuturesSimulationRuntimeStore | None = None) -> None:
        self._runtime_store = runtime_store or FuturesSimulationRuntimeStore()

    def build(
        self,
        *,
        state: dict[str, Any],
        profile: ExecutionProfile,
        date_iso: str,
        latest_close: float,
        latest_time: str,
        signal_side: str,
        open_positions_payload: list[dict[str, Any]],
    ) -> dict[str, Any]:
        stats = state["stats"]
        total_net_pnl = float(stats.get("total_net_pnl", 0.0))
        total_positions = int(stats.get("total_positions", 0))
        closed_positions_count = int(stats.get("closed_positions", 0))
        open_positions = len(open_positions_payload)
        # Spot-parity exposure metric tracks deployed capital (margin), not leveraged notional.
        active_exposure = sum(
            float(position.get("margin_usdt", 0.0) or 0.0)
            for position in open_positions_payload
        )
        reserved_capital = sum(
            float(position.get("margin_usdt", 0.0) or 0.0)
            for position in open_positions_payload
        )
        open_entry_fee = sum(
            float(position.get("entry_fee_paid", 0.0) or 0.0)
            for position in open_positions_payload
        )
        unrealized_pnl = 0.0
        for position in open_positions_payload:
            notional = float(position.get("notional_usdt") or 0.0)
            unrealized_pnl += self._unrealized_pct(position=position, latest_close=latest_close) * notional
        available_balance = profile.starting_balance + total_net_pnl - reserved_capital - open_entry_fee
        equity = available_balance + reserved_capital + unrealized_pnl
        net_return_pct = (
            (equity - profile.starting_balance) / profile.starting_balance * 100.0
            if profile.starting_balance > 0
            else 0.0
        )
        return_bps = net_return_pct * 100.0
        started_at_ms = coerce_int(state.get("started_at_ms"))
        elapsed_days = 0.0
        if started_at_ms > 0:
            elapsed_days = max((utc_now_ms() - started_at_ms) / 86_400_000.0, 1 / 24)
        annualized_return = (net_return_pct * (365.0 / elapsed_days)) if elapsed_days > 0 else 0.0
        closed_rows = [
            row
            for row in self._runtime_store.load_family_rows_all(family_name=POSITION_EVENTS_FAMILY)
            if str(row.get("event") or "").upper() == "CLOSED"
        ]
        closed_net_pnls = [self._as_float(row.get("net_pnl")) for row in closed_rows]
        closed_net_pnls = [value for value in closed_net_pnls if value is not None]
        wins = [value for value in closed_net_pnls if value > 0]
        win_rate = ((len(wins) / len(closed_net_pnls)) * 100.0) if closed_net_pnls else 0.0
        avg_net_per_trade = (
            sum(closed_net_pnls) / len(closed_net_pnls) if closed_net_pnls else 0.0
        )
        best_trade = max(closed_net_pnls) if closed_net_pnls else 0.0
        worst_trade = min(closed_net_pnls) if closed_net_pnls else 0.0
        direction_outcomes = self._direction_outcome_metrics(
            position_rows=self._runtime_store.load_family_rows_all(family_name=POSITION_EVENTS_FAMILY)
        )

        signals_all = self._runtime_store.load_family_rows_all(family_name="futures_signals")
        denied_all = self._runtime_store.load_family_rows_all(family_name="futures_denied_entries")
        today_signals = self._runtime_store.load_family_rows(
            family_name="futures_signals",
            date_iso=date_iso,
        )
        today_denied = self._runtime_store.load_family_rows(
            family_name="futures_denied_entries",
            date_iso=date_iso,
        )
        long_signals_all = [
            row for row in signals_all if str(row.get("side") or "").upper() in {"LONG", "BUY"}
        ]
        short_signals_all = [
            row for row in signals_all if str(row.get("side") or "").upper() in {"SHORT", "SELL"}
        ]
        no_signal_all = [
            row for row in signals_all if str(row.get("side") or "").upper() == "NO_SIGNAL"
        ]
        today_long_signals = [
            row for row in today_signals if str(row.get("side") or "").upper() in {"LONG", "BUY"}
        ]
        today_short_signals = [
            row for row in today_signals if str(row.get("side") or "").upper() in {"SHORT", "SELL"}
        ]
        today_no_signal = [
            row for row in today_signals if str(row.get("side") or "").upper() == "NO_SIGNAL"
        ]
        strategy_start = self._earliest_signal_timestamp_text(signals_all)
        elapsed = self._elapsed_since_text(strategy_start)
        peak_capital, lowest_capital = self._capital_extremes(
            starting_balance=profile.starting_balance,
            closed_rows=closed_rows,
        )
        signal_to_trade_conversion = (
            (total_positions / (len(long_signals_all) + len(short_signals_all)) * 100.0)
            if (len(long_signals_all) + len(short_signals_all)) > 0
            else 0.0
        )

        return {
            "date": datetime.now(tz=UTC).date().isoformat(),
            "datetime": latest_time,
            "market": "futures",
            "mode": profile.mode,
            "symbol": profile.symbol,
            "timeframe": profile.timeframe,
            "leverage": profile.leverage,
            "margin_mode": profile.margin_mode,
            "order_size_usdt": profile.order_size_usdt,
            "starting_capital": round(profile.starting_balance, 2),
            "available_balance": round(available_balance, 2),
            "reserved_capital": round(reserved_capital, 2),
            "equity": round(equity, 2),
            "last_capital": round(equity, 2),
            "total_net_pnl": round(total_net_pnl, 2),
            "gross_pnl": round(float(stats.get("total_gross_pnl", 0.0)), 2),
            "total_gross_pnl": round(float(stats.get("total_gross_pnl", 0.0)), 2),
            "fees_paid": round(float(stats.get("total_fees_paid", 0.0)), 2),
            "total_fees_paid": round(float(stats.get("total_fees_paid", 0.0)), 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "active_exposure": round(active_exposure, 2),
            "return_bps": round(return_bps, 2),
            "net_return_pct": round(net_return_pct, 2),
            "annualized_return": round(annualized_return, 2),
            "win_rate": round(win_rate, 2),
            "avg_net_per_trade": round(avg_net_per_trade, 2),
            "best_trade": round(best_trade, 2),
            "worst_trade": round(worst_trade, 2),
            **direction_outcomes,
            "peak_capital": round(peak_capital, 2),
            "lowest_capital": round(lowest_capital, 2),
            "total_positions": total_positions,
            "closed_positions": closed_positions_count,
            "open_positions": open_positions,
            "tp_hits": int(stats.get("tp_hits", 0)),
            "sl_hits": int(stats.get("sl_hits", 0)),
            "profit_lock_hits": int(stats.get("profit_lock_hits", 0)),
            "force_close_events": int(stats.get("force_close_events", 0)),
            "force_closes_by_reason": dict(stats.get("force_closes_by_reason") or {}),
            "total_signals_since_start": len(signals_all),
            "buy_signals_since_start": len(long_signals_all),
            "long_signals_since_start": len(long_signals_all),
            "short_signals_since_start": len(short_signals_all),
            "no_signal_since_start": len(no_signal_all),
            "denied_entries_since_start": len(denied_all),
            "skipped_entries": len(denied_all),
            "trades_opened_since_start": total_positions,
            "signal_to_trade_conversion": round(signal_to_trade_conversion, 2),
            "today_total_signals": len(today_signals),
            "today_buy_signals": len(today_long_signals),
            "today_long_signals": len(today_long_signals),
            "today_short_signals": len(today_short_signals),
            "today_no_signal": len(today_no_signal),
            "today_denied_entries": len(today_denied),
            "strategy_start": strategy_start,
            "elapsed": elapsed,
            "last_signal": signal_side,
            "position_event": state.get("last_position_event", "NO_EVENT"),
        }

    def build_minimal(self, *, profile: ExecutionProfile) -> dict[str, Any]:
        return {
            "date": datetime.now(tz=UTC).date().isoformat(),
            "datetime": datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "market": "futures",
            "mode": profile.mode,
            "symbol": profile.symbol,
            "timeframe": profile.timeframe,
            "leverage": profile.leverage,
            "margin_mode": profile.margin_mode,
            "order_size_usdt": profile.order_size_usdt,
            "starting_capital": round(profile.starting_balance, 2),
            "available_balance": round(profile.starting_balance, 2),
            "reserved_capital": 0.0,
            "equity": round(profile.starting_balance, 2),
            "last_capital": round(profile.starting_balance, 2),
            "total_net_pnl": 0.0,
            "gross_pnl": 0.0,
            "total_gross_pnl": 0.0,
            "fees_paid": 0.0,
            "total_fees_paid": 0.0,
            "unrealized_pnl": 0.0,
            "active_exposure": 0.0,
            "return_bps": 0.0,
            "net_return_pct": 0.0,
            "annualized_return": 0.0,
            "win_rate": 0.0,
            "avg_net_per_trade": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "long_positions": 0,
            "short_positions": 0,
            "long_net_pnl": 0.0,
            "short_net_pnl": 0.0,
            "best_direction": "Flat",
            "best_direction_kind": "generic",
            "peak_capital": round(profile.starting_balance, 2),
            "lowest_capital": round(profile.starting_balance, 2),
            "total_positions": 0,
            "closed_positions": 0,
            "open_positions": 0,
            "tp_hits": 0,
            "sl_hits": 0,
            "profit_lock_hits": 0,
            "force_close_events": 0,
            "force_closes_by_reason": {},
            "total_signals_since_start": 0,
            "buy_signals_since_start": 0,
            "no_signal_since_start": 0,
            "denied_entries_since_start": 0,
            "skipped_entries": 0,
            "trades_opened_since_start": 0,
            "signal_to_trade_conversion": 0.0,
            "today_total_signals": 0,
            "today_buy_signals": 0,
            "today_no_signal": 0,
            "today_denied_entries": 0,
            "strategy_start": "N/A",
            "elapsed": "0 days, 00:00",
            "last_signal": "NO_SIGNAL",
            "position_event": "NO_DATA",
        }

    def _earliest_signal_timestamp_text(self, signals_all: list[dict[str, Any]]) -> str:
        timestamp_values = [
            coerce_int(row.get("timestamp_ms"))
            for row in signals_all
            if coerce_int(row.get("timestamp_ms")) > 0
        ]
        if not timestamp_values:
            return "N/A"
        first_ts_ms = min(timestamp_values)
        return datetime.fromtimestamp(first_ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    @staticmethod
    def _elapsed_since_text(start_text: str) -> str:
        if start_text == "N/A":
            return "0 days, 00:00"
        try:
            started_at = datetime.strptime(start_text, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
        except ValueError:
            return "0 days, 00:00"
        now_utc = datetime.now(tz=timezone.utc)
        if now_utc <= started_at:
            return "0 days, 00:00"
        delta = now_utc - started_at
        total_seconds = int(delta.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{days} days, {hours:02d}:{minutes:02d}"

    def _capital_extremes(
        self,
        *,
        starting_balance: float,
        closed_rows: list[dict[str, Any]],
    ) -> tuple[float, float]:
        capital = float(starting_balance)
        peak = capital
        lowest = capital
        ordered_rows = sorted(
            closed_rows,
            key=lambda row: (
                coerce_int(row.get("timestamp_ms")),
                str(row.get("position_id") or ""),
            ),
        )
        for row in ordered_rows:
            net_pnl = self._as_float(row.get("net_pnl"))
            if net_pnl is None:
                continue
            capital += net_pnl
            peak = max(peak, capital)
            lowest = min(lowest, capital)
        return peak, lowest

    def _direction_outcome_metrics(self, *, position_rows: list[dict[str, Any]]) -> dict[str, Any]:
        opened_by_id: dict[str, dict[str, Any]] = {}
        closed_by_id: dict[str, dict[str, Any]] = {}
        for row in sorted(position_rows, key=self._position_sort_key):
            position_id = str(row.get("position_id") or "").strip()
            if not position_id:
                continue
            event = str(row.get("event") or "").upper()
            if event == "OPENED":
                opened_by_id[position_id] = row
            elif event == "CLOSED":
                closed_by_id[position_id] = row

        direction_totals = {
            "LONG": {"positions": 0, "net_pnl": 0.0},
            "SHORT": {"positions": 0, "net_pnl": 0.0},
        }
        for row in opened_by_id.values():
            direction = self._position_direction(row)
            if direction in direction_totals:
                direction_totals[direction]["positions"] += 1

        for row in closed_by_id.values():
            direction = self._position_direction(row)
            if direction not in direction_totals:
                continue
            net_pnl = self._as_float(row.get("net_pnl")) or 0.0
            direction_totals[direction]["net_pnl"] = round(
                float(direction_totals[direction]["net_pnl"]) + net_pnl,
                2,
            )

        long_net = float(direction_totals["LONG"]["net_pnl"])
        short_net = float(direction_totals["SHORT"]["net_pnl"])
        if long_net > short_net:
            best_direction = "LONG"
            best_direction_kind = "tp" if long_net > 0 else "generic"
        elif short_net > long_net:
            best_direction = "SHORT"
            best_direction_kind = "tp" if short_net > 0 else "generic"
        else:
            best_direction = "Flat"
            best_direction_kind = "generic"

        return {
            "long_positions": int(direction_totals["LONG"]["positions"]),
            "short_positions": int(direction_totals["SHORT"]["positions"]),
            "long_net_pnl": round(long_net, 2),
            "short_net_pnl": round(short_net, 2),
            "best_direction": best_direction,
            "best_direction_kind": best_direction_kind,
        }

    @staticmethod
    def _position_sort_key(row: dict[str, Any]) -> tuple[int, str, str]:
        return (
            coerce_int(row.get("timestamp_ms")),
            str(row.get("position_id") or ""),
            str(row.get("event") or ""),
        )

    @staticmethod
    def _position_direction(row: dict[str, Any]) -> str:
        side = str(row.get("selected_direction") or row.get("side") or "").upper()
        if side == "BUY":
            return "LONG"
        if side == "SELL":
            return "SHORT"
        if side in {"LONG", "SHORT"}:
            return side
        return "LONG"

    @staticmethod
    def _unrealized_pct(*, position: dict[str, Any], latest_close: float) -> float:
        entry = float(position.get("entry_price") or 0.0)
        if entry <= 0 or latest_close <= 0:
            return 0.0
        side = str(position.get("side") or "LONG").upper()
        if side in {"SHORT", "SELL"}:
            return (entry - latest_close) / entry
        return (latest_close - entry) / entry

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
