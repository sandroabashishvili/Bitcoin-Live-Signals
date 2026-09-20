"""File: runtime_write_service.py
Folder: platform_v2/spot/services
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Persist runtime-facing V2 records into daily JSON families.
"""

from __future__ import annotations

from pathlib import Path

from platform_v2.spot.domain.models.execution import DeniedEntryRecord
from platform_v2.spot.domain.models.force_close import ForceCloseEvent
from platform_v2.spot.domain.models.order import OrderResult
from platform_v2.spot.domain.models.position import PositionRecord
from platform_v2.spot.domain.models.signal import SignalDecision
from platform_v2.shared.backend.runtime_store.spot import (
    DENIED_ENTRIES_FAMILY,
    FORCE_CLOSES_FAMILY,
    ORDERS_FAMILY,
    POSITIONS_FAMILY,
    SIGNALS_FAMILY,
    append_runtime_record,
    upsert_runtime_record,
)


def write_signal_record(date_iso: str, signal: SignalDecision) -> Path:
    """Persist one signal decision into the signals family.

    Args:
        date_iso: Target date in ISO format.
        signal: Signal decision to persist.

    Returns:
        Path: Updated signals file path.
    """

    return upsert_runtime_record(
        SIGNALS_FAMILY,
        date_iso,
        signal,
        key_name="timestamp_ms",
    )


def write_denied_entry_record(date_iso: str, denied_entry: DeniedEntryRecord) -> Path:
    """Persist one denied-entry record into the denied entries family.

    Args:
        date_iso: Target date in ISO format.
        denied_entry: Denied-entry record to persist.

    Returns:
        Path: Updated denied entries file path.
    """

    return append_runtime_record(DENIED_ENTRIES_FAMILY, date_iso, denied_entry)


def write_position_record(date_iso: str, position: PositionRecord) -> Path:
    """Persist one position record into the positions family.

    Args:
        date_iso: Target date in ISO format.
        position: Position record to persist.

    Returns:
        Path: Updated positions file path.
    """

    return upsert_runtime_record(
        POSITIONS_FAMILY,
        date_iso,
        position,
        key_name="position_id",
    )


def write_order_record(date_iso: str, order_result: OrderResult) -> Path:
    """Persist one normalized order result into the orders family.

    Args:
        date_iso: Target date in ISO format.
        order_result: Order result to persist.

    Returns:
        Path: Updated orders file path.
    """

    return append_runtime_record(ORDERS_FAMILY, date_iso, order_result)


def write_force_close_record(date_iso: str, force_close_event: ForceCloseEvent) -> Path:
    """Persist one force-close event into the force_closes family."""

    return append_runtime_record(FORCE_CLOSES_FAMILY, date_iso, force_close_event)
