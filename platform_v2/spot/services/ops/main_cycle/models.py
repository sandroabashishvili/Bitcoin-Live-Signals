from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platform_v2.spot.domain.models.position import PositionRecord
from platform_v2.spot.services.permission.signal_permission_runtime_service import (
    SignalPermissionRunResult,
)


@dataclass(frozen=True)
class MainCycleResult:
    """Result bundle for one V2 main cycle."""

    cycle_key: str
    cycle_state: str
    cycle_note: str | None
    skipped: bool
    skip_reason: str | None
    fetched_candle_paths: tuple[Path, ...]
    fetched_orderbook_path: Path | None
    built_indicator_paths: tuple[Path, ...]
    signal_result: SignalPermissionRunResult | None
    updated_positions: tuple[PositionRecord, ...]
    metrics_path: Path | None
    daily_summary_path: Path | None


@dataclass(frozen=True)
class CycleKeyInfo:
    """Normalized cycle-key build result for the primary timeframe candle."""

    key: str
    state: str
    note: str | None = None


@dataclass(frozen=True)
class CycleMarkerInfo:
    """Normalized cycle-marker read result."""

    already_processed: bool
    state: str
    note: str | None = None


@dataclass(frozen=True)
class CycleInputs:
    """Prepared inputs required to run one guarded cycle."""

    fetched_candle_paths: tuple[Path, ...]
    cycle_info: CycleKeyInfo


@dataclass(frozen=True)
class TelegramSignalSnapshot:
    """Telegram-friendly metrics snapshot for one opened position alert."""

    open_positions: int
    active_exposure: float
    available_balance: float
    equity: float
    annualized_return: float
    net_return_pct: float
    total_net_pnl: float
    unrealized_pnl: float
    total_positions: int
    closed_positions: int
    tp_hits: int
    sl_hits: int
    force_close_events: int
