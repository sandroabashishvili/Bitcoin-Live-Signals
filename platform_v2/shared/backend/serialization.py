"""Convert domain objects into runtime-safe Python primitives."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any


def to_runtime_dict(value: Any) -> Any:
    """Recursively convert dataclasses, enums, mappings, and sequences."""

    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            field.name: to_runtime_dict(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, dict):
        return {
            str(key): to_runtime_dict(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [to_runtime_dict(item) for item in value]
    return value
