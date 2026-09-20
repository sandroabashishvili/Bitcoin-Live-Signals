from __future__ import annotations

from platform_v2.spot.services.ops.cycle_run_runtime_service import CycleRunRuntimeService
from platform_v2.spot.services.ops.daily_runtime_summary_service import DailyRuntimeSummaryService

from .models import MainCycleResult


class MainCycleFinalizeService:
    """Persist cycle observability records and attach final daily summary."""

    def __init__(
        self,
        cycle_run_runtime_service: CycleRunRuntimeService | None = None,
        daily_runtime_summary_service: DailyRuntimeSummaryService | None = None,
    ) -> None:
        self._cycle_run_runtime_service = cycle_run_runtime_service or CycleRunRuntimeService()
        self._daily_runtime_summary_service = (
            daily_runtime_summary_service or DailyRuntimeSummaryService()
        )

    def finalize_result(self, *, date_iso: str, result: MainCycleResult) -> MainCycleResult:
        self._cycle_run_runtime_service.build_and_store(date_iso=date_iso, result=result)
        daily_summary_path = self._daily_runtime_summary_service.build_and_store(date_iso=date_iso)
        return MainCycleResult(
            cycle_key=result.cycle_key,
            cycle_state=result.cycle_state,
            cycle_note=result.cycle_note,
            skipped=result.skipped,
            skip_reason=result.skip_reason,
            fetched_candle_paths=result.fetched_candle_paths,
            fetched_orderbook_path=result.fetched_orderbook_path,
            built_indicator_paths=result.built_indicator_paths,
            signal_result=result.signal_result,
            updated_positions=result.updated_positions,
            metrics_path=result.metrics_path,
            daily_summary_path=daily_summary_path,
        )
