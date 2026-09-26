# Replay Research

Status: `active`
Created: `2026-05-19`
Updated: `2026-08-01`
Author: Codex
Purpose: Research-only replay and what-if tools for signal, execution, and permission tuning.

This folder contains historical replay and research tools for `platform_v2`.

Research responsibilities:

- candle-by-candle replay
- signal-only research runs
- theoretical execution replay
- portfolio and outcome comparison
- current-vs-proposed strategy comparison

Output family:

- `/home/sandro/SmartSignalHub/platform_v2/runtime/artifacts/research/replay`

## Safe workflow

Do not reset live runtime before research. First create a validated SQLite-derived snapshot:

```bash
cd /home/sandro/SmartSignalHub
source venv/bin/activate
python3 -m platform_v2.tools.research snapshot
```

Snapshots are stored outside the project in:

- `/home/sandro/research_snapshots/smartsignalhub_YYYYMMDD_HHMMSS`

The default snapshot command reads canonical SQLite through persistence APIs and exports JSON for offline replay. It does not rely on legacy runtime JSON folders. Each snapshot has a `manifest.json` with the SHA-256 hash of every exported JSON file. Explicit JSON roots are a compatibility input only. The export is not a guaranteed cross-database transaction; consistency must be checked before research. Verify an existing snapshot with:

```bash
python3 -m platform_v2.tools.research verify-snapshot \
  /home/sandro/research_snapshots/smartsignalhub_YYYYMMDD_HHMMSS
```

Build a cross-system baseline from the snapshot:

```bash
python3 -m platform_v2.tools.research baseline \
  /home/sandro/research_snapshots/smartsignalhub_YYYYMMDD_HHMMSS
```

Every replay accepts an explicit snapshot data root and output root. Example:

```bash
python3 -m platform_v2.tools.research.replay.futures_entry_quality_what_if \
  --dates 2026-07-29 2026-07-30 \
  --data-root /home/sandro/research_snapshots/smartsignalhub_YYYYMMDD_HHMMSS/futures/data \
  --output-root /home/sandro/SmartSignalHub/platform_v2/runtime/artifacts/research/replay/my_test
```

The replay output must never be placed inside the snapshot. Keeping input and
output separate makes the experiment reproducible and protects live runtime.

## Futures Permission What-If Tools

SHORT market-plan zone block audit:

```bash
python3 -m platform_v2.tools.research.replay.futures_short_zone_block_what_if \
  --dates 2026-05-31 2026-06-01
```

This checks denied SHORT rows with `short_market_plan_zone_block` against their theoretical entry, TP, and SL until available data end.

## Futures conjunctive entry-quality rules

`futures_entry_quality_what_if` supports both the original independent
(OR-style) filters and explicit conjunctive (AND-style) filters. Use the
conjunctive options when a row should be blocked only when all configured
properties match.

Example: research only SHORT entries that are both a fresh flip and inside the
current short market-plan zone:

```bash
python3 -m platform_v2.tools.research.replay.futures_entry_quality_what_if \
  --dates 2026-07-01 2026-07-02 \
  --side SHORT \
  --block-timing \
  --conjunction-timing FRESH_FLIP \
  --conjunction-market-plan-alignment IN_ZONE
```

The generated report includes a chronological train/test split and seven-day
buckets. This is report-only research and does not change live permissions.

## Gate ablation audit

Use a frozen snapshot to compare executed-trade outcomes when each gate passed
versus failed, split by Spot, Futures LONG, and Futures SHORT:

```bash
python3 -m platform_v2.tools.research.replay.gate_ablation_audit \
  /home/sandro/research_snapshots/<snapshot-name>
```

The report also shows exact gate-count cohorts, score bands, combinations, and
a chronological train/test split. Results are observational: true removal of a
component requires a replay from persisted raw component scores.

## Strategy decision lineage

Signals created from `2026-07-31` onward can carry the exact scoring inputs
needed for reproducible comparisons.

Spot signal rows persist:

- `strategy_version`
- `threshold`
- `component_scores`
- `component_weights`

Futures signal rows persist:

- `strategy_version`
- `direction_scores`
- `direction_thresholds`
- `direction_component_scores`
- `direction_component_weights`

The main Futures simulation now uses `futures-short-flip-stop-cap-v2` after the
selected SHORT timing+exit replay was reviewed. Future candidate weights and
thresholds must still be evaluated separately for Spot, Futures LONG, and
Futures SHORT before any later promotion.

Reconstruct the current component logic at every historical signal timestamp
and run first-stage remove-one plus single-weight/threshold retention tests:

```bash
python3 -m platform_v2.tools.research.replay.historical_component_replay \
  /home/sandro/research_snapshots/<snapshot-name>
```

The tool aligns indicators to candle close time and orderflow to the actual
cycle execution time. Its persisted-score validation must be exact before the
report is used. This first stage only evaluates historically executed trades;
it does not assign hypothetical PnL to entries that were never opened.

Audit raw indicator bands and categorical conditions against executed outcomes:

```bash
python3 -m platform_v2.tools.research.replay.indicator_calibration_audit \
  /home/sandro/research_snapshots/<snapshot-name>
```

The report is direction-specific and includes chronological train/test
stability. It covers RSI, ADX, DI alignment, ADX slope, ATR growth, EMA distance
and slope, VWAP distance, MACD spread, swing structure, ATR spike, bounce state,
and directional orderflow. Treat stable bands as calibration candidates, then
confirm them in full candle-by-candle portfolio replay.

Research candidate weights and thresholds are versioned in:

- `candidate_profiles.py`
- `calibration_findings_v1.json`

RSI candidate profiles include both narrow reward changes and full Momentum
map alternatives. These are replay-only profiles: they do not alter the live
Futures score service. The full portfolio replay is required because changing
an RSI reward changes later cooldown, proximity, capital, and position-slot
state as well as the immediate signal.

Run independent candle-by-candle TP/SL outcomes for every candidate signal:

```bash
python3 -m platform_v2.tools.research.replay.candidate_signal_outcome_replay \
  /home/sandro/research_snapshots/<snapshot-name>
```

Use `--repair-macd-histogram` only to measure the historical effect of the
repaired three-point MACD sequence. Live scoring keeps this reward disabled
until portfolio replay and shadow validation pass.

Run the permission/state-aware portfolio replay after independent signal
screening:

```bash
python3 -m platform_v2.tools.research.replay.portfolio_state_replay \
  /home/sandro/research_snapshots/<snapshot-name>
```

This replay uses 5m exit candles and applies current capital, exposure,
position-state, cooldown, proximity, entry-quality, entry-location, and
market-plan permissions. The report compares baseline entry timestamps and
closed PnL with actual runtime positions. Always inspect this fidelity section
before interpreting candidate PnL.

Spot minus-rule force closes are modeled after normal 5m TP/SL updates and
before each new entry permission decision. The fidelity report shows actual
versus replay force-close counts alongside PnL and entry timestamp matches.

Run a direction-specific one-component weight grid with the same full
permission and portfolio state:

```bash
python3 -m platform_v2.tools.research.replay.futures_weight_grid_replay \
  /home/sandro/research_snapshots/<snapshot-name> \
  --side SHORT
```

The default grid tests `0.5x`, `0.75x`, `1.25x`, and `1.5x` for MTF, Regime,
Trend, Momentum, Orderbook, and Structure. Only one weight changes in each run;
threshold, permissions, position size, and SL/TP remain baseline. Use the grid
for screening exact candidates, not for automatic live tuning.

After a broad grid identifies a lead, keep the follow-up narrow instead of
rerunning or combining every component:

```bash
python3 -m platform_v2.tools.research.replay.futures_weight_grid_replay \
  /home/sandro/research_snapshots/<snapshot-name> \
  --side SHORT \
  --components regime \
  --multipliers 1.35 1.4 1.45 1.55 1.6 1.65
```

Run the equivalent state-aware grid for Spot BUY independently:

```bash
python3 -m platform_v2.tools.research.replay.spot_weight_grid_replay \
  /home/sandro/research_snapshots/<snapshot-name>
```

The Spot report has the same one-weight guardrail. The force-close-aware
baseline currently reproduces 60/60 closes, the exact `41.67%` win rate, and
three force closes. It uses the same canonical `score / 18.0` setup confidence
as actual Spot execution and produces `-2.40` replay net versus `-2.44` actual
net, with 58/60 exact entry timestamps.

Audit every recorded Spot/Futures exit against persisted 5m candle wicks:

```bash
python3 -m platform_v2.tools.research.replay.tp_touch_fidelity_audit \
  /home/sandro/research_snapshots/<snapshot-name>
```

The audit reports missed TP/SL touch candidates, a recorded close that happened
later than the first matching wick, same-5m-candle TP/SL ambiguity,
candle-history gaps, and positions that came within `0.1%` of TP without
actually touching it. It also lists earlier near misses before a later real TP
hit. A wick reversal is still retained in the 5m high/low; 1m data is needed
only to refine ordering inside a 5m candle, not to prove whether the 5m price
range reached a level.

Forward shadow evaluation uses a frozen candidate specification:

```text
platform_v2/tools/research/replay/shadow_candidate_set_v1.json
```

When a newer snapshot contains decisions after the frozen cutoff, evaluate
only new rows with the frozen three-arm evaluator:

```bash
python3 -m platform_v2.tools.research.replay.forward_shadow_replay \
  /home/sandro/research_snapshots/<new-snapshot-name>
```

Do not move the cutoff after seeing results. The frozen post-cutoff period is
the out-of-sample shadow check. The shadow portfolio starts flat at the cutoff;
pre-cutoff positions and reserved capital are deliberately not inherited.

SHORT entry-quality block audit:

```bash
python3 -m platform_v2.tools.research.replay.futures_entry_quality_block_what_if \
  --dates 2026-05-31 2026-06-01 \
  --side SHORT
```

This checks denied rows with `entry_quality_block` and marks which rows match the current tested override candidate.

Example:

```bash
python3 -m platform_v2.tools.research.replay.futures_entry_quality_what_if \
  --dates 2026-05-14 2026-05-15 2026-05-16 2026-05-17 2026-05-18 2026-05-19 2026-05-20 2026-05-21 2026-05-22 2026-05-23 2026-05-24 2026-05-25 \
  --block-timing \
  --block-side-location LONG:EXTENDED_INTO_RESISTANCE
```

Spot example:

```bash
python3 -m platform_v2.tools.research.replay.spot_entry_quality_what_if \
  --dates 2026-05-14 2026-05-15 2026-05-16 2026-05-17 2026-05-18 2026-05-19 2026-05-20 2026-05-21 2026-05-22 2026-05-23 2026-05-24 2026-05-25 \
  --block-location EXTENDED_INTO_RESISTANCE
```

Spot entry location plus missing-gate example:

```bash
python3 -m platform_v2.tools.research.replay.spot_entry_quality_what_if \
  --dates 2026-05-14 2026-05-15 2026-05-16 2026-05-17 2026-05-18 2026-05-19 2026-05-20 2026-05-21 2026-05-22 2026-05-23 2026-05-24 2026-05-25 \
  --block-location EXTENDED EXTENDED_INTO_RESISTANCE \
  --block-missing-gates ORDERBOOK REGIME
```

Gate-only research is supported by passing an empty `--block-location` list:

```bash
python3 -m platform_v2.tools.research.replay.spot_entry_quality_what_if \
  --dates 2026-07-01 2026-07-02 \
  --block-location \
  --block-missing-gates MTF
```

## Current-live comparison limit — 2026-09-12

Some archived replay/audit tools below explicitly use 5m evidence. Active v5 Spot/Futures use 1m exits and fresh execution quotes. Do not treat an older replay result as current portfolio parity without checking its input resolution, entry/fee assumptions and permissions. The September 11 indicator-path candidate remains archived, not deployed. See [research status](../../../docs/trading/strategy_research.md).


## Reproducible runs

Use `python3 -m platform_v2.tools.research.recorded_run --help` for the snapshot-only recorded launcher. It writes a unique run directory and `run_metadata.json` before executing an approved replay, then records completion/failure and input stability. Existing direct replay CLIs remain unchanged and do not automatically gain this metadata.

Metadata records source revision and file hashes, effective settings and candidate profiles, snapshot file hashes, observed timestamp coverage, command, Python version and UTC run times. Current settings are captured at launch: a historical candidate name does NOT freeze its original weights. Metadata identifies a run; retaining the source checkout and input snapshot is still required to reproduce it. Original historical metadata must never be fabricated retroactively. Dataset timestamp coverage is descriptive, not a guarantee of decision-time feature availability or a signal edge analysis.

The one-off `artifacts/entry_timing_20260916` bundle remains in place until its original input snapshot/revision can be established. Its existing result is historical evidence, not proof that rerunning it against today's database reproduces that result.

Example for a later, separately approved research run (not executed during Phase 1):

```bash
python3 -m platform_v2.tools.research.recorded_run portfolio_state_replay \
  /home/sandro/research_snapshots/EXISTING_VERIFIED_SNAPSHOT \
  --output-root /home/sandro/research_runs
```

Do not treat archived trade-outcome replay as the planned unbiased signal-decision dataset. The future signal edge audit requires its own dataset and label validation.
