"""File: position_exit_trigger_checks.py
Folder: platform_v2/tools/diagnostics/checks
Created date: 2026-05-01
Last updated date: 2026-05-01
Author: Codex
Purpose: Validate closed position TP/SL trigger candles against persisted candle data.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from platform_v2.spot.domain.models.position import ExitReason
from platform_v2.shared.backend.runtime_store.spot import CANDLES_FAMILY, POSITIONS_FAMILY, daily_json_path
from platform_v2.tools.diagnostics.core.config import V2_ROOT
from platform_v2.tools.diagnostics.core.models import FileFinding, add_finding


def check_position_exit_triggers(findings: list[FileFinding], date_iso: str) -> None:
    position_rows = _load_runtime_day_rows(POSITIONS_FAMILY, date_iso)
    if not position_rows:
        return

    candle_cache: dict[tuple[str, str], dict[int, dict[str, Any]]] = {}
    position_path = f"platform_v2/runtime/spot/data/{POSITIONS_FAMILY}/{POSITIONS_FAMILY}_{date_iso}.json"

    for index, row in enumerate(position_rows):
        if row.get("status") != "CLOSED":
            continue
        exit_reason = str(row.get("exit_reason") or "").strip()
        if exit_reason not in {ExitReason.TP_HIT.value, ExitReason.SL_HIT.value}:
            continue

        position_id = str(row.get("position_id") or f"index={index}")
        opened_at_ms = _runtime_timestamp_ms(row.get("opened_at"))
        trigger_close_ms = _runtime_int(row.get("exit_trigger_candle_close_ms"))
        if opened_at_ms is None or trigger_close_ms is None:
            continue

        if trigger_close_ms <= opened_at_ms:
            add_finding(
                findings,
                f"{position_path}#{index}",
                "position_exit_before_or_at_open",
                f"position_id={position_id} opened_at_ms={opened_at_ms} trigger_close_ms={trigger_close_ms}",
                "high",
            )

        symbol = str(row.get("symbol") or "").strip()
        timeframe = str(row.get("exit_check_timeframe") or "5m").strip()
        if not symbol or not timeframe:
            continue

        cache_key = (symbol, timeframe)
        if cache_key not in candle_cache:
            candle_cache[cache_key] = _load_candles_by_close_ms(symbol, timeframe)
        trigger_candle = candle_cache[cache_key].get(trigger_close_ms)
        if trigger_candle is None:
            add_finding(
                findings,
                f"{position_path}#{index}",
                "position_exit_trigger_candle_missing",
                f"position_id={position_id} symbol={symbol} timeframe={timeframe} close_ms={trigger_close_ms}",
                "medium",
            )
            continue

        mismatch = _position_exit_trigger_mismatch(row=row, candle=trigger_candle, exit_reason=exit_reason)
        if mismatch:
            add_finding(
                findings,
                f"{position_path}#{index}",
                "position_exit_trigger_mismatch",
                f"position_id={position_id} {mismatch}",
                "high",
            )


def _position_exit_trigger_mismatch(
    *,
    row: dict[str, Any],
    candle: dict[str, Any],
    exit_reason: str,
) -> str | None:
    execution = row.get("execution")
    if not isinstance(execution, dict):
        return None

    side = str(row.get("side") or "").strip().upper()
    high = _runtime_float(candle.get("high"))
    low = _runtime_float(candle.get("low"))
    stop_loss = _runtime_float(execution.get("stop_loss"))
    take_profit = _runtime_float(execution.get("take_profit"))
    if high is None or low is None or stop_loss is None or take_profit is None:
        return None

    if side in {"BUY", "LONG"}:
        if exit_reason == ExitReason.SL_HIT.value and low > stop_loss:
            return f"sl_hit not confirmed: candle_low={low} stop_loss={stop_loss}"
        if exit_reason == ExitReason.TP_HIT.value and high < take_profit:
            return f"tp_hit not confirmed: candle_high={high} take_profit={take_profit}"
        return None

    if side in {"SELL", "SHORT"}:
        if exit_reason == ExitReason.SL_HIT.value and high < stop_loss:
            return f"sl_hit not confirmed: candle_high={high} stop_loss={stop_loss}"
        if exit_reason == ExitReason.TP_HIT.value and low > take_profit:
            return f"tp_hit not confirmed: candle_low={low} take_profit={take_profit}"
        return None

    return None


def _load_runtime_json(path: Path) -> Any:
    payload: Any = None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = None
    return payload


def _load_runtime_day_rows(family_name: str, date_iso: str) -> list[dict[str, Any]]:
    payload = _load_runtime_json(daily_json_path(family_name, date_iso))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def _load_candles_by_close_ms(symbol: str, timeframe: str) -> dict[int, dict[str, Any]]:
    candle_path = V2_ROOT / "runtime" / "spot" / "data" / CANDLES_FAMILY / symbol / f"{timeframe}.json"
    payload = _load_runtime_json(candle_path)
    if not isinstance(payload, list):
        return {}

    candles_by_close_ms: dict[int, dict[str, Any]] = {}
    for row in payload:
        if not isinstance(row, dict):
            continue
        close_time = _runtime_int(row.get("close_time"))
        if close_time is not None:
            candles_by_close_ms[close_time] = row
    return candles_by_close_ms


def _runtime_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
    return None


def _runtime_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    parsed: float | None = None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = None
    return parsed


def _runtime_timestamp_ms(value: Any) -> int | None:
    raw_ms = _runtime_int(value)
    if raw_ms is not None:
        return raw_ms
    if not isinstance(value, str):
        return None

    stripped = value.strip()
    if not stripped:
        return None
    if stripped.endswith("Z"):
        stripped = stripped[:-1]
    parsed: datetime | None = None
    try:
        parsed = datetime.strptime(stripped, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        parsed = None
    if parsed is None:
        return None
    return int(parsed.timestamp() * 1000) + 999
