"""Typed models for dashboard explanation content."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExplanationItem:
    """One explanation entry for a metric, label, or status."""

    key: str
    title: str
    summary: str
    details: tuple[str, ...] = ()
    severity: str = "neutral"
    cta_label: str | None = None
    cta_href: str | None = None
    secondary_cta_label: str | None = None
    secondary_cta_href: str | None = None


@dataclass(frozen=True)
class ExplanationPresentation:
    """Presentation rules for explanation UI behavior."""

    mode: str = "drawer"
    trigger: str = "click"
    allow_hover_preview: bool = False
    css_variant: str = "default"
    attrs: dict[str, str] = field(default_factory=dict)
