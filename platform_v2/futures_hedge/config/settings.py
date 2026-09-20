"""Static defaults for the independent Futures Hedge subsystem."""

from __future__ import annotations

from pathlib import Path

from platform_v2.shared.backend.runtime_store import system_runtime_root


FUTURES_HEDGE_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = system_runtime_root("hedge")
RUNTIME_DATA_ROOT = RUNTIME_ROOT / "data"

DEFAULT_SYMBOL = "BTCUSDT"
DEFAULT_TIMEFRAME = "15m"

DEFAULT_STARTING_CAPITAL_USDT = 3000.0
DEFAULT_POSITION_MARGIN_USDT = 100.0
DEFAULT_LEVERAGE = 5
MIN_LEVERAGE = 1
MAX_LEVERAGE = 50

ENTRY_FEE_PCT = 0.0005
EXIT_FEE_PCT = 0.0005

RESET_AVAILABLE_CAPITAL_USDT = 300.0

SOURCE_POSITION_EVENTS_FAMILY = "futures_position_events"
