# Futures signal laboratory

This is a signal-only historical replay, not a portfolio/TP-SL backtest.
It reuses `tools/research` and leaves existing tools intact. No deployment,
live database modification, position opening or strategy restart is performed.

## Frozen inputs and baseline

`signal-lab-create WORKSPACE --trading-db ARCHIVE --market-db MARKET_DB
--release PINNED_RELEASE --start-ms START --end-ms END` creates separate SQLite
databases via online backup (including WAL), checks integrity and records hashes.
The executable Python source and pinned loader are retained. Creation refuses
an existing destination. All times are UTC epoch milliseconds, end exclusive.
Cross-database atomicity is not claimed: decisions use their own immutable
captured input revisions, not the later label database. End restricts labels too.

`signal-lab-run WORKSPACE` rebuilds indicators, MTF context, all six component
scores and the master signal from captured market revisions. It uses first
ON_TIME, evidence-complete Futures decisions. Each decoded evidence blob is
hash-checked. Available inputs are bounded by original decision time, not by
theoretical candle time. Selected direction, directional scores, gates and MTF
context must match historical records exactly. Any baseline mismatch prevents
candidate testing. `--limit N` is a smoke test only, not full validation.

The worker loads pinned source in a new process, relocates derived runtime
paths, denies network/process spawning, allows only read-only frozen SQLite,
and limits writes to its experiment directory. These are accidental-side-effect
guards, not a security sandbox for hostile Python code. Do not run untrusted code.

## One-component candidate

`signal-lab-candidate WORKSPACE mtf_trial_01` creates editable `scores.py` and
`mtf.py` under the candidate directory. Edit only the intended component's logic;
production files and baseline source remain unchanged.

`signal-lab-run WORKSPACE --name mtf_trial_01 --component mtf` uses the same
cohort. The declared component may change; any other component score changing
on that cohort aborts the run. This observational check is not a proof that the
candidate cannot affect unrelated components on unseen inputs. Weights and
master thresholds remain frozen. Every run is a new directory; reruns need a
new candidate name or a new workspace. Result, worker and protocol hashes are
checked before comparison.

`signal-lab-compare WORKSPACE mtf_trial_01` reports changed actions, signal
counts and direction-adjusted forward returns at 15/60/240 minutes. Price entry
is strictly the next one-minute open after original decision availability and
quote availability. Exact endpoint open is required; missing labels are counted,
not interpolated. Baseline/candidate use identical eligible label times, but
their selected signal subsets can differ; this is not a paired causal estimate.

## Interpretation and limits

The unchanged candidate must reproduce the baseline and have zero changed
actions. This tests plumbing, not signal quality. Mean/median/positive percentage
are price-direction metrics, not realized win rate or profitability. No fees,
capital, margin, stops, take profits or position management are modeled.

The initial workspace uses captured decisions from September 28–October 10,
2026. Earlier records are retained, but cannot automatically be treated as
point-in-time decisions under current logic. The sealed September 23–25 holdout
is not evaluated. The reused research period is exploratory, with overlapping
returns and no independent holdout; candidate promotion requires a separately
defined validation period and explicit approval. No automatic optimization or
production promotion exists.
