"""File: denied_entry_runtime_service.py
Folder: platform_v2/spot/services
Created date: 2026-03-25
Last updated date: 2026-03-25
Author: Codex
Purpose: Persist denied-entry records for V2 runtime analytics.
"""

from __future__ import annotations

from platform_v2.spot.domain.models.execution import DenialReason, DeniedEntryRecord, PermissionDecision
from platform_v2.spot.domain.models.signal import SignalDecision
from platform_v2.spot.services.ops.runtime_write_service import write_denied_entry_record


class DeniedEntryRuntimeService:
    """Create and persist denied-entry records from signal and permission data."""

    def build_and_persist(
        self,
        *,
        date_iso: str,
        signal: SignalDecision,
        permission: PermissionDecision,
        live_entry_price: float,
    ) -> DeniedEntryRecord | None:
        """Persist one denied-entry record when permission is denied."""

        if permission.is_allowed:
            return None

        denied_entry = DeniedEntryRecord(
            signal=signal,
            permission=permission,
            live_entry_price=live_entry_price,
            denial_reason=self._map_denial_reason(permission.reason),
            theoretical_setup=signal.theoretical_setup,
        )
        write_denied_entry_record(date_iso=date_iso, denied_entry=denied_entry)
        return denied_entry

    @staticmethod
    def _map_denial_reason(reason_text: str) -> DenialReason:
        """Map a stored reason string back to the normalized enum."""

        for reason in DenialReason:
            if reason.value == reason_text:
                return reason
        return DenialReason.UNKNOWN
