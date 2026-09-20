"""Shared schema validation using a subsystem-owned family registry."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .contracts import RuntimeFamilySpec


def missing_required_keys(
    family_name: str,
    payload: dict[str, Any],
    *,
    family_by_name: Mapping[str, RuntimeFamilySpec],
) -> list[str]:
    spec = family_by_name.get(family_name)
    if spec is None:
        return []
    return [key for key in spec.required_keys if key not in payload]


def validate_runtime_record(
    family_name: str,
    payload: Any,
    *,
    family_by_name: Mapping[str, RuntimeFamilySpec],
) -> list[str]:
    if not isinstance(payload, dict):
        return ["record must be an object"]
    missing = missing_required_keys(
        family_name,
        payload,
        family_by_name=family_by_name,
    )
    return [f"missing keys: {', '.join(missing)}"] if missing else []
