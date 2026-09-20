from __future__ import annotations

from pathlib import Path

from platform_v2.futures.config import ExecutionProfile
from platform_v2.futures.dashboard.overview_futures.py.page_builder import (
    OverviewFuturesPageBuilder,
)
from platform_v2.futures.dashboard.portfolio_futures.py.page_builder import (
    PortfolioFuturesPageService,
)
from platform_v2.futures.dashboard.trade_outcomes_futures.py.page_builder import (
    TradeOutcomesFuturesPageService,
)
from platform_v2.futures.dashboard.strategy_edge_futures.py.page_builder import (
    StrategyEdgeFuturesPageService,
)
from platform_v2.futures.dashboard.orderbook_futures.py.page_builder import (
    OrderbookFuturesPageService,
)
from platform_v2.futures_hedge.dashboard.overview_hedge import FuturesHedgeOverviewPageService
from platform_v2.futures_hedge.services.replay import FuturesHedgeReplayService
from platform_v2.futures.services.market import BinanceFuturesOrderflowService
from platform_v2.futures.services.analytics import (
    FuturesAggregateAuditReportService,
    FuturesEntryTimingSummaryService,
    FuturesGateEffectivenessReportService,
    FuturesMarketPlanService,
    FuturesShortFailureReportService,
    FuturesTradeEntryAuditService,
    FuturesTuningAuditReportService,
)
from platform_v2.futures.services.simulation import DirectionalFuturesSimulationService

from .models import CycleKeyInfo, MainCycleResult


class MainCycleExecutionService:
    """Execute the ready-state futures cycle body."""

    def __init__(
        self,
        orderflow_service: BinanceFuturesOrderflowService | None = None,
        simulation_service: DirectionalFuturesSimulationService | None = None,
        page_builder: OverviewFuturesPageBuilder | None = None,
        portfolio_page_service: PortfolioFuturesPageService | None = None,
        trade_outcomes_page_service: TradeOutcomesFuturesPageService | None = None,
        strategy_edge_page_service: StrategyEdgeFuturesPageService | None = None,
        orderbook_page_service: OrderbookFuturesPageService | None = None,
        hedge_replay_service: FuturesHedgeReplayService | None = None,
        hedge_overview_page_service: FuturesHedgeOverviewPageService | None = None,
        trade_entry_audit_service: FuturesTradeEntryAuditService | None = None,
        entry_timing_summary_service: FuturesEntryTimingSummaryService | None = None,
        aggregate_audit_report_service: FuturesAggregateAuditReportService | None = None,
        short_failure_report_service: FuturesShortFailureReportService | None = None,
        tuning_audit_report_service: FuturesTuningAuditReportService | None = None,
        gate_effectiveness_report_service: FuturesGateEffectivenessReportService | None = None,
        market_plan_service: FuturesMarketPlanService | None = None,
    ) -> None:
        self._orderflow_service = orderflow_service or BinanceFuturesOrderflowService()
        self._simulation_service = simulation_service or DirectionalFuturesSimulationService()
        self._page_builder = page_builder or OverviewFuturesPageBuilder()
        self._portfolio_page_service = portfolio_page_service or PortfolioFuturesPageService()
        self._trade_outcomes_page_service = (
            trade_outcomes_page_service or TradeOutcomesFuturesPageService()
        )
        self._strategy_edge_page_service = (
            strategy_edge_page_service or StrategyEdgeFuturesPageService()
        )
        self._orderbook_page_service = orderbook_page_service or OrderbookFuturesPageService()
        self._hedge_replay_service = hedge_replay_service or FuturesHedgeReplayService()
        self._hedge_overview_page_service = (
            hedge_overview_page_service or FuturesHedgeOverviewPageService()
        )
        self._trade_entry_audit_service = trade_entry_audit_service or FuturesTradeEntryAuditService()
        self._entry_timing_summary_service = (
            entry_timing_summary_service or FuturesEntryTimingSummaryService()
        )
        self._aggregate_audit_report_service = (
            aggregate_audit_report_service or FuturesAggregateAuditReportService()
        )
        self._short_failure_report_service = (
            short_failure_report_service or FuturesShortFailureReportService()
        )
        self._tuning_audit_report_service = (
            tuning_audit_report_service or FuturesTuningAuditReportService()
        )
        self._gate_effectiveness_report_service = (
            gate_effectiveness_report_service or FuturesGateEffectivenessReportService()
        )
        self._market_plan_service = market_plan_service or FuturesMarketPlanService()

    def run_ready_cycle(
        self,
        *,
        profile: ExecutionProfile,
        date_iso: str,
        fetched_candle_paths: tuple[Path, ...],
        cycle_info: CycleKeyInfo,
    ) -> MainCycleResult:
        fetched_orderflow_path = self._orderflow_service.fetch_and_store(
            symbol=profile.symbol,
            timeframe=profile.timeframe,
            limit=1000,
            lookback_hours=24,
        )
        self._market_plan_service.build_and_store(
            date_iso=date_iso,
            symbol=profile.symbol,
            timeframe=profile.timeframe,
        )
        summary = self._simulation_service.run(profile=profile, date_iso=date_iso)
        self._trade_entry_audit_service.build_and_store(date_iso=date_iso)
        self._entry_timing_summary_service.build_and_store(date_iso=date_iso)
        self._aggregate_audit_report_service.build_and_store(date_iso=date_iso)
        self._short_failure_report_service.build_and_store(date_iso=date_iso)
        self._tuning_audit_report_service.build_and_store(date_iso=date_iso)
        self._gate_effectiveness_report_service.build_and_store(date_iso=date_iso)
        hedge_report_path = self._hedge_replay_service.build_and_store()
        hedge_page_path = self._hedge_overview_page_service.build_and_store()
        page_path = self._page_builder.build_and_store(profile=profile, cycle_summary=summary)
        updated_page_paths = (
            page_path,
            self._portfolio_page_service.build_and_store(),
            self._trade_outcomes_page_service.build_and_store(),
            self._strategy_edge_page_service.build_and_store(),
            self._orderbook_page_service.build_and_store(symbol=profile.symbol, timeframe=profile.timeframe),
        )
        return MainCycleResult(
            cycle_key=cycle_info.key,
            cycle_state=cycle_info.state,
            cycle_note=cycle_info.note,
            skipped=False,
            skip_reason=None,
            fetched_candle_paths=fetched_candle_paths,
            fetched_orderflow_path=fetched_orderflow_path,
            summary=summary,
            page_path=page_path,
            updated_page_paths=updated_page_paths,
            hedge_report_path=hedge_report_path,
            hedge_page_path=hedge_page_path,
            cycle_run_path=None,
            daily_summary_path=None,
        )
