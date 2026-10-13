# Full Spot replay (research only)

The Spot laboratory uses the same frozen SQLite/source workspace contract as
the Futures laboratory, but executes **Spot-owned** production services:
PositionBatchUpdateService, SignalRuntimeService, SignalPermissionRuntimeService,
PositionRuntimeService, PortfolioStateService and PaperExecutionAdapter.
No Futures permission, margin, sizing or exit rules are substituted.

## Captured decision stages

Spot first persists a preliminary signal, then a decision timestamp, then an
execution quote for BUY. Replay follows the first LIVE_OBSERVED attempt and its
latest enrichment in that same run/attempt/cycle. A later retry must not replace
the original decision. Pre-batch position documents are recovered from the first
capture's initial read revisions and loaded **once**. Later positions evolve
independently. Canonical paper order timestamps are used only to reproduce the
observed baseline's historical fill time, not to select model/candidate trades.

Captured market revisions are hash-verified. Indicator formulas are unchanged;
Spot's captured snapshots feed the production MTF/context builder. Exit candle
history is bounded by the original cycle and retains the full captured 1m range
for inherited positions. Paper order UUIDs are random and not semantic parity
fields; human-readable Spot position ids and all actual position/account fields
are compared. The live runtime, network, alerts and external execution are denied
by worker guards. Private SQLite output stores daily versions of rows and states.

## Baseline validation

Observed mode compares signal components, directions, gates, confidence, entry
quality, theoretical setup and enriched quote/timestamp fields. Inter-cycle
position states are compared with captured pre-batch documents. Denied-entry
permission details are checked against archive records; the complete run must
match the terminal archived position state. No failed baseline can authorize
modeled/candidate runs. Input/source/output hash changes are rejected.

## Execution model and candidate

The baseline and candidate both use the next exact 1m open strictly after
decision/enrichment/quote availability. This is a modeled price, not a historical
exchange fill claim. Missing quotes are reported and deny new entries.
Existing positions update before the new signal, as in production. Candidate
positions, profit-lock, SL/TP levels, fees, exposure, cooldown and cash evolve
from their own signals. No old trade list is copied into a candidate.

Only Spot MTF changes: 5m RSI/VWAP agreement with shared ADX>20; 15m RSI/EMA50
slope agreement; 4h two of RSI/Tenkan-Kijun/EMA50-200 agreement. BUY and bearish
SELL context are mirrored. Spot never opens a Futures-style SHORT position.
Other long component scores changing on the same cohort abort the experiment.
Weights, master thresholds, entry permission and position-management rules remain
the pinned Spot version. This version does not support changing indicator formulas.

## Commands

```bash
cd /home/sandro/SmartSignalHub
export LD_LIBRARY_PATH=/home/sandro/research_snapshots/readiness_R21_20260927/sqlite
venv/bin/python -m platform_v2.tools.research.spot_lab prepare WORKSPACE
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE --model next-minute
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE --model next-minute --name unchanged
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE --model next-minute --name symmetric_all
venv/bin/python -m platform_v2.tools.research.spot_lab compare WORKSPACE
```

Example workspace: `/home/sandro/research_snapshots/spot_signal_lab_20261012`.
Each run has its own `spot_runs/` directory, worker/adapters, protocol, console log,
portfolio.json, replay.sqlite3 and hash manifest. Existing run folders are never
overwritten. `--limit N` is a smoke check; full historical validation requires the
complete captured interval and matching terminal archive.

## Limits and interpretation

The observed baseline must pass before comparisons. The unchanged modeled
candidate must reproduce every semantic cycle path, not only terminal PnL.
The report compares realized period net after fees, final equity including open
positions, cycle drawdown, permissions and a chronological split at the previous
Futures research cutoff. The earlier calendar overlaps candidate selection;
the later roughly two-day segment is too short for independent validation.
The split keeps evolving account state rather than resetting each subperiod.

No automatic production promotion. OHLC stop-first/profit-lock policy follows
production; exact intrabar exchange fills, liquidity, spread and slippage are not
claimed. The starting account includes inherited positions and closed results;
only recognized closed-net change is called period net PnL. Open positions are
not artificially closed at the end. Research results alone do not modify live
Spot or Futures and do not imply a profitable strategy.
