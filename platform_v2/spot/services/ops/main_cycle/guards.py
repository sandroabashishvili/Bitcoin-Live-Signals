from __future__ import annotations

import fcntl
from contextlib import contextmanager
from pathlib import Path
import tempfile

from platform_v2.shared.backend.persistence import read_runtime_state, write_runtime_state

from .models import CycleMarkerInfo


class MainCycleGuardService:
    """Manage process lock and processed-cycle marker state."""

    _LOCK_ROOT = Path(tempfile.gettempdir()) / "smartsignalhub-locks"
    _PROCESS_LOCK_PATH = _LOCK_ROOT / "spot-main-cycle.lock"
    _STATE_KEY = "main_cycle_marker"

    @contextmanager
    def try_process_lock(self):
        self._LOCK_ROOT.mkdir(parents=True, exist_ok=True)
        lock_handle = self._PROCESS_LOCK_PATH.open("a+", encoding="utf-8")
        acquired = False
        try:
            try:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                acquired = False
            yield acquired
        finally:
            if acquired:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            lock_handle.close()

    def read_cycle_marker(self, cycle_key: str) -> CycleMarkerInfo:
        payload = read_runtime_state(system="spot", state_key=self._STATE_KEY)
        if payload is None:
            return CycleMarkerInfo(
                already_processed=False,
                state="marker_missing",
                note="cycle marker state does not exist yet",
            )

        marker_cycle_key = payload.get("cycle_key")
        return CycleMarkerInfo(
            already_processed=marker_cycle_key == cycle_key,
            state="marker_match" if marker_cycle_key == cycle_key else "marker_miss",
            note=str(marker_cycle_key) if marker_cycle_key else None,
        )

    def write_cycle_marker(self, cycle_key: str) -> None:
        write_runtime_state(
            system="spot",
            state_key=self._STATE_KEY,
            payload={"cycle_key": cycle_key},
        )
