"""V2 news pipeline package for frontend-owned news generation."""

from .config import V2NewsPipelineConfig, load_config
from .feed_collector import collect_top_news
from .orchestrator import run_news_generation

__all__ = ["V2NewsPipelineConfig", "collect_top_news", "load_config", "run_news_generation"]
