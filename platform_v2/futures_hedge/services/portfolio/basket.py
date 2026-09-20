"""Basket accounting for Futures Hedge replay."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from platform_v2.futures_hedge.config import FuturesHedgeProfile


@dataclass(frozen=True)
class HedgeEntry:
    source_position_id: str
    side: str
    timestamp_ms: int
    time_readable: str
    entry_price: float
    margin_usdt: float
    notional_usdt: float
    quantity: float
    entry_fee_usdt: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_position_id": self.source_position_id,
            "side": self.side,
            "timestamp_ms": self.timestamp_ms,
            "time_readable": self.time_readable,
            "entry_price": round(self.entry_price, 2),
            "margin_usdt": round(self.margin_usdt, 2),
            "notional_usdt": round(self.notional_usdt, 2),
            "quantity": round(self.quantity, 8),
            "entry_fee_usdt": round(self.entry_fee_usdt, 4),
        }


@dataclass
class HedgeBasket:
    side: str
    entries: list[HedgeEntry] = field(default_factory=list)

    def add_entry(self, entry: HedgeEntry) -> None:
        if entry.side != self.side:
            raise ValueError(f"cannot add {entry.side} entry to {self.side} basket")
        self.entries.append(entry)

    def clear(self) -> None:
        self.entries.clear()

    @property
    def count(self) -> int:
        return len(self.entries)

    @property
    def total_margin_usdt(self) -> float:
        return sum(entry.margin_usdt for entry in self.entries)

    @property
    def total_notional_usdt(self) -> float:
        return sum(entry.notional_usdt for entry in self.entries)

    @property
    def total_quantity(self) -> float:
        return sum(entry.quantity for entry in self.entries)

    @property
    def entry_fees_usdt(self) -> float:
        return sum(entry.entry_fee_usdt for entry in self.entries)

    @property
    def average_entry_price(self) -> float:
        quantity = self.total_quantity
        if quantity <= 0:
            return 0.0
        return self.total_notional_usdt / quantity

    def unrealized_pnl(self, mark_price: float) -> float:
        mark = float(mark_price or 0.0)
        if mark <= 0:
            return 0.0
        if self.side == "SHORT":
            return sum((entry.entry_price - mark) * entry.quantity for entry in self.entries)
        return sum((mark - entry.entry_price) * entry.quantity for entry in self.entries)

    def exit_fee_usdt(self, profile: FuturesHedgeProfile) -> float:
        return self.total_notional_usdt * profile.exit_fee_pct

    def snapshot(self, *, mark_price: float, profile: FuturesHedgeProfile) -> dict[str, Any]:
        unrealized = self.unrealized_pnl(mark_price)
        margin = self.total_margin_usdt
        return {
            "side": self.side,
            "count": self.count,
            "margin_usdt": round(margin, 2),
            "notional_usdt": round(self.total_notional_usdt, 2),
            "quantity": round(self.total_quantity, 8),
            "average_entry_price": round(self.average_entry_price, 2),
            "mark_price": round(float(mark_price or 0.0), 2),
            "unrealized_pnl": round(unrealized, 2),
            "entry_fees_usdt": round(self.entry_fees_usdt, 4),
            "estimated_exit_fee_usdt": round(self.exit_fee_usdt(profile), 4),
            "roe_pct": round((unrealized / margin * 100.0) if margin > 0 else 0.0, 4),
        }


def build_entry_from_trigger(*, trigger: dict[str, Any], profile: FuturesHedgeProfile) -> HedgeEntry | None:
    side = str(trigger.get("side") or "").upper()
    if side not in {"LONG", "SHORT"}:
        return None
    entry_price = _as_float(trigger.get("entry_price"))
    if entry_price <= 0:
        return None
    notional = profile.position_notional_usdt
    quantity = notional / entry_price
    return HedgeEntry(
        source_position_id=str(trigger.get("position_id") or ""),
        side=side,
        timestamp_ms=_as_int(trigger.get("timestamp_ms") or trigger.get("opened_at_ms")),
        time_readable=str(trigger.get("time_readable") or trigger.get("opened_at") or ""),
        entry_price=entry_price,
        margin_usdt=profile.position_margin_usdt,
        notional_usdt=notional,
        quantity=quantity,
        entry_fee_usdt=notional * profile.entry_fee_pct,
    )


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
