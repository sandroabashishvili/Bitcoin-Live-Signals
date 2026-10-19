# Raw-market Spot backtest

Retention checkpoint, 2026-10-18: the retained current dataset is
`/home/sandro/research_snapshots/raw_spot_backtest_20261016_gap_recovered_v1/`.
Older segmented/captured input workspaces were deliberately removed. Their
thin reports are not runnable workspaces. Commands using `NEW_RAW_SPOT_EXPERIMENT`
are examples for a NEW preparation, not instructions to overwrite retained runs.
Use `~/research_snapshots/SPOT_RESEARCH_RESULTS.md` for existing current evidence.

## Matched fresh-account diagnostic

`paired_accounts.py MARKET_ROOT EVIDENCE_ROOT NEW_OUTPUT` creates a separate
frozen workspace from a verified baseline and a sealed `reconcile_live.py`
snapshot. It runs recomputed decisions, recorded decisions and an exact
recomputed control from the SAME first common candle and empty native 3,000
USDT account. Warmup history is preserved outside the account window. Both
arms use the same native permissions, fixed quotes and exit clock. Missing
recorded decisions skip entry in BOTH accounts, without fabricating NO_SIGNAL
or skipping exit management. Existing datasets/runs and live runtime stay intact.

The recorded arm is a retrospective diagnostic, NOT a tradable causal backtest:
original decisions may have been known after the modeled quote time. Original
scores/confidence/theoretical setup are retained, execution quotes/timestamps
are not; entry quality is recalculated against the fresh signal history.
Reconstructed market context is used in both arms. This does not reproduce
operational fills, prove complete production parity, or isolate ORDERBOOK as
the sole cause of profit differences. The report and per-cycle evidence are
sealed; the unchanged recomputed control must match exactly.

This is different from the captured-decision replay in `../SPOT_LAB.md`: it
recomputes indicators and current pinned decisions from historical market data.
Old signals, positions, indicator snapshots and broken old flow are NOT imported.
It is a new modeled history, never a rewrite of the actual operational ledger.

## Commands

From `/home/sandro/SmartSignalHub` with the configured private SQLite runtime:

```bash
export LD_LIBRARY_PATH=/home/sandro/research_snapshots/readiness_R21_20260927/sqlite
venv/bin/python -m platform_v2.tools.research.spot_backtest prepare /home/sandro/research_snapshots/NEW_RAW_SPOT_EXPERIMENT
venv/bin/python -m platform_v2.tools.research.spot_backtest run /home/sandro/research_snapshots/NEW_RAW_SPOT_EXPERIMENT
venv/bin/python -m platform_v2.tools.research.spot_backtest run /home/sandro/research_snapshots/NEW_RAW_SPOT_EXPERIMENT --name unchanged
venv/bin/python -m platform_v2.tools.research.spot_backtest run /home/sandro/research_snapshots/NEW_RAW_SPOT_EXPERIMENT --name control_v2
venv/bin/python -m platform_v2.tools.research.spot_backtest run /home/sandro/research_snapshots/NEW_RAW_SPOT_EXPERIMENT --name votes_existing_v1
venv/bin/python -m platform_v2.tools.research.spot_backtest run /home/sandro/research_snapshots/NEW_RAW_SPOT_EXPERIMENT --name scenarios_votes_v1
venv/bin/python -m platform_v2.tools.research.spot_backtest.compare /home/sandro/research_snapshots/NEW_RAW_SPOT_EXPERIMENT
```

Preparation and run directories must be new. Never reuse the example destination
after it already exists. The unchanged run is a deterministic control, not another
strategy. Automatic candidate selection or promotion is not implemented.

## Input preparation

- Read only Binance BTCUSDT **Spot** candles from market SQLite, current source
  first and then reset archives newest to oldest. Conflicting overlap is counted,
  not silently overwritten. Validate alignment, close time, finite OHLCV and shape.
- Preserve actual gaps; do not invent or interpolate candles. Sources/import
  provenance and coverage segments are recorded in `protocol.json`.
- Historical executed-flow volumes come from official Binance Spot 15m klines:
  taker-buy base volume is buyers; total base volume minus buyers is sellers.
  Compare all OHLCV fields with local candles before accepting flow for a period.
  Verify each downloaded ZIP with its official SHA-256 checksum and keep it.
- Normalize post-2025 microsecond timestamps to the project's millisecond clock.
  Exchange trade count is stored as `raw_trade_count`: it is **not** aggregate
  trade count. Raw first/last trade times and page counts are not invented.
- `flow_crosscheck.json` compares these quantities with already verified paginated
  aggregate-trade snapshots. A run requires at least one successful overlapping
  calibration and no volume mismatch. Preparation can report unavailable files;
  periods without trusted flow are excluded, not neutralized with zero scores.

Provider contract: https://github.com/binance/binance-public-data

## Simulation and safety

The worker verifies the pinned Python release and frozen market SHA-256 before
imports. It denies network calls, subprocesses, live runtime file access and
writes outside its private run. The market SQLite is immutable/read-only.
Native Spot signal, entry-quality, permission, portfolio, sizing, fee, SL/TP and
profit-lock services run through the existing private persistence/clock adapters.
The research market-context adapter supplies freshly recomputed native indicators,
native MTF signals and explicit `RESEARCH_VERIFIED_CANDLE_FLOW_V1` snapshots. It
does not pretend these are original captured `COMPLETE_CLOSED_WINDOW_V1` records.

Native indicators are computed on each contiguous history segment. Values are
causal prefixes (tested by appending future bars), with at least 200 prior/current
closed bars per 5m/15m/4h timeframe. Full contiguous-history initialization can
differ from an old live collector's rolling history length; this is not historical
decision-parity reproduction. Current signal formulas themselves are unchanged
for baseline/unchanged/control_v2; named candidates explicitly replace decisions.

Signals are evaluated only after the relevant candle closes; a declared 60-second
delay supplies the exact subsequent 1m open as a modeled execution quote. Only
already closed 1m candles enter exit management. Missing warmup, flow, quote or
exit minutes excludes the decision. Non-consecutive eligible decisions split the
simulation into separate empty accounts (native default starting balance), so
open positions are not carried across unknown history or secretly liquidated.
Final open positions are reported/marked, not silently treated as closed profit.

Report each segment separately. Summed closed net across segments is NOT a return
on one continuously invested account. Native fees are included; additional
slippage is zero in this first baseline. OHLC fills, fixed timing and archive
revisions are modeling assumptions, not evidence of actual exchange execution.

`results.json` contains accounts, positions and exclusions; `cycles.jsonl` contains
each signal/permission/account step; `manifest.json` seals the worker/data-adapter
sources and outputs. Candidate code and numeric rules are sealed in each private
run's `pre_run_manifest.json` BEFORE execution, then checked by the offline worker.

## Equal votes and five scenarios (exploratory v1)

`candidates.py:PROTOCOL` fixes all definitions before the first candidate result.
Both candidates keep 5m/15m/4h, the same cohort, native account permissions,
capital, sizing, fees, exit functions and native weighted setup confidence.
The original confidence remains a separate native setup input: "equal weights"
means equal signal votes, not removal of every downstream dependency on old
weighted scores. Entry times/history and thus positions/adaptive setups change.

- `votes_existing_v1`: existing six LONG gate booleans become 0/1 votes. BUY at
  >=4; opposing SHORT-score veto removed. This changes aggregation AND that veto,
  not just one numeric weight. No scenario trigger is required in this reference.
- `scenarios_votes_v1`: closed-bar pullback, breakout, bullish reversal, range
  bounce and failed-break/reclaim detectors; simplified scenario-aware votes.
  At least one detected scenario must have >=4/6 votes. Scenarios are alternatives,
  not five simultaneous mandatory filters. STRUCTURE repeats the mandatory
  detector, so effectively at least three other votes are required. These votes
  share price inputs and are NOT six independent pieces of evidence.
- Overlapping matches emit only ONE decision; declared scenario order determines
  its label, while all matches and vote vectors remain in `cycles.jsonl`.
- `control_v2` must reproduce the old baseline's entire results and all 7,244
  cycle records exactly. Comparison aborts if parity or the shared cohort fails.

`compare.py` verifies manifests and emits a new comparison directory (never
overwrites a prior report). It reports each segment, BUY states, continuous BUY
episodes, positions, all failed permission checks, overlapping detections and
one-label position attribution. Attribution within a combined strategy is NOT
an isolated scenario backtest. Episode 1/4/12h forward-close changes have no fees,
fills or matched market benchmark and are diagnostics, not tradable PnL.

All available history here is exploratory: no holdout or statistical claim of
superiority, no automatic live deployment. Independent per-scenario account
runs use the separate experiment below. New-timeframe comparisons and slippage
stress remain separate experiments.

## Standalone scenario accounts (same frozen v1 definitions)

The next experiment changes ONLY which scenario is enabled. The native execution
pipeline still sees each scenario's own chronological signal history and private
account, so permissions and trades must be rerun, not copied out of the combined
run. Every covered segment starts with its own empty native 3,000 USDT account.

```bash
venv/bin/python -m platform_v2.tools.research.spot_backtest run /home/sandro/research_snapshots/NEW_RAW_SPOT_EXPERIMENT --name scenarios_control_v2
venv/bin/python -m platform_v2.tools.research.spot_backtest run /home/sandro/research_snapshots/NEW_RAW_SPOT_EXPERIMENT --name scenario_pullback_v1
venv/bin/python -m platform_v2.tools.research.spot_backtest run /home/sandro/research_snapshots/NEW_RAW_SPOT_EXPERIMENT --name scenario_breakout_v1
venv/bin/python -m platform_v2.tools.research.spot_backtest run /home/sandro/research_snapshots/NEW_RAW_SPOT_EXPERIMENT --name scenario_reversal_v1
venv/bin/python -m platform_v2.tools.research.spot_backtest run /home/sandro/research_snapshots/NEW_RAW_SPOT_EXPERIMENT --name scenario_range_bounce_v1
venv/bin/python -m platform_v2.tools.research.spot_backtest run /home/sandro/research_snapshots/NEW_RAW_SPOT_EXPERIMENT --name scenario_failed_break_v1
venv/bin/python -m platform_v2.tools.research.spot_backtest.isolate_compare /home/sandro/research_snapshots/NEW_RAW_SPOT_EXPERIMENT
```

These directories must not already exist. The driver rejects rules differing
from the original combined experiment before creating a run. New reports go to
`comparisons/scenarios_isolated_v1`; existing reports remain untouched.

`isolate_compare.py` verifies all manifest hashes; the new combined control must
match the old combined results and every cycle exactly. Each isolated run must
have identical detector/vote function ASTs, identical per-cycle vote vectors,
the exact same cohort and preserved native confidence. Its BUY decisions must
be the original combined scenario's valid signal subset, without fallback to
inactive scenarios. Position entries must have their own BUY and ALLOWED
permission. Pairwise overlap and all failed permission checks are reported.

Standalone account profits must NOT be added as if they formed one portfolio;
several scenarios can enter overlapping trades. Neither a high total nor a
small positive sample on this already inspected history proves an improvement.

## Read-only pullback diagnosis

```bash
venv/bin/python -m platform_v2.tools.research.spot_backtest run /home/sandro/research_snapshots/NEW_RAW_SPOT_EXPERIMENT --name pullback_audit_v1
```

This is an audit, NOT another candidate. The source-pinned, offline worker verifies
the original isolated-run manifest and recomputes causal 15m indicators. It joins
every position to its original BUY, describes vote-pattern outcomes by segment,
and checks prior three-bar close changes, each prior bar's own EMA9 contact and
close recross. These diagnostic flags do not alter the original detector.

Forward 1/4/12-hour prices start at the modeled ENTRY minute open, not at the
trade's exit. Every minute must exist and remain inside the tested segment.
Open positions are excluded from closed PnL. No future diagnostic is fed back
into a historical decision. Reports go to the new private run directory;
existing outputs cannot be overwritten. The human diagnosis is retained at
`comparisons/pullback_diagnosis_v1/REPORT.md` in the frozen workspace.

These post-hoc groups are correlated and selected by execution permissions.
They identify hypotheses, not causal gate benefits or holdout validation.

## Official recovery of the known missing minutes

```bash
venv/bin/python -m platform_v2.tools.research.spot_backtest.recover_gap /home/sandro/research_snapshots/NEW_RAW_SPOT_EXPERIMENT /home/sandro/research_snapshots/raw_spot_backtest_20261016_gap_recovered_v1
```

The target MUST be new and separate. Fetches the official BTCUSDT Spot 1m daily
ZIP and checksum, validates a complete unique day, compares every existing daily
1m OHLCV row and both enclosing 15m aggregates, then inserts ONLY the declared
21 absent minutes into a cloned database. All original input/result files and
live runtime stay untouched. Provider mismatch or unavailable data aborts; an
incomplete target gets `RECOVERY_FAILED.json` and must not be used.

Pinned native source and historical flow provenance are copied, not substituted
with newer logic. The new protocol links the old dataset hashes and exact repair
source. Recovery does not relabel old two-account results as continuous-account
performance: future replays must generate their own distinct results.

User-facing experiment/data index:
`/home/sandro/research_snapshots/SPOT_RESEARCH_RESULTS.md`.

## Continuous-account round after minute recovery

Workspace: `/home/sandro/research_snapshots/raw_spot_backtest_20261016_gap_recovered_v1`.
Its `continuous_experiment_protocol.json` was declared before the first replay.
It pins the same old candidate rules, market/native-source hashes and ten run
names: baseline plus exact control, existing equal votes, combined scenarios
plus exact control, and each of the five standalone scenarios.

Each run copies that declaration into its pre-sealed input protocol. The engine
must find exactly ONE contiguous group and exactly 7,247 decisions, otherwise it
aborts. One native 3,000 USDT account runs through the entire cohort per variant;
there is no mid-August account reset or inherited live position. Different
variants still have different independent accounts, never one shared portfolio.

The standard commands and comparisons work with this new workspace; never
overwrite or relabel older segmented results. Closed PnL and remaining open
positions/final marked equity are reported separately. This is still exploratory
history, not holdout validation, and no candidate is automatically deployed.

After all ten declared runs finish, consolidate and verify their manifests and
both exact-control traces with:

```bash
venv/bin/python -m platform_v2.tools.research.spot_backtest.compare /home/sandro/research_snapshots/raw_spot_backtest_20261016_gap_recovered_v1 --continuous-summary
```

This creates `comparisons/continuous_round_v1/{REPORT.md,summary.json,manifest.json}`
and a copy of the analysis source. Report directories cannot be overwritten.

## Operational ledger reconciliation (diagnosis only)

```bash
venv/bin/python -m platform_v2.tools.research.spot_backtest.reconcile_live /home/sandro/research_snapshots/raw_spot_backtest_20261016_gap_recovered_v1 /home/sandro/research_snapshots/spot_live_reconciliation_20261017_v1
```

The destination must be new. Reads the live Spot SQLite through ONE read-only
transaction, freezes selected ledger families, and joins exact candle closes to
the raw baseline. Closures after the shared cutoff are not counted at the cutoff.
Reports missing live cycles and different initial account histories explicitly.

For BUY-related common cycles, original input evidence is selected only when its
record matches the persisted signal. Blob hashes are checked; selected manifests
and final relevant orderflow chunks are preserved. The SAME pinned orderbook
formula evaluates captured vs recovered volumes; this is not a new hypothesis
or optimization. The report joins actual/model positions and permission denials.

An exact baseline/control repeat proves INTERNAL determinism, NOT equivalence to
operational history. Corrected raw orderflow can legitimately produce different
signals from old captured faulty inputs. Do not label modeled baseline profit as
the actual operational account's profit. No live tables or rules are modified.
