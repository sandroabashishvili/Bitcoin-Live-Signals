"""File: summary_service.py
Folder: platform_v2/spot/services/metrics_system
Created date: 2026-04-08
Last updated date: 2026-04-08
Author: Codex
Purpose: Build and persist backend-computed portfolio and strategy summary metrics.
"""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

from platform_v2.spot.config import settings
from platform_v2.spot.domain.models.position import ExitReason
from platform_v2.spot.domain.models.position import PositionRecord
from platform_v2.shared.backend.runtime_store.spot import (
    DENIED_ENTRIES_FAMILY,
    FORCE_CLOSES_FAMILY,
    METRICS_FAMILY,
    SIGNALS_FAMILY,
    load_family_rows,
    load_family_rows_all,
    store_runtime_snapshot,
)
from platform_v2.spot.services.account.fee_service import FeeService
from platform_v2.spot.services.account.position_state_service import PositionStateService


class MetricsSummaryService:
    """Compute summary metrics from latest position state and persist them."""

    def __init__(self, position_state_service: PositionStateService | None = None) -> None:
        self._position_state_service = position_state_service or PositionStateService()

    def build_summary(
        self,
        *,
        date_iso: str,
        starting_balance: float = settings.DEFAULT_STARTING_BALANCE,
        lookback_days: int | None = None,
    ) -> dict[str, object]:
        """Build a backend-computed summary metrics payload."""

        positions = self._position_state_service.load_latest_positions(
            lookback_days=lookback_days,
            as_of_date_iso=date_iso,
        )
        open_positions = [position for position in positions if position.is_open]
        closed_positions = [position for position in positions if position.is_closed]

        reserved_capital = sum(position.execution.position_size for position in open_positions)
        unrealized_pnl = sum(float(position.unrealized_pnl or 0.0) for position in open_positions)
        open_entry_fees = FeeService.open_entry_fees_total(open_positions)
        total_net_pnl = sum(FeeService.net_pnl_value(position) for position in closed_positions)
        available_balance = starting_balance + total_net_pnl - reserved_capital - open_entry_fees
        equity = available_balance + reserved_capital + unrealized_pnl
        last_capital = equity
        wins = sum(1 for position in closed_positions if FeeService.net_pnl_value(position) > 0)
        win_rate = (wins / len(closed_positions) * 100.0) if closed_positions else 0.0
        tp_hits = sum(1 for position in closed_positions if position.exit_reason == ExitReason.TP_HIT)
        sl_hits = sum(1 for position in closed_positions if position.exit_reason == ExitReason.SL_HIT)
        force_close_events = sum(1 for position in closed_positions if position.was_force_closed)
        avg_net = (total_net_pnl / len(closed_positions)) if closed_positions else 0.0
        return_bps = ((last_capital - starting_balance) / starting_balance * 10000.0) if starting_balance else 0.0
        net_return_pct = return_bps / 100.0
        active_exposure = reserved_capital
        skipped_entries = self._count_family_rows(DENIED_ENTRIES_FAMILY)
        force_closes_by_reason = self._count_reasons_in_family(FORCE_CLOSES_FAMILY)
        strategy_start = self._earliest_signal_timestamp_text()
        elapsed = self._elapsed_since_text(strategy_start)
        elapsed_days = self._elapsed_days(strategy_start)
        annualized_return = self._annualized_return_pct(
            starting_balance=starting_balance,
            last_capital=last_capital,
            elapsed_days=elapsed_days,
        )
        gross_pnl = sum(FeeService.gross_pnl_value(position) for position in closed_positions)
        closed_fees_paid = FeeService.realized_fees_total(closed_positions)
        fees_paid = closed_fees_paid + open_entry_fees
        best_trade = max((FeeService.net_pnl_value(position) for position in closed_positions), default=0.0)
        worst_trade = min((FeeService.net_pnl_value(position) for position in closed_positions), default=0.0)
        today_signal_counts = self._same_day_signal_counts(date_iso)
        today_denied_entries = self._same_day_denied_entry_count(date_iso)
        cumulative_signal_counts = self._cumulative_signal_counts()
        cumulative_denied_entries = self._cumulative_denied_entry_count()
        trades_opened_since_start = len(positions)
        signal_to_trade_conversion = (
            (trades_opened_since_start / cumulative_signal_counts["buy_signals"]) * 100.0
            if cumulative_signal_counts["buy_signals"] > 0
            else 0.0
        )
        peak_capital, lowest_capital = self._capital_extremes(
            starting_balance=starting_balance,
            closed_positions=closed_positions,
        )
        current_strategy_closed = [p for p in closed_positions if p.strategy_version == settings.STRATEGY_VERSION]

        return {
            "active_strategy_version": settings.STRATEGY_VERSION,
            "current_strategy_closed_positions": len(current_strategy_closed),
            "current_strategy_net_pnl": round(sum(FeeService.net_pnl_value(p) for p in current_strategy_closed), 2),
            "date": date_iso,
            "datetime": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "starting_capital": round(starting_balance, 2),
            "available_balance": round(available_balance, 2),
            "reserved_capital": round(reserved_capital, 2),
            "equity": round(equity, 2),
            "last_capital": round(last_capital, 2),
            "total_net_pnl": round(total_net_pnl, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "return_bps": round(return_bps, 2),
            "net_return_pct": round(net_return_pct, 2),
            "annualized_return": round(annualized_return, 2),
            "gross_pnl": round(gross_pnl, 2),
            "fees_paid": round(fees_paid, 2),
            "best_trade": round(best_trade, 2),
            "worst_trade": round(worst_trade, 2),
            "peak_capital": round(peak_capital, 2),
            "lowest_capital": round(lowest_capital, 2),
            "active_exposure": round(active_exposure, 2),
            "total_signals_since_start": cumulative_signal_counts["total_signals"],
            "buy_signals_since_start": cumulative_signal_counts["buy_signals"],
            "no_signal_since_start": cumulative_signal_counts["no_signal"],
            "denied_entries_since_start": cumulative_denied_entries,
            "trades_opened_since_start": trades_opened_since_start,
            "signal_to_trade_conversion": round(signal_to_trade_conversion, 2),
            "today_total_signals": today_signal_counts["total_signals"],
            "today_buy_signals": today_signal_counts["buy_signals"],
            "today_no_signal": today_signal_counts["no_signal"],
            "today_denied_entries": today_denied_entries,
            "open_positions": len(open_positions),
            "closed_positions": len(closed_positions),
            "total_positions": len(positions),
            "tp_hits": tp_hits,
            "sl_hits": sl_hits,
            "profit_lock_hits": sum(p.exit_reason == ExitReason.PROFIT_LOCK_HIT for p in closed_positions),
            "strategy_versions": {
                version: {
                    "closed_positions": len(group),
                    "net_pnl": round(sum(FeeService.net_pnl_value(p) for p in group), 2),
                    "wins": sum(FeeService.net_pnl_value(p) > 0 for p in group),
                }
                for version in sorted({p.strategy_version for p in closed_positions})
                for group in [[p for p in closed_positions if p.strategy_version == version]]
            },
            "force_close_events": force_close_events,
            "force_closes_by_reason": force_closes_by_reason,
            "win_rate": round(win_rate, 2),
            "avg_net_per_trade": round(avg_net, 2),
            "skipped_entries": skipped_entries,
            "strategy_start": strategy_start,
            "elapsed": elapsed,
        }

    def build_and_store(
        self,
        *,
        date_iso: str,
        starting_balance: float = settings.DEFAULT_STARTING_BALANCE,
        lookback_days: int | None = None,
    ) -> Path:
        """Build summary metrics and store them in the metrics family."""

        summary = self.build_summary(
            date_iso=date_iso,
            starting_balance=starting_balance,
            lookback_days=lookback_days,
        )
        return store_runtime_snapshot(METRICS_FAMILY, date_iso, summary)

    def _count_family_rows(self, family_name: str) -> int:
        """Count all rows across one runtime data family."""
        return len(load_family_rows_all(family_name))

    def _count_reasons_in_family(self, family_name: str) -> dict[str, int]:
        """Return a count breakdown by `reason` field for one runtime family."""

        counts: dict[str, int] = {}
        for row in load_family_rows_all(family_name):
            reason = str(row.get("reason") or "unknown")
            counts[reason] = counts.get(reason, 0) + 1
        return counts

    @staticmethod
    def _same_utc_date(timestamp_ms: int, date_iso: str) -> bool:
        try:
            parsed = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        except (TypeError, ValueError, OSError):
            return False
        return parsed == date_iso

    def _same_day_signal_counts(self, date_iso: str) -> dict[str, int]:
        total_signals = 0
        buy_signals = 0
        no_signal = 0
        for row in load_family_rows(SIGNALS_FAMILY, date_iso):
            timestamp_ms = self._coerce_int(row.get("timestamp_ms"))
            if timestamp_ms is None or not self._same_utc_date(timestamp_ms, date_iso):
                continue
            total_signals += 1
            side = str(row.get("side") or "").upper()
            if side == "BUY":
                buy_signals += 1
            elif side == "NO_SIGNAL":
                no_signal += 1
        return {
            "total_signals": total_signals,
            "buy_signals": buy_signals,
            "no_signal": no_signal,
        }

    def _same_day_denied_entry_count(self, date_iso: str) -> int:
        total = 0
        for row in load_family_rows(DENIED_ENTRIES_FAMILY, date_iso):
            raw_signal = row.get("signal")
            signal = raw_signal if isinstance(raw_signal, dict) else {}
            value = signal.get("timestamp_ms", row.get("timestamp_ms"))
            timestamp_ms = self._coerce_int(value)
            if timestamp_ms is not None and self._same_utc_date(timestamp_ms, date_iso):
                total += 1
        return total

    def _cumulative_signal_counts(self) -> dict[str, int]:
        total_signals = 0
        buy_signals = 0
        no_signal = 0
        for row in load_family_rows_all(SIGNALS_FAMILY):
            total_signals += 1
            side = str(row.get("side") or "").upper()
            if side == "BUY":
                buy_signals += 1
            elif side == "NO_SIGNAL":
                no_signal += 1
        return {
            "total_signals": total_signals,
            "buy_signals": buy_signals,
            "no_signal": no_signal,
        }

    def _cumulative_denied_entry_count(self) -> int:
        return len(load_family_rows_all(DENIED_ENTRIES_FAMILY))

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _earliest_signal_timestamp_text(self) -> str:
        """Return the earliest known signal timestamp in UTC text form."""

        earliest_ms: int | None = None
        for row in load_family_rows_all(SIGNALS_FAMILY):
            value: Any = row.get("timestamp_ms")
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                continue
            if earliest_ms is None or parsed < earliest_ms:
                earliest_ms = parsed
        if earliest_ms is None:
            return "—"
        return datetime.fromtimestamp(earliest_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    @staticmethod
    def _elapsed_since_text(strategy_start: str) -> str:
        """Return elapsed wall-clock time since strategy start."""

        if strategy_start == "—":
            return "—"
        try:
            started_at = datetime.strptime(strategy_start, "%Y-%m-%d %H:%M:%S UTC").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return "—"
        now = datetime.now(tz=timezone.utc)
        if now < started_at:
            return "—"
        delta = now - started_at
        days = delta.days
        total_seconds = int(delta.total_seconds()) % 86400
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{days} days, {hours:02d}:{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _elapsed_days(strategy_start: str) -> float | None:
        """Return elapsed strategy age in fractional days."""

        if strategy_start == "—":
            return None
        try:
            started_at = datetime.strptime(strategy_start, "%Y-%m-%d %H:%M:%S UTC").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return None
        now = datetime.now(tz=timezone.utc)
        if now <= started_at:
            return None
        return (now - started_at).total_seconds() / 86400.0

    @staticmethod
    def _annualized_return_pct(
        *,
        starting_balance: float,
        last_capital: float,
        elapsed_days: float | None,
    ) -> float:
        """Compute annualized return percentage from current capital and elapsed days."""

        if starting_balance <= 0 or last_capital <= 0 or not elapsed_days or elapsed_days <= 0:
            return 0.0
        total_return = last_capital / starting_balance
        annual_factor = 365.0 / elapsed_days
        try:
            annualized = (total_return**annual_factor - 1.0) * 100.0
        except OverflowError:
            return 0.0
        return annualized

    @staticmethod
    def _timestamp_sort_key(value: str | None) -> tuple[int, str]:
        """Create a stable sortable key from readable UTC timestamps."""

        if not value:
            return (0, "")
        try:
            parsed = datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
            return (int(parsed.timestamp()), value)
        except ValueError:
            return (0, value)

    @staticmethod
    def _position_sort_timestamp(position: PositionRecord) -> str | None:
        """Return the best available readable timestamp for one position."""

        return position.closed_at or position.opened_at

    @classmethod
    def _capital_extremes(
        cls,
        *,
        starting_balance: float,
        closed_positions: list[PositionRecord],
    ) -> tuple[float, float]:
        """Compute peak and lowest capital levels from the closed-trade path."""

        equity = starting_balance
        peak = starting_balance
        lowest = starting_balance
        ordered = sorted(
            closed_positions,
            key=lambda position: cls._timestamp_sort_key(cls._position_sort_timestamp(position)),
        )
        for position in ordered:
            equity += FeeService.net_pnl_value(position)
            if equity > peak:
                peak = equity
            if equity < lowest:
                lowest = equity
        return peak, lowest
