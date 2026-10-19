# Exploratory equal-vote/scenario comparison, 2026-10-16

Evidence workspace: `/home/sandro/runtime_archives/trading_epoch_2026-10-18_v1/retired_metadata/research_snapshots_2026-10-18/raw_spot_backtest_20261016`.
Verified comparison: `comparisons/votes_scenarios_v1/{REPORT.md,summary.json,manifest.json}`.
Run inputs/rules were sealed before execution. Production was not changed.

All variants share 7,244 eligible BTCUSDT Spot closed-15m decisions, August 1
through October 15 UTC, split into two independent fresh-account segments at a
missing-minute boundary. Each account starts at native 3,000 USDT. Current
5m/15m/4h inputs are unchanged. The refactored control reproduces the baseline's
entire results JSON and every cycle record exactly. Regression: 432 tests passed.

| Variant | BUY candles | BUY episodes | Positions | Closed | Open at boundaries | Closed net USDT* |
|---|---:|---:|---:|---:|---:|---:|
| Current pinned baseline | 506 | 352 | 117 | 117 | 0 | +3.9037 |
| Existing LONG gate booleans, equal 4/6, no SHORT veto | 89 | 76 | 38 | 38 | 0 | +0.7819 |
| Five scenarios, new scenario-aware votes, equal 4/6 | 1,665 | 920 | 168 | 165 | 3 | +4.7347 |

*Native fees included; sum across separate accounts, not one continuous return.
Additional slippage is zero; these are modeled fills, not actual exchange trades.
Open positions are marked in account equity, not included in closed net.

Segment 1: baseline +5.0893, existing-votes +1.3250, scenarios +12.5390 closed
net USDT. Scenarios leave one open position and final equity 3,012.31.

Segment 2: baseline -1.1856, existing-votes -0.5431, scenarios -7.8043 closed
net USDT. Scenarios leave two open positions and final equity 2,993.33.

## What this establishes, and what it does not

- Equal votes on the OLD gate booleans reduce signal frequency sharply; the
  original weighted total could pass without four gate booleans being true.
  This candidate also removes opposing-score veto: not a weights-only ablation.
- New scenario rules increase signals/positions but worsen the second segment.
  Aggregate closed profit does not establish a robust improvement.
- Combined-run labels assign 146 positions to pullback, 14 to failed break,
  six to reversal, two to range bounce and zero to breakout. These are priority
  labels, NOT independent causal attribution or standalone scenario performance.
- There are 238 qualifying breakout detections, but most overlap an earlier
  priority scenario. Only six raw decisions retain the breakout label, and none
  becomes a position. Do NOT conclude that the breakout detector never fires.
- On candidate BUY candles, proximity fails 999 checks, entry location 792,
  cooldown 353 and entry quality 12. These checks overlap: their sum is NOT the
  number of denied positions. Their removal has NOT been tested or deployed.
- Native weighted confidence is retained for adaptive geometry/downstream native
  consumers, while signal votes have equal weights. This is not a claim that
  all old weighted-score dependencies have been eliminated.
- STRUCTURE repeats the mandatory scenario detector. Four votes do not mean
  four independent confirmations; several inputs remain correlated.
- There is no untouched holdout in this comparison. Next experiment should
  isolate each scenario on its own account with the same frozen definitions,
  examine overlap and rejected entries, then separately compare timeframes.
  Do not tune thresholds repeatedly against the same history and call it validation.

All settings here remain research-only. No candidate is promoted.
