"""File: utils.py
Folder: platform_v2/public_site/news/py/news_pipeline
Created date: 2026-03-29
Last updated date: 2026-03-29
Author: Codex
Purpose: Shared utility helpers for the V2 frontend-owned news pipeline.
"""

from __future__ import annotations

import hashlib
import html
import re
from pathlib import Path


def ensure_dirs(path: Path) -> None:
    """Create a directory tree if it does not exist."""

    path.mkdir(parents=True, exist_ok=True)


def clean_html(text: str) -> str:
    """Strip HTML tags from text."""

    plain_text = re.sub("<.*?>", "", text or "")
    plain_text = html.unescape(plain_text)
    return re.sub(r"\s+", " ", plain_text).strip()


def truncate(text: str, max_len: int) -> str:
    """Trim text without cutting the last word in half."""

    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0] + "..."


def safe_name(url: str) -> str:
    """Build a stable short hash for downloaded image names."""

    return hashlib.sha1((url or "na").encode("utf-8")).hexdigest()[:16]

