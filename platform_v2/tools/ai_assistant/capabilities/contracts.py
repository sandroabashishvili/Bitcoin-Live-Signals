"""Shared contracts for assistant capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CapabilityAnswer:
    capability: str
    text: str
    sources: tuple[str, ...] = ()
    facts: dict[str, Any] = field(default_factory=dict)

    def render(self) -> str:
        if not self.sources:
            return self.text
        source_lines = "\n".join(f"Source: {source}" for source in self.sources)
        return f"{self.text}\n{source_lines}"
