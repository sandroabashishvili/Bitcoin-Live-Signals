# Full Spot replay (research only)

## ORDERBOOK input-quality finding (2026-10-14)

`orderflow_input_audit WORKSPACE` verifies immutable first-attempt snapshots
against raw aggTrades acquisition responses. REQUEST/RESPONSE links use ledger
event_key strings, not numeric row ids. Source windows, actual first/last trade
times and consumed volumes are checked; there are no new API calls/live writes.

In workspace `spot_signal_lab_20261012`, all 1,395 orderflow inputs match capped
1,000-trade responses with latest trades more than 23 hours old; none covers
the latest closed 15-minute candle. A single current read-only observation
confirms the same issue. The collector requests the preceding 24h once, without
pagination, and stamps the resulting old sample at the current boundary.
Dominance and imbalance are identical in all input rows; ratio is a transform
of the same two quantities, not independent confirmation.

ORDERBOOK score ablations are deferred until collection is repaired and fresh,
complete data is available. Prior replay numbers remain reproductions of the
old pipeline but include this input-quality limitation. They are not erased or
promoted. Preserve archived evidence; do not silently substitute later-fetched
data as original historical decision inputs. Any live collector correction
requires a separate authorized pinned-release operation. Full evidence is under
`/home/sandro/research_snapshots/spot_signal_lab_20261012/orderflow_input_audit/`.

The authorized collector repair was activated on 2026-10-14 in pinned release
`41a68287bc792dd9a77189f039fd5829545a90a48896f40e5a1ecebf65599778`.
New Spot input covers the exact closed 15-minute candle with aggregate-ID
pagination and explicit completeness metadata. Legacy/unverified and wrong-window
input cannot silently enter current context. Old frozen workspaces remain unchanged;
the repair cannot manufacture trustworthy historical orderflow coverage. Collect
new verified inputs before drawing ORDERBOOK score-ablation conclusions. Deployment
and first-cycle acceptance evidence: `/home/sandro/research_snapshots/orderflow_fix_20261014/`.

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

The MTF candidate changes only Spot MTF: 5m RSI/VWAP agreement with shared ADX>20; 15m RSI/EMA50
slope agreement; 4h two of RSI/Tenkan-Kijun/EMA50-200 agreement. BUY and bearish
SELL context are mirrored. Spot never opens a Futures-style SHORT position.
Undeclared long component scores changing on the same cohort abort the experiment.
Global weights, master thresholds, entry permission and position-management rules remain
the pinned Spot version. This version does not support changing indicator formulas.

### TREND directional-weight ablation

`trend_symmetry_experiment` predeclares two research candidates. `trend_mirror_v1`
changes only the four bearish TREND point awards from 1/1/1/1 to
0.7/0.8/0.8/0.8, matching the unchanged bullish formula. The predicates stay intact:
price relative to EMA50, EMA50/EMA200 alignment with price, EMA50 slope, and
DI direction when ADX >= 20. Both directional maxima become 3.1 (previously
LONG 3.1 versus SHORT 4.0). The reported TREND gate stays 2.0 and global
weight 1.3. In the pinned Spot classifier, reported gates use LONG component
scores, so this ablation does not alter that gate. It alters the opposing weighted
direction score, which competes with LONG for the final BUY decision.

`mtf_trend_mirror_v1` combines this exact ablation with the already recorded
`symmetric_all` MTF candidate. Comparing it against MTF alone isolates TREND's
incremental effect; comparing TREND alone against production isolates its effect
without MTF. AST tests require every source node except the four bearish score
constants to remain identical. Each overlay is declared and hash-checked by the
driver and worker. Neither candidate changes live source or runtime.

```bash
venv/bin/python -m platform_v2.tools.research.trend_symmetry_experiment WORKSPACE
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE --model next-minute --name trend_mirror_v1
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE --model next-minute --name mtf_trend_mirror_v1
venv/bin/python -m platform_v2.tools.research.spot_lab compare-trend WORKSPACE
```

These are exploratory tests on the same previously used frozen period, not
independent validation and not evidence that TREND is the sole source of weak signals.

### TREND predicate ablations

`trend_rules_experiment` fixes two hypotheses before launching full replays:

- `alignment`: EMA50/EMA200 alignment earns its original points without also
  requiring price to be on the aligned side of EMA50. Price relative to EMA50
  still earns its separate original points. This separates two predicates;
  it does not establish statistical independence of their information.
- `dmi`: DI direction earns its original points without ADX availability or
  ADX >= 20. REGIME's strength evaluation is unchanged. This tests a repeated
  strength requirement; removing it may also admit weak/noisy signals.

Each is evaluated with pinned MTF and with the `symmetric_all` MTF research
overlay: `trend_alignment_v1`, `mtf_trend_alignment_v1`, `trend_dmi_v1`,
`mtf_trend_dmi_v1`. Original LONG/SHORT point asymmetry is retained deliberately
to isolate predicates rather than combine them with the previous weight test.
Weights, thresholds, other component predicates, all permission filters
(including proximity), fees and position management remain pinned. AST tests
require all other source nodes to be unchanged. These four runs do not test the
two TREND predicate changes together, nor combine them with proximity removal.

```bash
venv/bin/python -m platform_v2.tools.research.trend_rules_experiment WORKSPACE
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE --model next-minute --name trend_alignment_v1
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE --model next-minute --name mtf_trend_alignment_v1
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE --model next-minute --name trend_dmi_v1
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE --model next-minute --name mtf_trend_dmi_v1
venv/bin/python -m platform_v2.tools.research.spot_lab compare-trend-rules WORKSPACE
```

Signal quality and position outcomes are reported separately. Four variants on
the same reused period are exploratory comparisons, not a proof of profitability
or an independent validation set. There is no automatic production promotion.

### REGIME rules study

`regime_rules_experiment` declares two LONG REGIME variants before replay:

- `monotonic`: the original ADX base schedule awards 1.6 in [20,25), then
  0.7 in [25,30), then 1.1 above 30. This ablation changes only the last two
  awards to the existing 1.6. DI, ADX slope, ATR-growth adjustments, spike
  penalty and score clipping remain original. Increasing ADX need not mean a
  better entry, so removal of this apparent dip is a hypothesis, not a fix.
- `strength`: LONG uses the existing opposing direction-neutral REGIME helper.
  Missing ADX or ATR spike returns zero; ADX>=20 returns 2, >=18 returns 1,
  otherwise 0.5. This replaces the whole LONG model, removing DI/slope/ATR-growth
  shaping and replacing its spike penalty with hard zero. Do not attribute any
  resulting effect to one removed term. Opposing REGIME is unchanged.

Each runs with original MTF and the `symmetric_all` MTF overlay:
`regime_monotonic_v1`, `mtf_regime_monotonic_v1`, `regime_strength_v1`,
`mtf_regime_strength_v1`. TREND retains original rules and point awards;
proximity and every other entry filter remain enabled. Global weights,
thresholds, fees, size, stops/targets and position management do not change.
The worker permits only declared REGIME/MTF score changes. Comparisons also
require other five long component scores and opposing total score to match
each respective reference. These tests are not combined with earlier TREND
or proximity-off hypotheses and do not authorize production promotion.

```bash
venv/bin/python -m platform_v2.tools.research.regime_rules_experiment WORKSPACE
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE --model next-minute --name regime_monotonic_v1
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE --model next-minute --name mtf_regime_monotonic_v1
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE --model next-minute --name regime_strength_v1
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE --model next-minute --name mtf_regime_strength_v1
venv/bin/python -m platform_v2.tools.research.spot_lab compare-regime WORKSPACE
```

Four variants on previously reused data are exploratory. Forward price labels
are gross returns, not trade PnL or independent trials. Added and removed BUY
quality is retained alongside full portfolio results and cycle drawdown.

### MOMENTUM RSI/MACD study

In pinned Spot, LONG RSI contributes 0.5 in [50,52), 1 in [52,58),
1.4 in [58,65), 0.8 in [65,72), otherwise zero. MACD>=signal adds 0.8.
Histogram-sequence points are disabled, so a raw MOMENTUM gate at 2 can pass
only in the [58,65) RSI band with MACD>=signal. This is a selective gate flag,
not a mandatory master BUY veto. The opposing MOMENTUM uses different rules.

`momentum_rules_experiment` fixes two independent LONG rule candidates:

- `rsi_direction`: +1.4 (the original peak RSI award) whenever RSI>50;
  RSI=50 abstains and RSI>=72 is no longer suppressed. MACD stays original.
  This deliberately tests removal of the upper ceiling and band shaping, not
  a claim that high RSI guarantees a good entry.
- `macd_positive`: retain original RSI and add MACD>0 to the existing
  MACD>=signal award condition. Missing MACD/signal still gets no MACD points;
  positive equality with the signal still qualifies, as in the original rule.
  It may reject useful below-zero recoveries as well as weak rallies.

Both run with original and symmetric research MTF, producing
`momentum_rsi_direction_v1`, `mtf_momentum_rsi_direction_v1`,
`momentum_macd_positive_v1`, `mtf_momentum_macd_positive_v1`. Histogram remains
disabled; maximum actual LONG points remain 2.2. Opposing MOMENTUM, other five
components (including original TREND/REGIME), weights, thresholds and all entry
filters/position-management rules remain original. None combines with prior
TREND/REGIME/proximity-off hypotheses. AST tests require exact rule isolation.

```bash
venv/bin/python -m platform_v2.tools.research.momentum_rules_experiment WORKSPACE
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE --model next-minute --name momentum_rsi_direction_v1
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE --model next-minute --name mtf_momentum_rsi_direction_v1
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE --model next-minute --name momentum_macd_positive_v1
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE --model next-minute --name mtf_momentum_macd_positive_v1
venv/bin/python -m platform_v2.tools.research.spot_lab compare-momentum WORKSPACE
```

The four variants are declared before replay but use an already reused period,
not independent validation. Whole-cohort and added/removed BUY quality are gross
price-return diagnostics, separate from full portfolio PnL and cycle drawdown.
No automatic promotion or live edits occur.

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

### Descriptive BUY permission audit

`venv/bin/python -m platform_v2.tools.research.spot_permission_audit WORKSPACE`
audits verified production-baseline and MTF-candidate BUY cycles against exact
15/60/240 minute future open prices. Both the primary denial reason and every
failed check are retained. Overlapping checks and sole-failure cases are reported
separately; missing endpoints and labels outside the frozen period are counted,
never interpolated. The unchanged control and matching cohorts are required.
The output goes to a new `spot_permission_audit/` directory with input/output
hashes. No portfolio trajectory, signal rule or filter is changed.

Gross forward returns in these groups are descriptive, not the profitability of
removing a filter. Signal times and account state differ; consecutive signals
overlap. Disabling a filter requires a full new replay because later cash,
positions, cooldown and proximity depend on the resulting new entries.

### Proximity-only full replay

`spot_filter_experiment` creates `proximity_off_v1` (pinned Spot signals) and
`mtf_proximity_off_v1` (recorded MTF candidate signals). Both replace only the
body of PermissionDecisionService._passes_proximity with True. AST tests require
all other source nodes to match. Capital, exposure, position slots, cooldown,
duplicate checks, entry location, entry quality, execution quotes, size, fees
and native exit/position management stay intact. Candidates are chosen after
the descriptive audit: these are exploratory, not a pre-registered holdout test.
Long signal components on the same cohort must stay unchanged apart from the
explicitly declared MTF overlay. No live source is changed.

```bash
venv/bin/python -m platform_v2.tools.research.spot_filter_experiment WORKSPACE
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE --model next-minute --name proximity_off_v1
venv/bin/python -m platform_v2.tools.research.spot_lab run WORKSPACE --model next-minute --name mtf_proximity_off_v1
venv/bin/python -m platform_v2.tools.research.spot_lab compare-filters WORKSPACE
```

This does NOT implement all-filters-off, remove Spot's opposing score, or turn
the six gate flags into independent 4-of-6 directional strategy votes.

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
