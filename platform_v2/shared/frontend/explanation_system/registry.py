"""Registry for reusable dashboard explanations."""

from __future__ import annotations

from typing import Iterable

from .models import ExplanationItem


class ExplanationRegistry:
    """Simple in-memory registry for explanation items."""

    def __init__(self, items: Iterable[ExplanationItem] | None = None) -> None:
        self._items: dict[str, ExplanationItem] = {}
        if items:
            for item in items:
                self.register(item)

    def register(self, item: ExplanationItem) -> None:
        self._items[item.key] = item

    def get(self, key: str) -> ExplanationItem | None:
        return self._items.get(key)

    def as_dict(self) -> dict[str, ExplanationItem]:
        return dict(self._items)
