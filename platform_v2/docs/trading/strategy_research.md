# Strategy research

Updated: 2026-10-20.

## Supported system

There is one supported research path: `platform_v2/tools/research/spot_backtest/`.
The short `python -m platform_v2.tools.research` command delegates to that same
engine. See [the research guide](../../tools/research/README.md) and
[backtest instructions](../../tools/research/spot_backtest/README.md).

The old replay engines, recorded-run CLI, signal/Futures portfolio/Spot labs,
standalone gate experiments and their profiles/results/tests were retired.
Old dated promotion records are not instructions to deploy anything. No old
candidate is automatically selected or promoted by cleanup.

## Preserved data

The historical Spot market database remains at
`/home/sandro/research_snapshots/raw_spot_backtest_20261016_gap_recovered_v1/market.sqlite3`.
Its official recovery and input provenance remain beside it. Old run accounts,
code captures and comparisons were deleted: this is a dataset, not a complete
runnable historical experiment or current proof of profitability.

Current live trading databases are preserved. Backups are under
`/home/sandro/backups/`; the separate October 18 runtime archive was subsequently
deleted at the user's request, not proved redundant with a byte-identical backup.
Live trading directly imports the normal Spot/Futures/Hedge source, not research
workspaces. Research workers must never write to live databases or change the
strategy automatically.

## Validation workflow

1. Prepare a new isolated experiment from explicit, verified inputs and current
   rules. Never overwrite old output or use the live runtime as output.
2. Run the current-rule baseline and unchanged control; require identical cohort,
   accounts, decisions and results before interpreting a changed candidate.
3. Change one declared hypothesis at a time; rerun the whole decision/permission/
   execution/account path. Do not reuse trades selected by another variant.
4. Report input gaps, exclusions, BUY decisions, positions, fees, closed PnL and
   remaining open equity separately. Synthetic OHLC fills are not exchange fills.
5. Use genuinely independent history and execution-cost sensitivity before
   interpreting an exploratory gain as a deployable improvement.

Retained candidate/scenario and reconciliation modules are optional modes of the
same engine, not approved production strategies. Recorded-history comparisons
are retrospective diagnostics and cannot establish causal/tradable execution.

## Scope limits

The remaining engine is Spot-specific. No current full Futures/Hedge historical
backtest is claimed after removal of the older portfolio labs. Existing native
Futures/Hedge operation is unaffected. Building new research capability requires
an explicit task, not retaining every old simulator indefinitely.

Regression tests validate implementation contracts; they are not profitability
results. The cleanup acceptance used a two-decision historical smoke replay and
an identical unchanged control, not a new full-period strategy evaluation.
