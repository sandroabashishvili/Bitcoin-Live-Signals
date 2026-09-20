"""Canonical runtime roots for every SmartSignalHub subsystem."""

from __future__ import annotations

from pathlib import Path


PLATFORM_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ROOT = PLATFORM_ROOT / "runtime"
SYSTEM_NAMES = ("spot", "futures", "hedge")
SYSTEM_RUNTIME_ROOTS = {name: RUNTIME_ROOT / name for name in SYSTEM_NAMES}


def system_runtime_root(system: str) -> Path:
    try:
        return SYSTEM_RUNTIME_ROOTS[system]
    except KeyError as exc:
        supported = ", ".join(SYSTEM_NAMES)
        raise ValueError(f"Unknown runtime system {system!r}; expected one of: {supported}") from exc


def system_data_root(system: str) -> Path:
    return system_runtime_root(system) / "data"
