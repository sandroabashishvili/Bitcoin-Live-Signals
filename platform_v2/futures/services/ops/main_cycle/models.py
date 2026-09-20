from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platform_v2.futures.services.simulation.models import FuturesCycleSummary


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
    """Prepared inputs required to run one guarded futures cycle."""

    fetched_candle_paths: tuple[Path, ...]
    cycle_info: CycleKeyInfo


@dataclass(frozen=True)
class MainCycleResult:
    """Result bundle for one futures main cycle."""

    cycle_key: str
    cycle_state: str
    cycle_note: str | None
    skipped: bool
    skip_reason: str | None
    fetched_candle_paths: tuple[Path, ...]
    fetched_orderflow_path: Path | None
    summary: FuturesCycleSummary | None
    page_path: Path | None
    updated_page_paths: tuple[Path, ...] = ()
    hedge_report_path: Path | None = None
    hedge_page_path: Path | None = None
    cycle_run_path: Path | None = None
    daily_summary_path: Path | None = None
