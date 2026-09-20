"""Spot runtime ledger family registry."""

from __future__ import annotations

from ..contracts import RuntimeFamilyKind, RuntimeFamilySpec


SIGNALS_FAMILY = "signals"
DENIED_ENTRIES_FAMILY = "denied_entries"
ORDERS_FAMILY = "orders"
POSITIONS_FAMILY = "positions"
FORCE_CLOSES_FAMILY = "force_closes"
METRICS_FAMILY = "metrics"
CYCLE_RUNS_FAMILY = "cycle_runs"
DAILY_SUMMARIES_FAMILY = "daily_summaries"
CANDLES_FAMILY = "candles"
ORDERFLOW_FAMILY = "orderflow"
INDICATOR_SNAPSHOTS_FAMILY = "indicator_snapshots"


ALL_FAMILY_SPECS: tuple[RuntimeFamilySpec, ...] = (
    RuntimeFamilySpec(
        name=SIGNALS_FAMILY,
        kind=RuntimeFamilyKind.EVENT,
        writer_owner="services.signal / services.permission",
        reader_owner="metrics_system / frontend page builders / diagnostics",
        retention="hot 14d, archive 90d, research selected",
        required_keys=("timestamp_ms", "symbol", "timeframe", "side", "score", "threshold", "gates"),
        frontend_used=True,
        description="Spot signal decisions and diagnostic gate state.",
    ),
    RuntimeFamilySpec(
        name=DENIED_ENTRIES_FAMILY,
        kind=RuntimeFamilyKind.EVENT,
        writer_owner="services.permission",
        reader_owner="metrics_system / frontend strategy views / diagnostics",
        retention="hot 14d, archive 90d, research selected",
        required_keys=("timestamp_ms", "reason"),
        frontend_used=True,
        description="Actionable Spot signals denied by permission policy.",
    ),
    RuntimeFamilySpec(
        name=ORDERS_FAMILY,
        kind=RuntimeFamilyKind.EVENT,
        writer_owner="services.permission / services.account",
        reader_owner="portfolio / diagnostics",
        retention="hot 30d, archive 1y",
        required_keys=("timestamp_ms", "symbol", "status", "side"),
        frontend_used=True,
        description="Spot simulated order records.",
    ),
    RuntimeFamilySpec(
        name=POSITIONS_FAMILY,
        kind=RuntimeFamilyKind.EVENT,
        writer_owner="services.account",
        reader_owner="metrics_system / portfolio / diagnostics",
        retention="hot 90d, archive 1y",
        required_keys=("position_id", "symbol", "side", "status", "opened_at"),
        frontend_used=True,
        description="Spot position lifecycle rows.",
    ),
    RuntimeFamilySpec(
        name=FORCE_CLOSES_FAMILY,
        kind=RuntimeFamilyKind.EVENT,
        writer_owner="services.account / services.permission",
        reader_owner="metrics_system / diagnostics",
        retention="hot 90d, archive 1y",
        required_keys=("timestamp_ms", "reason", "position_id"),
        frontend_used=True,
        description="Spot force-close audit rows.",
    ),
    RuntimeFamilySpec(
        name=CYCLE_RUNS_FAMILY,
        kind=RuntimeFamilyKind.EVENT,
        writer_owner="services.ops",
        reader_owner="diagnostics / runtime health",
        retention="hot 14d, archive 90d",
        required_keys=("timestamp_ms", "system", "state"),
        frontend_used=True,
        description="Spot cycle-level observability rows.",
    ),
    RuntimeFamilySpec(
        name=METRICS_FAMILY,
        kind=RuntimeFamilyKind.SNAPSHOT,
        writer_owner="services.metrics_system",
        reader_owner="frontend page builders / diagnostics",
        retention="hot 90d, archive daily summaries",
        required_keys=("date", "equity", "open_positions", "total_net_pnl"),
        frontend_used=True,
        description="Spot aggregate metrics snapshot.",
    ),
    RuntimeFamilySpec(
        name=DAILY_SUMMARIES_FAMILY,
        kind=RuntimeFamilyKind.SNAPSHOT,
        writer_owner="services.ops",
        reader_owner="frontend overview / diagnostics",
        retention="hot 90d, archive 1y",
        required_keys=("date",),
        frontend_used=True,
        description="Spot daily runtime summary.",
    ),
    RuntimeFamilySpec(
        name=CANDLES_FAMILY,
        kind=RuntimeFamilyKind.SNAPSHOT,
        writer_owner="services.market",
        reader_owner="signal / diagnostics",
        retention="latest snapshot, research store separate",
        required_keys=("open", "high", "low", "close"),
        frontend_used=False,
        description="Spot candle snapshots by symbol/timeframe.",
    ),
    RuntimeFamilySpec(
        name=ORDERFLOW_FAMILY,
        kind=RuntimeFamilyKind.SNAPSHOT,
        writer_owner="services.market",
        reader_owner="signal / orderbook frontend / diagnostics",
        retention="latest same-day snapshot, archive selected",
        required_keys=("timestamp_ms",),
        frontend_used=True,
        description="Spot orderflow/orderbook snapshot.",
    ),
    RuntimeFamilySpec(
        name=INDICATOR_SNAPSHOTS_FAMILY,
        kind=RuntimeFamilyKind.SNAPSHOT,
        writer_owner="services.signal",
        reader_owner="signal / overview frontend / diagnostics",
        retention="latest snapshot",
        required_keys=("symbol", "timeframe"),
        frontend_used=True,
        description="Spot indicator context snapshots.",
    ),
)

FAMILY_BY_NAME: dict[str, RuntimeFamilySpec] = {
    spec.name: spec for spec in ALL_FAMILY_SPECS
}
