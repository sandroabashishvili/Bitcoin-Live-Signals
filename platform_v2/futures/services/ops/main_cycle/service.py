from __future__ import annotations

from platform_v2.shared.backend.research_evidence.runtime import recorded_cycle

from platform_v2.futures.config import ExecutionProfile

from .execution import MainCycleExecutionService
from .finalize import MainCycleFinalizeService
from .guards import MainCycleGuardService
from .inputs import MainCycleInputService
from .models import CycleInputs, CycleKeyInfo, MainCycleResult


class MainCycleService:
    """Run one guarded futures main cycle."""

    def __init__(
        self,
        input_service: MainCycleInputService | None = None,
        guard_service: MainCycleGuardService | None = None,
        execution_service: MainCycleExecutionService | None = None,
        finalize_service: MainCycleFinalizeService | None = None,
    ) -> None:
        self._input_service = input_service or MainCycleInputService()
        self._guard_service = guard_service or MainCycleGuardService()
        self._execution_service = execution_service or MainCycleExecutionService()
        self._finalize_service = finalize_service or MainCycleFinalizeService()

    @recorded_cycle("futures")
    def run(
        self,
        *,
        profile: ExecutionProfile,
        date_iso: str,
        fetch_limit: int = 500,
    ) -> MainCycleResult:
        cycle_inputs = self._input_service.prepare_cycle_inputs(
            profile=profile,
            fetch_limit=fetch_limit,
        )
        cycle_result = self._run_guarded_cycle(
            profile=profile,
            date_iso=date_iso,
            cycle_inputs=cycle_inputs,
        )
        return self._finalize_service.finalize_result(
            date_iso=date_iso,
            result=cycle_result,
        )

    def _run_guarded_cycle(
        self,
        *,
        profile: ExecutionProfile,
        date_iso: str,
        cycle_inputs: CycleInputs,
    ) -> MainCycleResult:
        cycle_info = cycle_inputs.cycle_info
        fetched_candle_paths = cycle_inputs.fetched_candle_paths

        with self._guard_service.try_process_lock() as lock_acquired:
            if not lock_acquired:
                return self._build_skipped_result(
                    cycle_info=cycle_info,
                    skip_reason="concurrent_cycle_locked",
                    fetched_candle_paths=fetched_candle_paths,
                )

            from platform_v2.shared.backend.research_evidence.runtime import ACTIVE
            from platform_v2.shared.backend.research_evidence.execution import ProjectionStage, committed
            import os
            attempt = ACTIVE.get()
            atomic = attempt is not None and os.environ.get("SSH_RESEARCH_ATOMIC_SIMULATION") == "1"
            if atomic and profile.mode != "simulation":
                raise RuntimeError("atomic projection staging supports simulation only")
            if atomic and committed(attempt.ledger.path, "futures", cycle_info.key):
                return self._build_skipped_result(cycle_info=cycle_info,
                    skip_reason="cycle_already_committed", fetched_candle_paths=fetched_candle_paths)
            marker_info = self._guard_service.read_cycle_marker(cycle_info.key)
            if marker_info.already_processed:
                return self._build_skipped_result(
                    cycle_info=cycle_info,
                    skip_reason=f"cycle_already_processed:{marker_info.state}",
                    fetched_candle_paths=fetched_candle_paths,
                )

            if atomic:
                with ProjectionStage(attempt.ledger.path, "futures", cycle_info.key,
                        attempt.attempt_id, before_commit=lambda: self._guard_service.write_cycle_marker(cycle_info.key)) as stage:
                    result = self._execution_service.run_ready_cycle(
                        profile=profile,
                        date_iso=date_iso,
                        fetched_candle_paths=fetched_candle_paths,
                        cycle_info=cycle_info,
                        commit_callback=stage.publish,
                    )
                    if not stage.published:
                        raise RuntimeError("simulation returned without atomic publication")
                    return result
            ready_result = self._execution_service.run_ready_cycle(
                profile=profile,
                date_iso=date_iso,
                fetched_candle_paths=fetched_candle_paths,
                cycle_info=cycle_info,
            )
            self._guard_service.write_cycle_marker(cycle_info.key)
            return ready_result

    @staticmethod
    def _build_skipped_result(
        *,
        cycle_info: CycleKeyInfo,
        skip_reason: str,
        fetched_candle_paths: tuple,
    ) -> MainCycleResult:
        return MainCycleResult(
            cycle_key=cycle_info.key,
            cycle_state=cycle_info.state,
            cycle_note=cycle_info.note,
            skipped=True,
            skip_reason=skip_reason,
            fetched_candle_paths=fetched_candle_paths,
            fetched_orderflow_path=None,
            summary=None,
            page_path=None,
            cycle_run_path=None,
            daily_summary_path=None,
        )
