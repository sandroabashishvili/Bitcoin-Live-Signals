"""Compatibility wrapper for the shared explanation drawer host."""

from __future__ import annotations

from platform_v2.shared.frontend.explanation_system import render_explanation_host as _render_shared_host


def render_explanation_host(*, base_prefix: str = "../") -> str:
    """Render the shared explanation drawer shell and loader script."""

    del base_prefix
    return _render_shared_host(asset_prefix="../../../shared/frontend/explanation_system/")
