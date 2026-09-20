"""Portfolio account state for Futures Hedge replay."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platform_v2.futures_hedge.config import FuturesHedgeProfile

from .basket import HedgeBasket, HedgeEntry


@dataclass
class HedgeAccount:
    profile: FuturesHedgeProfile
    cash_usdt: float = field(init=False)
    realized_pnl_usdt: float = 0.0
    total_entry_fees_usdt: float = 0.0
    total_exit_fees_usdt: float = 0.0
    reset_count: int = 0
    skipped_entries: list[dict[str, Any]] = field(default_factory=list)
    reset_events: list[dict[str, Any]] = field(default_factory=list)
    long_basket: HedgeBasket = field(default_factory=lambda: HedgeBasket(side="LONG"))
    short_basket: HedgeBasket = field(default_factory=lambda: HedgeBasket(side="SHORT"))

    def __post_init__(self) -> None:
        self.cash_usdt = self.profile.starting_capital_usdt

    @property
    def used_margin_usdt(self) -> float:
        return self.long_basket.total_margin_usdt + self.short_basket.total_margin_usdt

    @property
    def total_fees_usdt(self) -> float:
        return self.total_entry_fees_usdt + self.total_exit_fees_usdt

    def unrealized_pnl(self, mark_price: float) -> float:
        return self.long_basket.unrealized_pnl(mark_price) + self.short_basket.unrealized_pnl(mark_price)

    def equity_usdt(self, mark_price: float) -> float:
        return self.cash_usdt + self.unrealized_pnl(mark_price)

    def available_capital_usdt(self, mark_price: float) -> float:
        return self.equity_usdt(mark_price) - self.used_margin_usdt

    def can_open(self, *, entry: HedgeEntry, mark_price: float) -> bool:
        required = entry.margin_usdt + entry.entry_fee_usdt
        return self.available_capital_usdt(mark_price) >= required

    def add_entry(self, entry: HedgeEntry) -> None:
        self.cash_usdt -= entry.entry_fee_usdt
        self.total_entry_fees_usdt += entry.entry_fee_usdt
        if entry.side == "SHORT":
            self.short_basket.add_entry(entry)
        else:
            self.long_basket.add_entry(entry)

    def should_reset(self, mark_price: float) -> bool:
        return self.used_margin_usdt > 0 and self.available_capital_usdt(mark_price) < 0

    def reset(self, *, mark_price: float, timestamp_ms: int, time_readable: str, reason: str) -> None:
        gross_pnl = self.unrealized_pnl(mark_price)
        exit_fees = self.long_basket.exit_fee_usdt(self.profile) + self.short_basket.exit_fee_usdt(self.profile)
        net_pnl = gross_pnl - exit_fees
        before_equity = self.equity_usdt(mark_price)
        self.cash_usdt += gross_pnl - exit_fees
        self.realized_pnl_usdt += net_pnl
        self.total_exit_fees_usdt += exit_fees
        self.reset_count += 1
        self.reset_events.append(
            {
                "reset_id": self.reset_count,
                "timestamp_ms": timestamp_ms,
                "time_readable": time_readable,
                "reason": reason,
                "mark_price": round(mark_price, 2),
                "gross_pnl": round(gross_pnl, 2),
                "exit_fees_usdt": round(exit_fees, 4),
                "net_pnl": round(net_pnl, 2),
                "equity_before_reset": round(before_equity, 2),
                "cash_after_reset": round(self.cash_usdt, 2),
                "long_basket": self.long_basket.snapshot(mark_price=mark_price, profile=self.profile),
                "short_basket": self.short_basket.snapshot(mark_price=mark_price, profile=self.profile),
            }
        )
        self.long_basket.clear()
        self.short_basket.clear()

    def snapshot(self, *, mark_price: float) -> dict[str, Any]:
        equity = self.equity_usdt(mark_price)
        available = self.available_capital_usdt(mark_price)
        estimated_exit_fees = self.long_basket.exit_fee_usdt(self.profile) + self.short_basket.exit_fee_usdt(
            self.profile
        )
        estimated_close_equity = equity - estimated_exit_fees
        return {
            "cash_usdt": round(self.cash_usdt, 2),
            "equity_usdt": round(equity, 2),
            "estimated_exit_fees_usdt": round(estimated_exit_fees, 4),
            "estimated_close_equity_usdt": round(estimated_close_equity, 2),
            "starting_capital_usdt": round(self.profile.starting_capital_usdt, 2),
            "net_return_pct": round(
                ((equity - self.profile.starting_capital_usdt) / self.profile.starting_capital_usdt * 100.0)
                if self.profile.starting_capital_usdt > 0
                else 0.0,
                4,
            ),
            "estimated_close_return_pct": round(
                (
                    (estimated_close_equity - self.profile.starting_capital_usdt)
                    / self.profile.starting_capital_usdt
                    * 100.0
                )
                if self.profile.starting_capital_usdt > 0
                else 0.0,
                4,
            ),
            "available_capital_usdt": round(available, 2),
            "used_margin_usdt": round(self.used_margin_usdt, 2),
            "unrealized_pnl_usdt": round(self.unrealized_pnl(mark_price), 2),
            "realized_pnl_usdt": round(self.realized_pnl_usdt, 2),
            "total_fees_usdt": round(self.total_fees_usdt, 4),
            "entry_fees_usdt": round(self.total_entry_fees_usdt, 4),
            "exit_fees_usdt": round(self.total_exit_fees_usdt, 4),
            "reset_count": self.reset_count,
            "long_basket": self.long_basket.snapshot(mark_price=mark_price, profile=self.profile),
            "short_basket": self.short_basket.snapshot(mark_price=mark_price, profile=self.profile),
        }
