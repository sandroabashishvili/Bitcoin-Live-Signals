"""Shared frontend helpers for page builders and renderers."""

from .py.page_bits import (
    normalize_generated_html,
    render_content_hero,
    render_page_head,
    render_runtime_hero,
)
from .py.navigation import render_site_navigation
from .py.site_footer import render_site_footer
from .py.runtime_clock import render_runtime_clock_script, render_runtime_clock_strip
from .py.metric_formatting import escape as escape_value
from .py.metric_formatting import strong as strong_value
from .py.metric_formatting import value_class as metric_value_class

__all__ = [
    "render_content_hero",
    "normalize_generated_html",
    "render_page_head",
    "render_runtime_hero",
    "render_runtime_clock_script",
    "render_runtime_clock_strip",
    "render_site_footer",
    "render_site_navigation",
    "escape_value",
    "metric_value_class",
    "strong_value",
]
