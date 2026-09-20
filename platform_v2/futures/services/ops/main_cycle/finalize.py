from __future__ import annotations

from platform_v2.futures.services.ops.cycle_run_runtime_service import CycleRunRuntimeService
from platform_v2.futures.services.ops.daily_runtime_summary_service import DailyRuntimeSummaryService

from .models import MainCycleResult


class MainCycleFinalizeService:
    """Persist futures observability records and attach final daily summary."""

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
        cycle_run_path = self._cycle_run_runtime_service.build_and_store(
            date_iso=date_iso,
            result=result,
        )
        daily_summary_path = self._daily_runtime_summary_service.build_and_store(date_iso=date_iso)
        return MainCycleResult(
            cycle_key=result.cycle_key,
            cycle_state=result.cycle_state,
            cycle_note=result.cycle_note,
            skipped=result.skipped,
            skip_reason=result.skip_reason,
            fetched_candle_paths=result.fetched_candle_paths,
            fetched_orderflow_path=result.fetched_orderflow_path,
            summary=result.summary,
            page_path=result.page_path,
            updated_page_paths=result.updated_page_paths,
            hedge_report_path=result.hedge_report_path,
            hedge_page_path=result.hedge_page_path,
            cycle_run_path=cycle_run_path,
            daily_summary_path=daily_summary_path,
        )
