"""Metrics system for SmartSignalHub V2."""

from .grouped_payloads import (
    build_overview_portfolio_snapshot_items,
    build_overview_strategy_snapshot_items,
    build_overview_trade_outcomes_snapshot_items,
    build_portfolio_capital_snapshot_items,
    build_portfolio_trade_outcome_items,
    build_strategy_activity_evaluation_items,
    build_strategy_activity_items,
    build_strategy_funnel_items,
    build_strategy_outcome_items,
    build_strategy_page_snapshot_items,
)
from .overview_content import OverviewPageContentService
from .orderbook_content import OrderbookPageContentService
from .portfolio_content import PortfolioPageContentService
from .summary_service import MetricsSummaryService

__all__ = [
    "MetricsSummaryService",
    "build_portfolio_capital_snapshot_items",
    "build_portfolio_trade_outcome_items",
    "build_overview_portfolio_snapshot_items",
    "build_overview_trade_outcomes_snapshot_items",
    "build_overview_strategy_snapshot_items",
    "build_strategy_activity_evaluation_items",
    "build_strategy_activity_items",
    "build_strategy_outcome_items",
    "build_strategy_funnel_items",
    "build_strategy_page_snapshot_items",
    "OverviewPageContentService",
    "OrderbookPageContentService",
    "PortfolioPageContentService",
]
