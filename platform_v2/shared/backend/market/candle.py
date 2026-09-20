"""Canonical OHLCV candle model shared by Spot and Futures."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    """Normalized market candle used across V2.

    Args:
        symbol: Instrument symbol.
        timeframe: Candle timeframe, for example 5m or 30m.
        open_time_ms: Candle open timestamp in milliseconds.
        close_time_ms: Candle close timestamp in milliseconds.
        open_price: Candle open price.
        high_price: Candle high price.
        low_price: Candle low price.
        close_price: Candle close price.
        volume: Candle traded volume.
    """

    symbol: str
    timeframe: str
    open_time_ms: int
    close_time_ms: int
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float

    @property
    def midpoint_price(self) -> float:
        """Return the midpoint between the candle high and low.

        Returns:
            float: Midpoint price for the candle range.
        """

        return (self.high_price + self.low_price) / 2.0

    @property
    def is_bullish(self) -> bool:
        """Return whether the candle closed above or equal to its open.

        Returns:
            bool: True when close price is above or equal to open price.
        """

        return self.close_price >= self.open_price

    @property
    def is_bearish(self) -> bool:
        """Return whether the candle closed below its open.

        Returns:
            bool: True when close price is below open price.
        """

        return self.close_price < self.open_price

    @property
    def range_size(self) -> float:
        """Return the full candle range.

        Returns:
            float: High minus low.
        """

        return self.high_price - self.low_price
