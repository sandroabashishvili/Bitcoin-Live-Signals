# SL TP Policy

Status: `active v5 policy; reviewed 2026-09-12`  
Created: `2026-05-19`  
Author: Codex  
Purpose: Current stop-loss and take-profit policy.

## Current Understanding

The system uses adaptive TP/SL planning instead of a simple fixed percentage model.

The same adaptive service shape exists for Spot and Futures.

Signal construction uses the latest fully closed candle. When a signal is
actually allowed, the execution setup is anchored to a fresh Binance ticker
quote observed during that cycle. Both Futures and Spot rebuild the adaptive
execution setup from the same closed-candle context and the live entry price.
Futures must not mechanically shift theoretical TP/SL distances because doing
so can move the final target away from the original resistance or liquidity
zone.

## Required Inputs

SL/TP planning requires ATR. If ATR is missing or invalid, adaptive setup returns no payload and the caller must use fallback behavior where implemented.

Core inputs:

```text
side
entry
atr
swing_low
swing_high
ema50
kijun
resistance_level
liquidity_zone
liquidity_tolerance
adx
confidence
fee_buffer_pct
```

## Stop-Loss Logic

Stop-loss uses structure-aware priority:

```text
1. swing level
2. kijun
3. ema50
4. ATR fallback
```

Candidate levels are rejected if they are on the wrong side of entry or too far away in ATR terms.

Current distance limits:

```text
swing max distance = 3.5 ATR
kijun max distance = 2.6 ATR
ema50 max distance = 2.0 ATR
```

ADX modifies SL ATR multiplier:

```text
ADX < 18 -> widen SL multiplier by 10%
ADX > 28 -> tighten SL multiplier by 5%
```

A fee buffer is applied after stop selection:

```text
LONG  stop is moved lower
SHORT stop is moved higher
```

Current fee buffer in SL/TP inputs:

```text
0.0006
```

## Take-Profit Logic

TP starts from risk-derived RRR:

```text
base TP = entry +/- (risk * resolved_rrr)
```

RRR is derived from confidence, then bounded by configured min/max from the SL/TP input model.

TP can be clamped to:

```text
resistance_level
liquidity_zone
psychological level
```

Clamp is rejected if the effective R:R would become too tight.

If TP is too close to entry, it is expanded using ATR/RRR fallback logic.

## Exit Confirmation

TP/SL confirmation uses closed 1m candles for both Spot and Futures. Signal
calculation remains on 5m/15m/4h; the 1m series is execution evidence only.

Do not casually change TP/SL hit logic without checking runtime positions, orders, and candle data together.

## Exit Monitoring

Closed 1m bars are examined inside the 15-minute main cycle. There is no
independent one-minute monitoring loop. TP remains fixed; full trailing TP/SL
is not deployed for either system.

Current exit monitoring timeframe:

```text
1m
```

The first 1m candle whose open time predates the position open is excluded from
exit evaluation. Its high/low includes price action from before the position
existed and cannot be used as proof of a TP or SL hit.

Conservative same-candle rule:

```text
if TP and SL are both touched in the same candle, SL wins
```

Spot BUY:

```text
SL hit if candle low <= stop_loss
TP hit if candle high >= take_profit
```

Futures SHORT:

```text
SL hit if candle high >= stop_loss
TP hit if candle low <= take_profit
```

Spot BUY and Futures LONG v5 retain the narrow post-entry protection rule without changing the
original TP/SL geometry. After the LONG reaches 70% of its entry-to-TP path,
a stop at 25% of that path becomes active from the next closed 1m candle. The
exit is recorded as `profit_lock_hit`, not as TP or SL. Positions opened before
the policy is active keep their original fixed lifecycle.

## Fees And Exit Types

Spot currently uses symmetric entry/exit fee settings in root settings.

Futures policy:

```text
entry open  = taker
TP/SL close = maker
profit-lock close = maker
force close = taker
```

Fee policy is documented separately in `trading/fees.md`.
