"""File: position_lifecycle_service.py
Folder: platform_v2/futures/services/simulation
Created date: 2026-06-01
Last updated date: 2026-06-01
Author: Codex
Purpose: Handle open Futures position lifecycle updates before new entries.
"""

from __future__ import annotations

from typing import Any

from platform_v2.futures.config import ExecutionProfile
from platform_v2.shared.backend.runtime_store.futures import POSITION_EVENTS_FAMILY

from .position_service import FuturesPositionService
from .runtime_store import FuturesSimulationRuntimeStore
from .state_store import FuturesSimulationStateStore


class FuturesPositionLifecycleService:
    """Close existing Futures positions when their TP or SL is reached."""

    def __init__(
        self,
        *,
        runtime_store: FuturesSimulationRuntimeStore,
        state_store: FuturesSimulationStateStore,
        position_service: FuturesPositionService,
    ) -> None:
        self._runtime_store = runtime_store
        self._state_store = state_store
        self._position_service = position_service

    def process_existing_positions(
        self,
        *,
        state: dict[str, Any],
        profile: ExecutionProfile,
        date_iso: str,
        exit_candles: list[dict[str, Any]],
    ) -> str:
        position_event = self._close_resolved_positions(
            state=state,
            profile=profile,
            date_iso=date_iso,
            exit_candles=exit_candles,
        )
        return position_event

    def write_open_position_state_updates(
        self,
        *,
        date_iso: str,
        open_positions: list[dict[str, Any]],
        latest_close: float,
        ts_ms: int,
        time_text: str,
    ) -> None:
        for position in open_positions:
            row = self._position_service.build_open_position_state_row(
                position=position,
                latest_close=latest_close,
                ts_ms=ts_ms,
                time_text=time_text,
            )
            self._runtime_store.append_daily_row(
                family_name=POSITION_EVENTS_FAMILY,
                date_iso=date_iso,
                row=row,
            )

    def _close_resolved_positions(
        self,
        *,
        state: dict[str, Any],
        profile: ExecutionProfile,
        date_iso: str,
        exit_candles: list[dict[str, Any]],
    ) -> str:
        position_event = "NO_EVENT"
        open_positions = self._state_store.open_positions(state)
        survivors: list[dict[str, Any]] = []
        for position in open_positions:
            relevant_exit_candles = self._position_service.candles_after_position_open(
                position=position,
                candles=exit_candles,
            )
            close_event = self._position_service.try_close_position_from_candles(
                position=position,
                candles=relevant_exit_candles,
                leverage=profile.leverage,
            )
            if close_event is None:
                survivors.append(position)
                continue

            self._store_close_event(close_event=close_event, date_iso=date_iso)
            self._position_service.apply_close_stats(state, close_event)
            position_event = str(close_event.get("outcome") or "CLOSED")
            state["last_position_event"] = position_event
        self._state_store.set_open_positions(state, survivors)
        return position_event

    def _store_close_event(self, *, close_event: dict[str, Any], date_iso: str) -> None:
        self._runtime_store.append_daily_row(
            family_name=POSITION_EVENTS_FAMILY,
            date_iso=date_iso,
            row=close_event,
        )
