from __future__ import annotations

from unittest.mock import patch

from platform_v2.futures.services.ops.main_cycle.guards import MainCycleGuardService


def test_cycle_marker_uses_runtime_state_without_json_files() -> None:
    service = MainCycleGuardService()
    with patch(
        "platform_v2.futures.services.ops.main_cycle.guards.read_runtime_state",
        return_value={"cycle_key": "cycle-1"},
    ):
        marker = service.read_cycle_marker("cycle-1")
    assert marker.already_processed is True
    assert marker.state == "marker_match"

    with patch("platform_v2.futures.services.ops.main_cycle.guards.write_runtime_state") as write_state:
        service.write_cycle_marker("cycle-2")
    write_state.assert_called_once_with(
        system="futures",
        state_key="main_cycle_marker",
        payload={"cycle_key": "cycle-2"},
    )
