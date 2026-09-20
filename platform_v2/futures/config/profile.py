"""Load and persist Futures execution profile with safe defaults."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import settings


@dataclass(frozen=True)
class ExecutionProfile:
    market: str
    mode: str
    symbol: str
    timeframe: str
    leverage: int
    margin_mode: str
    order_size_usdt: float
    starting_balance: float


def _default_payload() -> dict[str, Any]:
    return {
        "market": "futures",
        "mode": settings.DEFAULT_MODE,
        "symbol": settings.DEFAULT_SYMBOL,
        "timeframe": settings.DEFAULT_TIMEFRAME,
        "leverage": settings.DEFAULT_LEVERAGE,
        "margin_mode": settings.DEFAULT_MARGIN_MODE,
        "order_size_usdt": settings.DEFAULT_ORDER_SIZE_USDT,
        "starting_balance": settings.DEFAULT_STARTING_BALANCE,
    }


def _read_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_mode(value: Any) -> str:
    text = str(value or "").strip().lower()
    return "live" if text == "live" else "simulation"


def _normalize_margin_mode(value: Any) -> str:
    text = str(value or "").strip().lower()
    return "cross" if text == "cross" else "isolated"


def _build_profile(payload: dict[str, Any]) -> ExecutionProfile:
    leverage = _as_int(payload.get("leverage"), settings.DEFAULT_LEVERAGE)
    leverage = max(settings.MIN_LEVERAGE, min(settings.MAX_LEVERAGE, leverage))
    return ExecutionProfile(
        market="futures",
        mode=_normalize_mode(payload.get("mode")),
        symbol=str(payload.get("symbol") or settings.DEFAULT_SYMBOL).strip() or settings.DEFAULT_SYMBOL,
        timeframe=str(payload.get("timeframe") or settings.DEFAULT_TIMEFRAME).strip() or settings.DEFAULT_TIMEFRAME,
        leverage=leverage,
        margin_mode=_normalize_margin_mode(payload.get("margin_mode")),
        order_size_usdt=max(0.0, _as_float(payload.get("order_size_usdt"), settings.DEFAULT_ORDER_SIZE_USDT)),
        starting_balance=max(0.0, _as_float(payload.get("starting_balance"), settings.DEFAULT_STARTING_BALANCE)),
    )


def load_execution_profile(path: Path | None = None) -> ExecutionProfile:
    base = _default_payload()
    if path is not None:
        base.update(_read_payload(path))
    return _build_profile(base)
