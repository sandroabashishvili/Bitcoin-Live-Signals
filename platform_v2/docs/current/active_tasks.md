# Current Work and Strategy Status

Updated: 2026-09-12.

## Active runtime

September 10 reset began a new simulation history. Spot runs independent direction/quality v5; Futures runs SHORT-zone-required / LONG-profit-lock / 1m-exit v5. Hedge intentionally follows Futures OPENED events and keeps its own basket/account policy. Hedge policy is out of scope for this maintenance pass.

September 12 maintenance reviews documentation, post-reset lineage, GitHub/public SEO and cleanup. Findings and validation are recorded in [system review](system_review_20260912.md). Local fixes are not evidence of remote deployment; check that report before publishing or restarting.

## Research, not deployed

- SHORT ORDERBOOK weight candidate: promising in an archived comparison, not promoted to live settings.
- RSI/MACD/ADX/rejection candidate: tested September 11, historical comparison worsened; production restored to v5. Archived evidence: `/home/sandro/research_snapshots/score_fix_20260911/RESULT.md`.
- Full trailing TP/SL for LONG and SHORT: research only. Active LONG protection is the fixed 70%/25% profit lock.
- Independent one-minute exit monitor: not implemented; current loops examine closed 1m bars once per 15-minute cycle.

## Next decisions

Accumulate stable-version simulation evidence and review actual entries/exits, net PnL, drawdown and missed opportunities. Do not treat a small trade sample, Gate win rate or one historical candidate as proof of an edge. Compare separate time periods and market conditions with fees and consistent portfolio assumptions.

Indicator path-sensitive rules and missing rejection features remain research questions. Keep candidate code/results separate and promote only after a reproducible comparison. No strategy tuning or another reset is part of this maintenance pass.

Google Search Console coverage/selected canonical and field performance still require account data. Public HTTP/canonical checks alone cannot establish actual Google indexing.
