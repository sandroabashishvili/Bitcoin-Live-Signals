# Strategy Research And Calibration

Status: `research evidence; current promotion status below`  
Created: `2026-07-31`  
Updated: `2026-08-01`  
Author: Codex  
Purpose: Current evidence, safety rules, and next steps for Spot/Futures strategy calibration.

## Current status — 2026-09-12

Active versions are Spot independent direction/quality v5 and Futures SHORT-zone-required / LONG-profit-lock / 1m-exit v5. The September 11 RSI/MACD/ADX/rejection candidate was rolled back after worse historical replay results; it is not deployed. The SHORT ORDERBOOK weight experiment is also not promoted. Full trailing exits and an independent one-minute monitor remain research/planning work.

Evidence: `/home/sandro/research_snapshots/score_fix_20260911/RESULT.md`, `/home/sandro/research_snapshots/indicator_audit_20260911/REPORT.md` and per-experiment manifests. Preserve candidate inputs and baseline parity limits. Current equations reproducing saved indicators do not independently prove market logic is effective.

The sections below describe the **July 31 / August 1 research snapshot**, not the new post-reset period or current deployment status. Use [active tasks](../current/active_tasks.md) and [current rules](futures_rules.md) for today's behavior.

## Objective

Improve signal quality, expectancy, and drawdown without guessing from a small
set of trades and without changing the live strategy before replay and shadow
validation.

The research is direction-specific:

- Spot BUY
- Futures LONG
- Futures SHORT

MTF, Regime, Trend, Momentum, Orderbook, and Structure are six scoring
components of one decision system. They are not six independent trading bots.

## Frozen Research Baseline

Current input snapshot:

```text
/home/sandro/research_snapshots/smartsignalhub_20260731_153256
```

The snapshot is hash-verified and contains approximately:

- 4,614 15m candles
- 4,580 indicator snapshots
- 4,100 orderflow rows
- 4,105 reconstructed Spot decision timestamps
- 8,210 reconstructed Futures direction rows

Actual closed-trade baseline:

| Market | Closed trades | Net PnL |
|---|---:|---:|
| Spot | 60 | -2.44 |
| Futures LONG | 60 | -6.61 |
| Futures SHORT | 97 | -25.43 |

## Confirmed Technical Finding

MACD histogram values were calculated but replaced by an empty list during
snapshot construction. Persistence is fixed and covered by a test.

The histogram signal reward remains disabled behind
`MACD_HISTOGRAM_SIGNAL_ENABLED = False`. Repairing the historical sequence and
immediately enabling its reward made replay worse, so persistence repair and
strategy promotion are deliberately separate decisions.

## Indicator Calibration Findings

The current evidence shows that some rewarded bands are associated with poor
outcomes. Examples include:

- Futures SHORT small directional MACD spread (`0-0.2 ATR`)
- Futures SHORT rewarded swing-high distance (`1.5-2.5 ATR`)
- Futures SHORT bearish DI alignment in the tested period
- Futures LONG RSI `58-65`
- Futures LONG MACD alignment
- several Spot orderflow and bounce-confirmation cohorts

These are observational findings, not sufficient reasons to delete an
indicator. Component overlap, entry permissions, timing, and TP/SL lifecycle
must be replayed together.

Versioned evidence and research-only candidates live in:

```text
platform_v2/tools/research/replay/calibration_findings_v1.json
platform_v2/tools/research/replay/candidate_profiles.py
```

### RSI entry-map replay

Futures LONG currently uses RSI in two different contexts:

- MTF entry context prefers the earlier `40-55` pullback area and penalizes
  late/extended RSI.
- Momentum gives its largest RSI reward to `58-65`.

Two isolated state-aware alternatives tested whether this overlap was the main
problem. Neither changed weights, threshold, permissions, position size, or
SL/TP:

| LONG RSI candidate | LONG net | Train net | Test net | Drawdown | Result |
|---|---:|---:|---:|---:|---|
| Baseline | -1.01 | +14.23 | -15.24 | 31.25 | reference |
| Remove RSI from Momentum; keep it in MTF | -19.18 | +8.23 | -27.41 | 30.93 | rejected |
| Replace Momentum RSI with the MTF pullback map | -16.02 | +3.84 | -19.86 | 44.02 | rejected |

This rejects the simple claim that LONG entries improve by moving the RSI
reward from `58-65` to a lower band. It does not prove the current late reward
is correctly calibrated. The stronger lead remains contextual: removing the
MACD alignment reward only when RSI is already `58+` improved LONG from
`-1.01` to `+18.59`, but its test half remained negative at `-10.41`. RSI must
therefore be researched together with confirmation/timing context, not made an
independent BUY trigger.

The contextual RSI boundary check compared `55`, `58`, `60`, and `65`. LONG
net results were `+5.92`, `+18.59`, `+1.30`, and `+3.10` respectively. Only
`58` improved both chronological halves relative to baseline, which matches
the start of the current strongest RSI reward band. The candidate is not
approved because its absolute test result remains negative.

### LONG MACD spread candidate

The executed-trade audit identified LONG directional MACD spread `0.2-0.5
ATR` as negative in both chronological halves. Removing only the MACD
alignment `+0.8` reward in that band produced:

| Metric | LONG baseline | MACD spread candidate |
|---|---:|---:|
| Trades | 63 | 59 |
| Net PnL | -1.01 | +16.34 |
| Train net | +14.23 | +21.43 |
| Test net | -15.24 | -5.09 |
| Direction drawdown | 40.38 | 33.57 |

This is the best-balanced LONG indicator candidate so far. It improves both
halves, expectancy, and drawdown, but the test half remains negative. It stays
research-only and must be checked on a separate period or forward shadow data.

## Replay Layers

### 1. Historical component retention

Checks how executed trades would be retained when one component weight or
threshold changes. It is useful for screening, but it cannot score trades that
were never opened.

### 2. Independent signal outcome replay

Builds a theoretical TP/SL outcome for every candidate signal. It revealed that
simple component weight changes alone do not solve Futures performance.

### 3. Permission/state-aware portfolio replay

Current canonical research tool:

```bash
python3 -m platform_v2.tools.research.replay.portfolio_state_replay \
  /home/sandro/research_snapshots/smartsignalhub_20260731_153256
```

It models:

- chronological entries and overlapping open positions
- 5m candle TP/SL lifecycle
- capital and exposure reservation
- position and direction slots
- cooldown and proximity
- duplicate entry checks
- Spot weak-open-position and BUY location checks
- Futures liquidation buffer and entry quality
- Futures LONG location and SHORT market-plan permission

First baseline fidelity checkpoint:

| Market | Replay opened | Actual opened | Exact entry matches | Replay closed net | Actual closed net |
|---|---:|---:|---:|---:|---:|
| Spot | 60 | 60 | 58 | -2.40 | -2.44 |
| Futures | 159 | 158 | 148 | -31.89 | -32.04 |

Futures fidelity is strong. Spot minus-rule force-close parity now brings
replay within `0.04` of actual net PnL. Spot theoretical setup, execution setup,
and replay now share the execution-time `score / 18.0` confidence conversion.
The two remaining non-matching Spot timestamps are delayed by the current
`buy_entry_location_block` when current code is replayed over entries opened
before that rule existed; they are documented strategy-version drift, not a
reason to fit historical date exceptions. Conservative same-candle SL-first
handling remains an explicit limitation.

## First Portfolio Candidate Result

- Spot orderbook-zero produced `-3.16` after force-close parity and reduced
  opened positions from 60 to 35. It was `-0.10` in the chronological train
  half and `-3.06` in the test half, so it remains rejected.
- Futures LONG MTF-half improved combined replay net from `-31.89` to `-16.16`,
  but remained negative and changed many historical LONG entries. Relative to
  baseline it improved both halves, but the train half remained negative.
- Futures SHORT momentum-zero, trend-half, and structure-half candidates were
  worse than baseline in the state-aware replay.

Narrow indicator-band replay added after the first pass:

- Futures LONG baseline replay net: `-1.01`.
- LONG MTF weight `0.5`: `+14.72`; both train and test improved relative to
  baseline, but test remained `-8.16`.
- LONG MACD alignment reward removed: `+12.32`; both halves improved relative
  to baseline, but test remained `-7.47`.
- LONG moderate MTF/MACD combination: `+11.75`, still negative in test.
- LONG RSI `58-65` reward removal/reduction worsened results.
- SHORT MACD-spread, Structure-band, DI-alignment, and combined narrow reward
  removals did not improve the SHORT portfolio result.

This is causal replay evidence that several negative executed-trade cohorts
must not simply be deleted from scoring. Portfolio path and permission state
change which later trades can open.

No candidate is approved for live promotion from these results. Later sections
record the narrowly scoped candidates approved only for forward shadow.

## Entry Timing Classification Correction

The first narrow live-code correction was completed on `2026-07-31` without
changing trade eligibility:

- `FRESH_FLIP` now requires an opposite prior actionable direction.
- first actionable direction is `FRESH_SIGNAL`.
- same-direction return after `NO_SIGNAL` is `FRESH_REENTRY`.

The corrected state-aware replay opened the exact same 159 positions with the
same `-31.89` net result and `60.86` drawdown. The old `FRESH_FLIP` cohort then
separated into materially different groups:

| Direction / timing | Trades | Net PnL |
|---|---:|---:|
| LONG true `FRESH_FLIP` | 41 | -14.34 |
| LONG `FRESH_REENTRY` | 22 | +13.33 |
| SHORT true `FRESH_FLIP` | 34 | -27.97 |
| SHORT `FRESH_REENTRY` | 45 | -1.74 |
| SHORT `EARLY_CONTINUATION` | 14 | +2.86 |

This confirms that the old timing label mixed different entry contexts and
that true flips are the next narrow logic problem to research. It does not yet
justify a hard block, position-size rule, or live score change.

## SHORT Flip Confirmation Shadow Candidate

A one-candle confirmation rule was tested with the complete chronological
permission and portfolio state. It does not resize a position and it does not
permanently block SHORT. The first LONG-to-SHORT direction change becomes
pending; the immediately next closed 15-minute candle must remain SHORT, after
which all existing permissions are evaluated again.

| Metric | Baseline | SHORT confirmation |
|---|---:|---:|
| Opened positions | 159 | 152 |
| Net PnL | -31.89 | +3.82 |
| Average net per closed position | -0.2018 | +0.0253 |
| Max sequential drawdown | 60.86 | 47.91 |
| Train net | -43.16 | -27.50 |
| Test net | +11.27 | +31.32 |
| SHORT net | -30.88 | +4.83 |

The relative result improved in both chronological halves and drawdown fell.
The LONG version was rejected because it worsened net PnL and drawdown. The
SHORT-only rule first passed forward-shadow selection under research version
`research-futures-short-flip-confirmation-v1`. It was later promoted only as
part of the combined SHORT timing+exit simulation version documented below.
This is not evidence for real-money execution.

## Retired Exploratory Candidate

The earlier combined replay candidate remains recorded in:

```text
platform_v2/tools/research/replay/shadow_candidate_set_v1.json
```

Rules:

- LONG: remove the MACD alignment `+0.8` reward only when RSI is `58` or higher.
- SHORT: keep the signal eligible, but use `25%` margin/notional when
  directional MACD spread is `0.0-0.2 ATR`.

Combined state-aware replay:

| Metric | Baseline | Shadow candidate |
|---|---:|---:|
| Net PnL | -31.89 | +36.92 |
| Average net per closed position | -0.2018 | +0.2429 |
| Max sequential drawdown | 60.86 | 40.78 |
| Train net | -43.16 | +8.24 |
| Test net | +11.27 | +28.69 |

Direction result in the combined candidate:

- LONG: `+18.59`
- SHORT: `+18.33`

The user rejected conditional position sizing as the intended solution. This
candidate is therefore retired and must not be promoted or forward-tested as
the active strategy candidate. The results remain as research evidence only.
Its sizing and MACD rules were not added to live settings.

## First Direction-Specific Weight Grid

The first full state-aware SHORT weight grid was completed on `2026-07-31`.
It changes only one of the six component weights at a time. Thresholds,
permissions, position size, and SL/TP remain on the baseline, so a weight is
not confused with a risk-management change.

The strongest stable relative improvements were:

| Component | Baseline weight | Tested weight | SHORT net | Delta | Train delta | Test delta | Portfolio net | Drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Regime | 0.8 | 1.2 | -6.77 | +24.11 | +5.31 | +18.80 | -7.78 | 52.69 |
| Orderbook | 0.9 | 0.675 | -7.92 | +22.96 | +10.23 | +12.73 | -8.92 | 49.96 |
| Structure | 0.9 | 0.675 | -12.10 | +18.78 | +3.25 | +15.53 | -18.21 | 57.38 |

All three improved the SHORT result in both chronological halves, but none
made SHORT or the total portfolio positive. They are calibration leads, not
approved strategy changes. The non-linear result also matters: Regime `1.2`
improved the replay, while Regime `1.0` worsened it. A weight must therefore be
tested as an exact candidate through the full portfolio path; it cannot be
estimated by assuming that more or less weight behaves monotonically.

The first narrow follow-up kept the two leading components separate:

| Component | Tested weight | SHORT net | Delta | Train delta | Test delta | Portfolio net | Drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|
| Regime | 1.16 | -3.36 | +27.52 | +5.17 | +22.35 | -4.37 | 52.78 |
| Orderbook | 0.6975 | +0.49 | +31.37 | +10.30 | +21.06 | -0.52 | 49.93 |

Orderbook `0.6975` is the first single-weight SHORT candidate to make the
direction slightly positive, but the complete portfolio remains slightly
negative. Further decimal fitting on the same snapshot would increase
overfitting risk. This candidate is therefore recorded for later cross-period
or forward validation, not refined indefinitely on the same data.

Canonical report:

```text
platform_v2/runtime/artifacts/research/replay/futures_weight_grid_short_20260731_202158_777472.md
platform_v2/runtime/artifacts/research/replay/futures_weight_grid_short_20260731_202910_810078.md
platform_v2/runtime/artifacts/research/replay/futures_weight_grid_short_20260731_202936_554862.md
```

RSI, MACD, ADX/DI, ATR, EMA/VWAP distance, Structure, and Orderbook entry bands
have an observational calibration audit. Their actual score changes still
require the same state-aware replay before any live change.

### Futures LONG weight grid

The same one-component grid was completed for LONG. Only two coarse candidates
improved total, train, and test relative to baseline:

| Component | Baseline | Tested | LONG net | Train delta | Test delta | Portfolio net | Drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|
| MTF | 1.0 | 0.5 | +14.72 | +8.65 | +7.08 | -16.16 | 51.91 |
| Orderbook | 0.9 | 0.45 | +12.87 | +4.07 | +9.81 | -18.01 | 76.72 |

All tested whole-Momentum weight changes worsened LONG. This supports a narrow
MACD-band correction rather than disabling or broadly rescaling Momentum.
Neither weight candidate has a positive absolute test result, and the
Orderbook candidate materially worsens total portfolio drawdown.

Canonical report:

```text
platform_v2/runtime/artifacts/research/replay/futures_weight_grid_long_20260731_211415_430161.md
```

### Spot BUY weight grid

The first full state-aware Spot grid was completed with one weight changed at a
time. The strongest stable relative candidates were:

| Component | Baseline | Tested | Replay net | Train delta | Test delta | Opened | Drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|
| Regime | 0.8 | 1.2 | -1.05 | +0.48 | +0.87 | 69 | 6.46 |
| Trend | 1.3 | 0.65 | -1.61 | +0.68 | +0.11 | 30 | 5.26 |
| Regime | 0.8 | 1.0 | -1.64 | +0.42 | +0.34 | 65 | 6.47 |

Trend `0.975` reached `+1.00`, but its test delta was `-0.95`, so it remains
time-unstable. No stable Spot weight candidate made the replay profitable.
Regime `1.2` is still the best stable relative screen, but remains negative.

Spot minus-rule force-close parity was then added. A later fidelity audit found
that signal/replay confidence used `score / 14.6` while the actual execution
path used `score / 18.0`. The canonical execution conversion is now shared by
all three paths. Replay is `-2.40` against actual `-2.44`; both contain 60
closed positions, a `41.67%` win rate, and exactly three force closes. Entry
timestamps are `58/60` exact.

The weight grid was rerun after parity:

| Component | Tested | Replay net | Train delta | Test delta | Stability |
|---|---:|---:|---:|---:|---|
| Regime | 1.2 | -1.05 | +0.48 | +0.87 | stable relative, still negative |
| Trend | 0.65 | -1.61 | +0.68 | +0.11 | stable relative, still negative |
| Regime | 1.0 | -1.64 | +0.42 | +0.34 | stable relative, still negative |
| Orderbook | 0.675 | -1.75 | +0.75 | -0.10 | rejected as time-unstable |
| Trend | 0.975 | +1.00 | +4.35 | -0.95 | rejected as time-unstable |

No Spot candidate is approved for shadow or live use. Trend `0.975` is the
clearest example of why positive full-period PnL is insufficient when the test
half worsens.

Canonical report:

```text
platform_v2/runtime/artifacts/research/replay/spot_weight_grid_20260731_215740_225257.md
```

## Exit Geometry And Joint Replay

The replay now records stop distance, target distance, and effective reward to
risk in ATR units for every modeled Futures entry. These fields are measured
from the adaptive SL/TP output; the live SL/TP service was not changed.

Baseline outcome cohorts suggested that SHORT stops in the `2.5-3.5 ATR` band
were weak, but that association was not treated as proof. Three explicit exit
policies were therefore run through the full permission/state-aware replay:

| SHORT exit candidate | SHORT net | Train | Test | Portfolio drawdown | Result |
|---|---:|---:|---:|---:|---|
| Baseline | -30.88 | -57.39 | +26.51 | 60.86 | reference |
| Cap `2.5-3.5 ATR` stops at `2.5 ATR` | -20.43 | -50.38 | +29.96 | 56.76 | relative gain in both halves |
| Widen `2.5-3.5 ATR` stops to `3.5 ATR` | -53.71 | -79.88 | +26.17 | 83.35 | rejected |
| Move `2.0-2.2 R` targets to `1.8 R` | -20.50 | -66.64 | +46.14 | 70.11 | rejected as time-unstable |

The 2.5 ATR cap changed 43 modeled exits and improved six of seven rolling
seven-day SHORT buckets relative to baseline. It remains a narrow candidate,
not a general fixed-stop replacement.

The strongest SHORT timing and exit candidates were then combined:

| Metric | Baseline | Flip confirmation | Flip + stop cap |
|---|---:|---:|---:|
| Portfolio net | -31.89 | +3.82 | +13.33 |
| Portfolio train | -43.16 | -27.50 | -20.78 |
| Portfolio test | +11.27 | +31.32 | +34.11 |
| SHORT net | -30.88 | +4.83 | +14.34 |
| Drawdown | 60.86 | 47.91 | 45.08 |

The two rules are complementary in this snapshot. The old half remains
negative, so this is approved only for forward shadow. Combining it with the
narrow LONG MACD-spread candidate produced `+23.10` total, `-21.16` train,
`+44.27` test, and `45.84` drawdown. That joint result is reference evidence;
separate forward arms are required to preserve attribution.

Canonical report and frozen candidate set:

```text
platform_v2/runtime/artifacts/research/replay/portfolio_state_replay_20260731_224517_357243.md
platform_v2/tools/research/replay/shadow_candidate_set_v2.json
```

The first technical forward-shadow checkpoint used verified snapshot
`smartsignalhub_20260731_221656`. Only one actual post-cutoff SHORT had closed,
so the sample is explicitly insufficient for strategy judgment. It did verify
the frozen evaluator and exposed a sparse-period report bug when no LONG side
existed; the report writer now supports zero-trade directions. The dedicated
command is:

```bash
python3 -m platform_v2.tools.research.replay.forward_shadow_replay \
  /home/sandro/research_snapshots/<new-snapshot-name>
```

The forward shadow is an independent flat virtual portfolio starting at the
fixed cutoff. This avoids contaminating later evaluation with fitted pre-cutoff
candidate state, but it does not inherit positions or capital reserved before
the cutoff. That limitation is printed in every post-cutoff report.

## Main Simulation Promotion

On `2026-08-01`, after owner review, the `short_timing_plus_exit` arm was
promoted to the market-fed Futures simulation as:

```text
futures-short-flip-stop-cap-v2
```

The promoted change contains exactly two SHORT rules:

1. confirm a true LONG-to-SHORT flip on the immediately next closed 15-minute candle;
2. cap only adaptive SHORT stops in the `2.5-3.5 ATR` band at `2.5 ATR`, keeping TP unchanged.

Spot, Futures LONG scoring, all component weights, thresholds, position size,
and TP policy remain unchanged. The stop cap is applied inside the Futures
SL/TP service, so permission/liquidation checks and the opened position receive
the same adjusted stop. Frozen replay explicitly disables the promoted default
and applies candidate policies separately, preserving the old baseline.

Post-integration replay reproduced the selected results exactly: baseline
`-31.89`, candidate `+13.33`, train `-20.78`, test `+34.11`, and drawdown
`45.08`. Promotion record:

```text
platform_v2/tools/research/replay/futures_strategy_promotion_v2.json
```

## Promotion Rule

A live strategy change requires all of the following:

1. clear reason tied to a versioned finding
2. train/test stability, not only full-period improvement
3. acceptable baseline replay fidelity
4. better expectancy and drawdown, not only fewer trades
5. direction-specific candidate definition
6. shadow-mode validation before any real-money consideration
7. explicit strategy version update after owner review

## Next Work

1. verify the first true SHORT flip confirmation and first in-band capped-stop event in runtime
2. keep the frozen baseline and forward arms as comparison evidence
3. evaluate the LONG MACD-spread arm only on a later forward period before any promotion
4. keep SHORT Orderbook `0.6975` and Spot Regime `1.2` as research leads, not live changes
5. retain the two remaining Spot timestamp differences as documented strategy-version drift

The active simulation changed only SHORT timing and the narrow stop cap. Live
weights, threshold, position size, Spot behavior, and LONG scoring remain unchanged.

## LONG Profit Protection Promotion

The fixed-entry audit showed that some LONG trades moved close to TP and later
closed at the original SL. A conservative candidate was therefore tested:

```text
activate after 70% of the original TP path
protect 25% of the original TP path
activation is effective from the next closed 5m candle
same-candle ordering remains stop-first
```

With the already promoted SHORT policy held constant, the full permission/state-aware
replay changed total net from `+13.33` to `+17.53`. LONG net changed from
`-1.01` to `+3.19`; LONG train/test deltas were `+0.92` and `+3.28`, and LONG
test drawdown improved from `32.20` to `24.25`. The candidate produced 15
explicit profit-lock exits. It is promoted only to simulation as
`futures-short-flip-stop-cap-long-profit-lock-v3`.

Evidence:

```text
platform_v2/runtime/artifacts/research/replay/portfolio_state_replay_20260801_102615_722579.md
platform_v2/tools/research/replay/futures_strategy_promotion_v3.json
```

### Rejected structure-room blocker

After profit-lock promotion, a separate state-aware test rejected LONG entries
when the nearest upper swing/resistance/liquidity level was closer than `0.3`,
`0.5`, or `1.0 ATR`. All three variants damaged the portfolio:

| Minimum room | Total net | LONG net | Train | Test |
|---:|---:|---:|---:|---:|
| no extra block (v3) | +17.53 | +3.19 | -19.87 | +37.39 |
| 0.3 ATR | -22.77 | -37.11 | -54.05 | +31.28 |
| 0.5 ATR | -38.53 | -52.87 | -66.32 | +27.79 |
| 1.0 ATR | -31.03 | -45.37 | -67.17 | +36.14 |

Therefore proximity to a structure level is not a valid standalone hard
blocker. The reusable structure-room feature remains available for later
conditional TP/source-quality research, but the rejected policy code was
removed after recording the evidence.

```text
platform_v2/runtime/artifacts/research/replay/portfolio_state_replay_20260801_104512_638458.md
```

## TP Wick Fidelity Audit

The complete frozen history was checked for the concern that a fast wick could
touch TP and reverse before the next runtime cycle. The audit compared the
actual execution TP/SL of 60 Spot and 158 Futures positions with every
persisted closed 5m candle after entry and before recorded close.

Results:

- 218 positions checked
- zero missed TP-touch candidates
- zero TP or SL exits recorded later than their first matching wick
- zero same-5m-candle TP/SL ambiguities
- zero gaps in either Spot or Futures 5m candle history
- four positions came within `0.1%` of TP without touching it

The closest was Futures SHORT `FUT-000035`: TP `59208.69`, lowest Futures
price `59210.40`, a difference of `1.71 USDT` (`0.002888%`). Binance Futures
1m source data confirmed the same low. Therefore a rapid reversal is not lost
by 5m OHLC aggregation: the wick remains in `high`/`low`. Remaining visual
disagreement can come from rounding or comparing Futures last price with a
different Spot, mark-price, index, or chart feed.

The strongest stored match for the reported pattern "first rise, retrace near
entry, then a later TP" is Spot `SPOT-000050`. Its fixed TP was
`64675.41454057`. The first rise on 2026-07-26 reached `64662.99`, missing TP
by `12.42454057 USDT` (`0.019211%`), then retraced to `64414.00` near the
`64388.38` entry, and finally crossed TP on the 14:05-14:09 UTC candle. Binance
Spot 1m klines independently confirm that the earlier 12:05-12:09 UTC wick
peaked at exactly `64662.99`. This is a near miss that is difficult to
distinguish visually at the dashboard chart scale, not a delayed TP record.

Regression tests now also prove that both the current Spot and Futures runtime
close a position on the first candle whose wick crosses TP even when that
candle closes back below TP.

Canonical report:

```text
platform_v2/runtime/artifacts/research/replay/tp_touch_fidelity_audit_20260801_091636_510296.md
```

## Position Management Grid And 1m Promotion

Entry scoring, thresholds, permissions, sizing, and TP/SL construction were
frozen. The complete state-aware Futures replay compared the active v3 policy
with one break-even candidate, two stepped LONG locks, and three SHORT locks.

| Position management | Total net | Train | Test |
|---|---:|---:|---:|
| active LONG 70/25, no SHORT trail | +17.53 | -19.87 | +37.39 |
| LONG break-even at 60% | +6.92 | -30.39 | +37.31 |
| LONG steps 50/0 and 75/35 | +4.74 | -37.13 | +41.87 |
| LONG steps 50/0, 70/25, 85/50 | +2.34 | -37.43 | +39.77 |
| best tested SHORT lock combination (1m) | -15.94 | -24.85 | +8.91 |

The current LONG 70/25 protection therefore remains the selected policy.
General stepped trailing is rejected, and SHORT receives no moving stop. The
The grid was run first on stored 5m history and then on the complete matching
Binance Futures 1m range. The selected 70/25 result remained exactly `+17.53`
on 1m data, while SHORT trailing deteriorated further. Runtime execution now
uses closed 1m candles to reduce intrabar ambiguity without changing
5m/15m/4h signal logic.

The promoted simulation version is
`futures-short-flip-stop-cap-long-profit-lock-1m-v4`.

Evidence:

```text
platform_v2/runtime/artifacts/research/replay/position_management_grid_20260801_195400_808818.json
platform_v2/runtime/artifacts/research/replay/position_management_grid_20260801_200513_863236.json
platform_v2/tools/research/replay/futures_strategy_promotion_v4.json
```
