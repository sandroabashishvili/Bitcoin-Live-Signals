"""Runtime profile for the independent Futures Hedge subsystem."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from . import settings


@dataclass(frozen=True)
class FuturesHedgeProfile:
    """Owner-controlled settings for Hedge paper/replay accounting."""

    symbol: str = settings.DEFAULT_SYMBOL
    timeframe: str = settings.DEFAULT_TIMEFRAME
    starting_capital_usdt: float = settings.DEFAULT_STARTING_CAPITAL_USDT
    position_margin_usdt: float = settings.DEFAULT_POSITION_MARGIN_USDT
    leverage: int = settings.DEFAULT_LEVERAGE
    entry_fee_pct: float = settings.ENTRY_FEE_PCT
    exit_fee_pct: float = settings.EXIT_FEE_PCT

    @property
    def position_notional_usdt(self) -> float:
        return self.position_margin_usdt * float(self.leverage)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_profile() -> FuturesHedgeProfile:
    return FuturesHedgeProfile()
