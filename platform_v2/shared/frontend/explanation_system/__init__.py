"""Shared explanation-system helpers for dashboard detail UI."""

from .host import render_explanation_host
from .models import ExplanationItem, ExplanationPresentation
from .registry import ExplanationRegistry
from .renderers import render_explanation_anchor, render_explanation_payload

__all__ = [
    "ExplanationItem",
    "ExplanationPresentation",
    "ExplanationRegistry",
    "render_explanation_host",
    "render_explanation_anchor",
    "render_explanation_payload",
]
