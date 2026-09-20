"""Shared explanation-system helpers for frontend detail UI."""

from .py.data_loader import load_explanation_map
from .py.host import render_explanation_host
from platform_v2.shared.frontend.explanation_system import (
    ExplanationItem,
    ExplanationPresentation,
    ExplanationRegistry,
    render_explanation_anchor,
    render_explanation_payload,
)

__all__ = [
    "ExplanationItem",
    "ExplanationPresentation",
    "ExplanationRegistry",
    "load_explanation_map",
    "render_explanation_host",
    "render_explanation_anchor",
    "render_explanation_payload",
]
