"""External news capability placeholder."""

from __future__ import annotations

from .contracts import CapabilityAnswer


def answer_news() -> CapabilityAnswer:
    text = "\n".join(
        [
            "News capability",
            "Live news is not wired into this local assistant yet.",
            "Trusted answers require current web/news access plus source links/citations.",
            "Until that source is configured, the assistant must not summarize politics, markets, or current events from memory.",
            "Project-local news generation files are separate from live news reading.",
        ]
    )
    return CapabilityAnswer("news", text)
