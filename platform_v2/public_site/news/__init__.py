from pathlib import Path

from platform_v2.public_site.news.py.news_pipeline import run_news_generation


class NewsPageBuilder:
    """Compatibility wrapper that delegates News generation to the pipeline."""

    def build_and_store(self) -> Path:
        result = run_news_generation()
        return result["news_index_path"]

EXPORTS = (NewsPageBuilder,)

__all__ = ["NewsPageBuilder"]
