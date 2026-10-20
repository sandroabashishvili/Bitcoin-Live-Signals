# Spot historical backtest

This is the single supported research engine. It recomputes the normal Spot
indicators, decisions, permissions and position/account evolution from historical
market data. The former replay, signal-lab, portfolio-lab and captured-Spot-lab
entry points have been retired. There is no research dependency in live trading.

## Commands

```bash
cd /home/sandro/SmartSignalHub
export LD_LIBRARY_PATH=/home/sandro/SmartSignalHub/platform_v2/shared/native/sqlite
venv/bin/python -m platform_v2.tools.research --help
venv/bin/python -m platform_v2.tools.research prepare /home/sandro/research_snapshots/NEW_EXPERIMENT
venv/bin/python -m platform_v2.tools.research run /home/sandro/research_snapshots/NEW_EXPERIMENT
venv/bin/python -m platform_v2.tools.research run /home/sandro/research_snapshots/NEW_EXPERIMENT --name unchanged
venv/bin/python -m platform_v2.tools.research.spot_backtest.compare /home/sandro/research_snapshots/NEW_EXPERIMENT
```

Use a new output directory, never the live runtime or an existing run. The short
`research` command delegates to `research.spot_backtest`; it is not another engine.
Preparation explicitly captures experiment inputs/code for offline reproducibility;
no live service imports or selects that capture. Preparation may access official
Binance archives. The worker is offline, rejects live runtime access and confines
writes to its private run. Nothing is automatically deployed into the strategy.

## Modules

- `dataset.py`, `recover_gap.py`: historical input validation, coverage and official
  missing-minute recovery, never interpolation.
- `engine.py`, `native_adapters.py`, `worker.py`: native Spot simulation, isolated
  persistence/clock and fail-closed worker.
- `common.py`: hashing, paths and recorded subprocess output; replaces legacy lab helpers.
- `candidates.py`: optional scenario/equal-vote variants, not active production rules.
- `compare.py`, `isolate_compare.py`, `pullback_audit.py`: controls and diagnostics.
- `reconcile_live.py`, `paired_accounts.py`, `paired_support.py`,
  `paired_execution_audit.py`: optional model/recorded-history reconciliation using
  the same engine, not separate trading strategies.

## Data and limitations

The retained `raw_spot_backtest_20261016_gap_recovered_v1/market.sqlite3` under
`/home/sandro/research_snapshots/` is a market dataset, NOT a runnable old experiment.
Its old runs, source capture and comparisons were intentionally deleted. Commands
above prepare a NEW workspace; old profit figures are not current verified results.

Decisions require causal closed 5m/15m/4h inputs and warmup, complete flow, exact
modeled quote and exit-minute coverage. Gaps divide coverage into separate fresh
accounts: summed profits are not a continuous-account return. Open positions are
reported separately, not forced closed. Native fees, fixed 60-second decision delay,
minute-OHLC execution and zero extra slippage are assumptions, not actual fills.
Recorded decisions are retrospective diagnostics, not guaranteed causal replay.
Exact controls establish determinism, not profitability or operational parity.
