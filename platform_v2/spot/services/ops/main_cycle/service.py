from __future__ import annotations

from platform_v2.spot.config import settings

from .execution import MainCycleExecutionService
from .finalize import MainCycleFinalizeService
from .guards import MainCycleGuardService
from .inputs import MainCycleInputService
from .models import CycleInputs, CycleKeyInfo, MainCycleResult


class MainCycleService:
    """Run one minimal closed-candle V2 cycle."""

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

    def run(
        self,
        *,
        symbol: str = settings.DEFAULT_SYMBOL,
        timeframe: str = settings.DEFAULT_TIMEFRAME,
        date_iso: str,
        position_size: float = settings.DEFAULT_POSITION_SIZE,
        starting_balance: float = settings.DEFAULT_STARTING_BALANCE,
        fetch_limit: int = settings.DEFAULT_FETCH_LIMIT,
    ) -> MainCycleResult:
        cycle_inputs = self._input_service.prepare_cycle_inputs(
            symbol=symbol,
            timeframe=timeframe,
            fetch_limit=fetch_limit,
        )
        cycle_result = self._run_guarded_cycle(
            symbol=symbol,
            timeframe=timeframe,
            date_iso=date_iso,
            position_size=position_size,
            starting_balance=starting_balance,
            cycle_inputs=cycle_inputs,
        )
        return self._finalize_service.finalize_result(
            date_iso=date_iso,
            result=cycle_result,
        )

    def _run_guarded_cycle(
        self,
        *,
        symbol: str,
        timeframe: str,
        date_iso: str,
        position_size: float,
        starting_balance: float,
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

            marker_info = self._guard_service.read_cycle_marker(cycle_info.key)
            if marker_info.already_processed:
                return self._build_skipped_result(
                    cycle_info=cycle_info,
                    skip_reason=f"cycle_already_processed:{marker_info.state}",
                    fetched_candle_paths=fetched_candle_paths,
                )

            ready_result = self._execution_service.run_ready_cycle(
                symbol=symbol,
                timeframe=timeframe,
                date_iso=date_iso,
                position_size=position_size,
                starting_balance=starting_balance,
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
            fetched_orderbook_path=None,
            built_indicator_paths=(),
            signal_result=None,
            updated_positions=(),
            metrics_path=None,
            daily_summary_path=None,
        )
