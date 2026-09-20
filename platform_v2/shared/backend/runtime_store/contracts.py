"""Storage-neutral runtime family contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RuntimeFamilyKind(StrEnum):
    EVENT = "event"
    SNAPSHOT = "snapshot"
    STATE = "state"
    CACHE = "cache"


@dataclass(frozen=True)
class RuntimeFamilySpec:
    name: str
    kind: RuntimeFamilyKind
    writer_owner: str
    reader_owner: str
    retention: str
    required_keys: tuple[str, ...] = ()
    frontend_used: bool = False
    description: str = ""
    persisted: bool = True
    derived_from: tuple[str, ...] = ()
