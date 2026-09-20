from __future__ import annotations

import html as html_lib
import json
from pathlib import Path


def parse_news_json(
    json_path: str, max_items: int, indexes: list[int] | None,
    *, overrides_path: str | None = None,
) -> list[tuple[str, str, str]]:
    path = Path(json_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items", []) if isinstance(payload, dict) else []

    normalized: list[tuple[str, str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = html_lib.unescape(str(item.get("title") or "")).strip()
        summary = html_lib.unescape(str(item.get("summary") or "")).strip()
        source = html_lib.unescape(str(item.get("source") or "")).strip()
        if not title:
            continue
        normalized.append((title, summary, source))

    if overrides_path:
        overrides = json.loads(Path(overrides_path).read_text(encoding="utf-8"))
        entries = overrides.get("stories") if isinstance(overrides, dict) else None
        if not isinstance(entries, list):
            raise ValueError("Story overrides must contain a stories list")
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("Each story override must be an object")
            index = entry.get("index")
            if type(index) is not int or not 1 <= index <= len(normalized) or index in seen:
                raise ValueError(f"Invalid or duplicate override index: {index}")
            original, summary, source = normalized[index - 1]
            if entry.get("expected_title") != original:
                raise ValueError(f"Story {index} changed; review the override before rendering")
            title = entry.get("title", original)
            summary = entry.get("summary", summary)
            if not isinstance(title, str) or not title.strip() or not isinstance(summary, str):
                raise ValueError(f"Invalid title/summary in story override {index}")
            normalized[index - 1] = (title.strip(), summary.strip(), source)
            seen.add(index)

    if indexes:
        if any(not 1 <= i <= len(normalized) for i in indexes):
            raise ValueError(f"News indexes must be between 1 and {len(normalized)}")
        return [normalized[i - 1] for i in indexes]
    return normalized[: max(1, max_items)]
