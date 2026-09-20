"""Futures runtime ledger family registry."""

from __future__ import annotations

from ..contracts import RuntimeFamilyKind, RuntimeFamilySpec


SIGNALS_FAMILY = "futures_signals"
DENIED_ENTRIES_FAMILY = "futures_denied_entries"
ORDERS_FAMILY = "futures_orders"
POSITIONS_FAMILY = "futures_positions"
POSITION_EVENTS_FAMILY = "futures_position_events"
FORCE_CLOSES_FAMILY = "futures_force_closes"
TRADE_ENTRY_AUDITS_FAMILY = "futures_trade_entry_audits"
ENTRY_TIMING_SUMMARIES_FAMILY = "futures_entry_timing_summaries"
TRADE_AUDIT_REPORTS_FAMILY = "futures_trade_audit_reports"
TUNING_AUDIT_REPORTS_FAMILY = "futures_tuning_audit_reports"
SHORT_FAILURE_REPORTS_FAMILY = "futures_short_failure_reports"
STRATEGY_GATE_EFFECTIVENESS_REPORTS_FAMILY = "futures_strategy_gate_effectiveness_reports"
TRADE_GATE_EFFECTIVENESS_REPORTS_FAMILY = "futures_trade_gate_effectiveness_reports"
MARKET_PLANS_FAMILY = "futures_market_plans"
METRICS_FAMILY = "futures_metrics"
CYCLE_RUNS_FAMILY = "futures_cycle_runs"
DAILY_SUMMARIES_FAMILY = "futures_daily_summaries"
CANDLES_FAMILY = "candles_futures"
ORDERFLOW_FAMILY = "orderflow_futures"
INDICATOR_SNAPSHOTS_FAMILY = "indicator_snapshots_futures"
ENGINE_STATE_FAMILY = "engine_state_futures"


ALL_FAMILY_SPECS: tuple[RuntimeFamilySpec, ...] = (
    RuntimeFamilySpec(
        name=SIGNALS_FAMILY,
        kind=RuntimeFamilyKind.EVENT,
        writer_owner="futures.services.simulation",
        reader_owner="futures metrics_system / frontend page builders / diagnostics",
        retention="hot 14d, archive 90d, research selected",
        required_keys=("timestamp_ms", "symbol", "timeframe", "side", "score", "threshold", "gates"),
        frontend_used=True,
        description="Futures LONG/SHORT/NO_SIGNAL decisions and direction diagnostics.",
    ),
    RuntimeFamilySpec(
        name=DENIED_ENTRIES_FAMILY,
        kind=RuntimeFamilyKind.EVENT,
        writer_owner="futures.services.simulation",
        reader_owner="futures metrics_system / strategy frontend / diagnostics",
        retention="hot 14d, archive 90d, research selected",
        required_keys=("timestamp_ms", "reason", "signal_side"),
        frontend_used=True,
        description="Futures actionable signals denied by permission policy.",
    ),
    RuntimeFamilySpec(
        name=ORDERS_FAMILY,
        kind=RuntimeFamilyKind.EVENT,
        writer_owner="futures.services.simulation",
        reader_owner="portfolio / diagnostics",
        retention="hot 30d, archive 1y",
        required_keys=("timestamp_ms", "symbol", "status", "side", "position_side"),
        frontend_used=True,
        description="Futures simulated order records with exchange side and position direction.",
    ),
    RuntimeFamilySpec(
        name=POSITIONS_FAMILY,
        kind=RuntimeFamilyKind.STATE,
        writer_owner="derived from futures_position_events",
        reader_owner="futures metrics_system / portfolio / diagnostics",
        retention="hot 90d, archive 1y",
        required_keys=("position_id", "symbol", "side", "status", "opened_at"),
        frontend_used=True,
        description="Virtual latest-position projection derived by position_id from Futures lifecycle events.",
        persisted=False,
        derived_from=(POSITION_EVENTS_FAMILY,),
    ),
    RuntimeFamilySpec(
        name=POSITION_EVENTS_FAMILY,
        kind=RuntimeFamilyKind.EVENT,
        writer_owner="futures.services.simulation",
        reader_owner="futures analytics / notifications / diagnostics",
        retention="hot 90d, archive 1y",
        required_keys=("position_id", "symbol", "side", "status", "event", "timestamp_ms"),
        frontend_used=False,
        description="Futures LONG/SHORT position lifecycle event history.",
    ),
    RuntimeFamilySpec(
        name=FORCE_CLOSES_FAMILY,
        kind=RuntimeFamilyKind.EVENT,
        writer_owner="futures.services.simulation",
        reader_owner="futures metrics_system / diagnostics",
        retention="hot 90d, archive 1y",
        required_keys=("timestamp_ms", "reason", "position_id"),
        frontend_used=True,
        description="Futures force-close audit rows.",
    ),
    RuntimeFamilySpec(
        name=TRADE_ENTRY_AUDITS_FAMILY,
        kind=RuntimeFamilyKind.EVENT,
        writer_owner="futures.services.analytics",
        reader_owner="strategy tuning / diagnostics",
        retention="hot 90d, archive research selected",
        required_keys=("position_id", "side", "outcome", "entry_timing_type"),
        frontend_used=False,
        description="Closed Futures trade attribution with entry-time signal and indicator context.",
    ),
    RuntimeFamilySpec(
        name=ENTRY_TIMING_SUMMARIES_FAMILY,
        kind=RuntimeFamilyKind.SNAPSHOT,
        writer_owner="futures.services.analytics.trade_audit",
        reader_owner="strategy tuning / diagnostics",
        retention="hot 90d, archive research selected",
        required_keys=("date", "total_trades", "by_timing", "by_side_timing"),
        frontend_used=False,
        description="Daily Futures entry timing performance summary by timing bucket and direction.",
    ),
    RuntimeFamilySpec(
        name=TRADE_AUDIT_REPORTS_FAMILY,
        kind=RuntimeFamilyKind.SNAPSHOT,
        writer_owner="futures.services.analytics.trade_audit",
        reader_owner="strategy tuning / diagnostics / future frontend audit page",
        retention="hot 90d, archive research selected",
        required_keys=("date", "window_start", "window_end", "sample_size", "sample_status"),
        frontend_used=False,
        description="Multi-day Futures trade audit report for rule tuning decisions.",
    ),
    RuntimeFamilySpec(
        name=TUNING_AUDIT_REPORTS_FAMILY,
        kind=RuntimeFamilyKind.SNAPSHOT,
        writer_owner="futures.services.analytics.trade_audit",
        reader_owner="strategy tuning / diagnostics",
        retention="hot 90d, archive research selected",
        required_keys=("date", "sample_size", "by_side", "candidate_rules"),
        frontend_used=False,
        description="Focused Futures tuning audit across side, timing, location, market-plan alignment, and gate combinations.",
    ),
    RuntimeFamilySpec(
        name=SHORT_FAILURE_REPORTS_FAMILY,
        kind=RuntimeFamilyKind.SNAPSHOT,
        writer_owner="futures.services.analytics.trade_audit",
        reader_owner="strategy tuning / diagnostics",
        retention="hot 90d, archive research selected",
        required_keys=("date", "window_start", "window_end", "short_sample_size", "short_net_pnl"),
        frontend_used=False,
        description="SHORT-only Futures failure attribution across timing, location, gates, and market-plan alignment.",
    ),
    RuntimeFamilySpec(
        name=STRATEGY_GATE_EFFECTIVENESS_REPORTS_FAMILY,
        kind=RuntimeFamilyKind.SNAPSHOT,
        writer_owner="futures.services.analytics.gate_effectiveness",
        reader_owner="futures strategy frontend / diagnostics",
        retention="hot 90d, archive research selected",
        required_keys=("date", "strategy_logic_evaluation", "signal_activity_summary"),
        frontend_used=True,
        description="Daily backend-computed Futures strategy/signal-side gate effectiveness snapshot.",
    ),
    RuntimeFamilySpec(
        name=TRADE_GATE_EFFECTIVENESS_REPORTS_FAMILY,
        kind=RuntimeFamilyKind.SNAPSHOT,
        writer_owner="futures.services.analytics.gate_effectiveness",
        reader_owner="futures trade outcomes frontend / diagnostics",
        retention="hot 90d, archive research selected",
        required_keys=("date", "trade_outcomes_logic_evaluation"),
        frontend_used=True,
        description="Daily backend-computed Futures executed-trade gate effectiveness snapshot.",
    ),
    RuntimeFamilySpec(
        name=MARKET_PLANS_FAMILY,
        kind=RuntimeFamilyKind.EVENT,
        writer_owner="futures.services.analytics.market_plan",
        reader_owner="strategy tuning / diagnostics / future frontend plan view",
        retention="hot 90d, archive research selected",
        required_keys=("date", "timestamp_ms", "symbol", "timeframe", "bias", "current_price"),
        frontend_used=False,
        description="Per-cycle Futures trader-style market plan with LONG/SHORT working zones.",
    ),
    RuntimeFamilySpec(
        name=CYCLE_RUNS_FAMILY,
        kind=RuntimeFamilyKind.EVENT,
        writer_owner="futures.services.ops",
        reader_owner="diagnostics / runtime health",
        retention="hot 14d, archive 90d",
        required_keys=("timestamp_ms", "system", "state"),
        frontend_used=True,
        description="Futures cycle-level observability rows.",
    ),
    RuntimeFamilySpec(
        name=METRICS_FAMILY,
        kind=RuntimeFamilyKind.SNAPSHOT,
        writer_owner="futures.services.simulation.metrics_service",
        reader_owner="futures frontend page builders / diagnostics",
        retention="hot 90d, archive daily summaries",
        required_keys=("date", "equity", "open_positions", "total_net_pnl"),
        frontend_used=True,
        description="Futures aggregate metrics snapshot.",
    ),
    RuntimeFamilySpec(
        name=DAILY_SUMMARIES_FAMILY,
        kind=RuntimeFamilyKind.SNAPSHOT,
        writer_owner="futures.services.ops",
        reader_owner="futures overview / diagnostics",
        retention="hot 90d, archive 1y",
        required_keys=("date",),
        frontend_used=True,
        description="Futures daily runtime summary.",
    ),
    RuntimeFamilySpec(
        name=CANDLES_FAMILY,
        kind=RuntimeFamilyKind.SNAPSHOT,
        writer_owner="futures.services.market",
        reader_owner="futures signal / diagnostics",
        retention="latest snapshot, research store separate",
        required_keys=("open", "high", "low", "close"),
        frontend_used=False,
        description="Futures candle snapshots by symbol/timeframe.",
    ),
    RuntimeFamilySpec(
        name=ORDERFLOW_FAMILY,
        kind=RuntimeFamilyKind.SNAPSHOT,
        writer_owner="futures.services.market",
        reader_owner="futures signal / orderbook frontend / diagnostics",
        retention="latest same-day snapshot, archive selected",
        required_keys=("timestamp_ms",),
        frontend_used=True,
        description="Futures orderflow/orderbook snapshot.",
    ),
    RuntimeFamilySpec(
        name=INDICATOR_SNAPSHOTS_FAMILY,
        kind=RuntimeFamilyKind.SNAPSHOT,
        writer_owner="futures.services.analytics",
        reader_owner="futures signal / diagnostics / trade entry audit",
        retention="latest snapshot, archive selected",
        required_keys=("symbol", "timeframe", "timestamp_ms", "price"),
        frontend_used=False,
        description="Futures indicator snapshots built from Binance Futures candles.",
    ),
    RuntimeFamilySpec(
        name=ENGINE_STATE_FAMILY,
        kind=RuntimeFamilyKind.STATE,
        writer_owner="futures.services.simulation.state_store",
        reader_owner="futures simulation engine",
        retention="current state, archive on reset",
        required_keys=("open_positions", "stats", "next_position_id"),
        frontend_used=False,
        description="Futures simulation memory used to continue open positions across cycles.",
    ),
)

FAMILY_BY_NAME: dict[str, RuntimeFamilySpec] = {
    spec.name: spec for spec in ALL_FAMILY_SPECS
}
