"""File: outcome.py
Folder: platform_v2/spot/services/analytics/strategy_effectiveness
Created date: 2026-05-01
Last updated date: 2026-05-01
Author: Codex
Purpose: Outcome and timestamp helpers for Spot strategy effectiveness analytics.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from platform_v2.spot.storage.paths import candle_file_path
from platform_v2.shared.backend.persistence import read_market_series_safely
from platform_v2.shared.backend.runtime_store.spot import load_json_list


def load_candle_rows(*, symbol: str, timeframe: str) -> list[dict[str, Any]]:
    path = candle_file_path(symbol, timeframe)
    rows = read_market_series_safely(
        venue="binance",
        asset_class="crypto",
        market_type="spot",
        dataset="candles",
        symbol=symbol,
        timeframe=timeframe,
    )
    return rows or load_json_list(path)


def theoretical_outcome(*, row: dict[str, Any], candles: list[dict[str, Any]]) -> str:
    signal_ts = normalized_signal_timestamp_ms(row)
    theoretical_setup = row.get("theoretical_setup") or {}
    if not isinstance(theoretical_setup, dict):
        return "open"
    stop_loss = parse_float(theoretical_setup.get("stop_loss"))
    take_profit = parse_float(theoretical_setup.get("take_profit"))
    if stop_loss is None or take_profit is None:
        return "open"
    if signal_ts is None:
        return "open"

    for candle in candles:
        candle_open_ts = parse_int(candle.get("timestamp"))
        if candle_open_ts is None or candle_open_ts <= signal_ts:
            continue
        low_price = parse_float(candle.get("low"))
        high_price = parse_float(candle.get("high"))
        if low_price is None or high_price is None:
            continue
        if low_price <= stop_loss:
            return "sl"
        if high_price >= take_profit:
            return "tp"
    return "open"


def build_signal_lookup(signal_rows: list[dict[str, Any]]) -> dict[tuple[str, str, int], dict[str, Any]]:
    lookup: dict[tuple[str, str, int], dict[str, Any]] = {}
    for row in signal_rows:
        if str(row.get("side") or "").upper() != "BUY":
            continue
        timestamp_ms = normalized_signal_timestamp_ms(row)
        if timestamp_ms is None:
            continue
        lookup[(str(row.get("symbol") or ""), str(row.get("timeframe") or ""), timestamp_ms)] = row
    return lookup


def signal_lookup_key(position: Any) -> tuple[str, str, int]:
    symbol = str(getattr(position, "symbol", "") or "")
    timeframe = str(getattr(position, "timeframe", "") or "")
    timestamp_ms = normalized_timestamp_ms(
        timestamp_ms=timestamp_ms_from_position_opened_at(
            getattr(position, "signal_candle_close_time", None)
            or getattr(position, "opened_at", None)
        ),
        timeframe=timeframe,
    )
    return (symbol, timeframe, int(timestamp_ms or 0))


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
    if exit_reason == "profit_lock_hit":
        return "lock"
    if exit_reason == "tp_hit":
        return "tp"
    return "sl"


def net_pnl_value(position: Any) -> float:
    value = getattr(position, "net_pnl", None)
    if value is None:
        value = getattr(position, "pnl", 0.0)
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def parse_int(value: Any) -> int | None:
    raw_value: Any = value
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def parse_float(value: Any) -> float | None:
    raw_value: Any = value
    if raw_value is None:
        return None
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


def normalized_timestamp_ms(*, timestamp_ms: Any, timeframe: Any) -> int | None:
    parsed = parse_int(timestamp_ms)
    if parsed is None:
        return None
    return parsed


def normalized_signal_timestamp_ms(row: dict[str, Any]) -> int | None:
    return normalized_timestamp_ms(
        timestamp_ms=row.get("timestamp_ms"),
        timeframe=row.get("timeframe"),
    )
