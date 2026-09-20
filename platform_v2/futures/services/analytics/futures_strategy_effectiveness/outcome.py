"""File: outcome.py
Folder: platform_v2/futures/services/analytics/futures_strategy_effectiveness
Created date: 2026-05-01
Last updated date: 2026-05-01
Author: Codex
Purpose: Outcome and timestamp helpers for Futures strategy effectiveness analytics.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from platform_v2.futures.storage import candle_file_path, load_json_list


TIMEFRAME_MS = {
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}


def load_candle_rows(*, symbol: str, timeframe: str) -> list[dict[str, Any]]:
    return load_json_list(candle_file_path(symbol, timeframe))


def theoretical_outcome(*, row: dict[str, Any], candles: list[dict[str, Any]]) -> str:
    signal_ts = normalized_signal_timestamp_ms(row)
    theoretical_setup_raw = row.get("theoretical_setup")
    theoretical_setup = theoretical_setup_raw if isinstance(theoretical_setup_raw, dict) else {}
    stop_loss = as_float(theoretical_setup.get("stop_loss"))
    take_profit = as_float(theoretical_setup.get("take_profit"))
    if stop_loss is None or take_profit is None or signal_ts is None:
        return "open"

    for candle in candles:
        candle_open_ts = parse_int(candle.get("timestamp"))
        if candle_open_ts is None or candle_open_ts <= signal_ts:
            continue
        low_price = as_float(candle.get("low"))
        high_price = as_float(candle.get("high"))
        if low_price is None or high_price is None:
            continue
        direction = signal_direction(row)
        if direction == "SHORT":
            if high_price >= stop_loss:
                return "sl"
            if low_price <= take_profit:
                return "tp"
            continue
        if low_price <= stop_loss:
            return "sl"
        if high_price >= take_profit:
            return "tp"
    return "open"


def build_signal_lookup(signal_rows: list[dict[str, Any]]) -> dict[tuple[str, str, int], dict[str, Any]]:
    lookup: dict[tuple[str, str, int], dict[str, Any]] = {}
    for row in signal_rows:
        if signal_direction(row) != "LONG":
            continue
        timestamp_ms = normalized_signal_timestamp_ms(row)
        if timestamp_ms is None:
            continue
        lookup[(str(row.get("symbol") or ""), str(row.get("timeframe") or ""), timestamp_ms)] = row
    return lookup


def signal_lookup_key_from_position(position: Any) -> tuple[str, str, int] | None:
    symbol = str(getattr(position, "symbol", "") or "")
    timeframe = str(getattr(position, "timeframe", "") or "")
    raw_timestamp_ms = timestamp_ms_from_position_opened_at(getattr(position, "opened_at", None))
    timestamp_ms = normalized_timestamp_ms(
        timestamp_ms=raw_timestamp_ms,
        timeframe=timeframe,
    )
    if not symbol or not timeframe or timestamp_ms is None:
        return None
    return (symbol, timeframe, timestamp_ms)


def timestamp_ms_from_position_opened_at(value: Any) -> int | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text.isdigit():
        try:
            return int(text)
        except (TypeError, ValueError):
            return None
    try:
        base_ms = int(
            datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
            .replace(tzinfo=UTC)
            .timestamp()
            * 1000
        )
        return base_ms + 999
    except ValueError:
        return None


def closed_trade_outcome_key(position: Any) -> str:
    exit_reason = str(
        getattr(getattr(position, "exit_reason", None), "value", None)
        or getattr(position, "exit_reason", "")
        or ""
    ).lower()
    if bool(getattr(position, "was_force_closed", False)) or exit_reason == "force_close":
        return "force_close"
    if exit_reason == "tp_hit":
        return "tp"
    if exit_reason == "profit_lock_hit":
        return "profit_lock"
    return "sl"


def net_pnl_value(position: Any) -> float:
    value = getattr(position, "net_pnl", None)
    if value is None:
        value = getattr(position, "pnl", 0.0)
    parsed = as_float(value)
    return parsed if parsed is not None else 0.0


def signal_direction(row: dict[str, Any]) -> str:
    side = str(row.get("selected_direction") or row.get("side") or "").upper()
    if side == "BUY":
        return "LONG"
    if side == "SELL":
        return "SHORT"
    return side


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalized_timestamp_ms(*, timestamp_ms: Any, timeframe: Any) -> int | None:
    parsed = parse_int(timestamp_ms)
    if parsed is None:
        return None
    window_ms = TIMEFRAME_MS.get(str(timeframe or "").lower())
    if window_ms is None or window_ms <= 0:
        return parsed
    return (parsed // window_ms) * window_ms


def normalized_signal_timestamp_ms(row: dict[str, Any]) -> int | None:
    return normalized_timestamp_ms(
        timestamp_ms=row.get("timestamp_ms"),
        timeframe=row.get("timeframe"),
    )
