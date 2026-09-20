from __future__ import annotations

import json
import traceback

from platform_v2.public_site.news.py.news_pipeline import run_news_generation

from .logging_utils import tee_tool_output


def main() -> None:
    with tee_tool_output("news_generation_system.log"):
        try:
            result = run_news_generation()
            printable = {key: str(value) for key, value in result.items()}
            print(json.dumps(printable, ensure_ascii=False, indent=2))
        except Exception:
            # Keep the traceback in the runtime log even when cron redirects
            # output to the compatibility path.
            traceback.print_exc()
            raise
