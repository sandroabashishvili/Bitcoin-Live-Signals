"""File: http_client.py
Folder: platform_v2/public_site/news/py/news_pipeline
Created date: 2026-03-29
Last updated date: 2026-03-29
Author: Codex
Purpose: HTTP helpers for fetching RSS feeds and article HTML in the V2 news pipeline.
"""

from __future__ import annotations

import logging
import ssl
from urllib.error import URLError
import urllib.request


logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 12
USER_AGENT = "SmartSignalHub/1.0 (+https://sandro-abashishvili.de/Bitcoin-Live-Signals/)"
SSL_CONTEXT = ssl.create_default_context()


def urlread(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> bytes:
    """Fetch raw bytes from a URL with a browser-like user agent."""

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout, context=SSL_CONTEXT) as response:
        content = response.read(2_000_001)
        if len(content) > 2_000_000:
            raise ValueError("News response exceeds 2 MB limit")
        return content


def fetch_text(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> str:
    """Fetch text content from a URL and decode it as UTF-8."""

    text = ""
    try:
        text = urlread(url, timeout=timeout).decode("utf-8", "ignore")
    except (OSError, URLError, ValueError) as exc:
        logger.warning("Failed to fetch text from %s: %s", url, exc)
    return text
