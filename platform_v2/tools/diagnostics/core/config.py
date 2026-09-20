"""Shared diagnostics configuration."""

from __future__ import annotations

from pathlib import Path


V2_ROOT = Path(__file__).resolve().parents[3]
SCAN_ROOTS = (
    "app",
    "config",
    "domain",
    "futures",
    "futures_hedge",
    "infrastructure",
    "public_site",
    "runtime",
    "services",
    "shared",
    "spot",
    "storage",
    "tools",
)
TOP_LEVEL_DIRS = (
    "app",
    "automation",
    "config",
    "content",
    "docs",
    "domain",
    "engine",
    "futures",
    "futures_hedge",
    "infrastructure",
    "public_site",
    "runtime",
    "services",
    "shared",
    "spot",
    "tools",
    "web",
)
MAX_OK_LINES = 400
HIGH_FILE_LINES = 600
MAX_OK_FUNCTION_LINES = 80
HIGH_FUNCTION_LINES = 120
SHARED_HELPER_OK_LINES = 250
COMPLEXITY_THRESHOLD = 20
HIGH_COMPLEXITY_THRESHOLD = 35
PRINT_HEAVY_THRESHOLD = 6
DEBUG_MARKERS = ("temporary", "temp fix", "legacy fallback", "todo")
COMMENT_MARKERS = ("fixme", "hack", "xxx")
CONFIG_DRIFT_TOKENS = ("threshold", "balance", "ratio", "pct", "percent", "multiplier", "limit", "lookback")
ALLOWED_LITERAL_NUMBERS = {0, 0.0, 1, 1.0, -1, -1.0, 2, 2.0, 5, 10, 100}
RUNTIME_FAMILIES = (
    "candles",
    "indicator_snapshots",
    "orderflow",
    "signals",
    "positions",
    "orders",
    "metrics",
    "denied_entries",
    "cycle_runs",
    "daily_summaries",
)
RUNTIME_GROWTH_TRACKED_FAMILIES = (
    "signals",
    "positions",
    "orders",
    "denied_entries",
    "cycle_runs",
    "daily_summaries",
    "metrics",
)
RUNTIME_FAMILY_WARNING_DAYS = 45
RUNTIME_FAMILY_HIGH_DAYS = 90
RUNTIME_JSON_WARNING_BYTES = 250_000
RUNTIME_JSON_HIGH_BYTES = 1_000_000
RUNTIME_JSON_WARNING_ROWS = 1_000
RUNTIME_JSON_HIGH_ROWS = 5_000
SIGNAL_REQUIRED_KEYS = ("timestamp_ms", "symbol", "timeframe", "side", "snapshot_price", "score", "threshold", "gates")
SIGNAL_GATE_KEYS = ("mtf", "regime", "momentum", "trend", "orderbook", "structure")
POSITION_REQUIRED_KEYS = ("position_id", "symbol", "timeframe", "side", "status", "execution", "opened_at")
POSITION_EXECUTION_KEYS = ("entry_price", "stop_loss", "take_profit", "rr_ratio", "position_size", "mode")
ORDER_REQUIRED_KEYS = ("request", "status")
ORDER_REQUEST_KEYS = ("symbol", "timeframe", "side", "order_type", "quantity", "client_order_id", "requested_at_ms")
METRICS_REQUIRED_KEYS = (
    "date",
    "datetime",
    "starting_capital",
    "available_balance",
    "reserved_capital",
    "equity",
    "total_net_pnl",
    "unrealized_pnl",
    "open_positions",
    "closed_positions",
    "total_positions",
    "tp_hits",
    "sl_hits",
    "force_close_events",
    "win_rate",
    "avg_net_per_trade",
    "best_trade",
    "worst_trade",
    "peak_capital",
    "lowest_capital",
)
DENIED_REQUIRED_KEYS = ("signal", "permission", "live_entry_price", "denial_reason")
