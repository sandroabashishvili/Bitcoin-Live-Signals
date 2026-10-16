# Futures Rules

Updated: 2026-10-15. Scoring version: `futures-short-zone-required-long-profit-lock-1m-v5`.

Futures independently evaluates Binance Futures BTCUSDT context. Defaults: simulation, isolated x5, 100 USDT margin (500 USDT notional), 3,000 USDT starting balance. Current runtime confirms simulation; this document does not authorize live trading.

## Signals and gates

ORDERBOOK measures executed Futures trade flow, not passive depth. The closed-window
collector repair uses the exact decision candle and aggregate-ID pagination;
same-millisecond trades are retained and subsequent requests do not mix fromId
with time bounds. The main cycle supplies the actual candle close explicitly.
Snapshots carry window bounds, first/last trade times, page count and
`COMPLETE_CLOSED_WINDOW_V1` status. Legacy/unverified, incomplete or wrong-candle
inputs are rejected rather than used as current data. API errors propagate and
cannot become apparently valid zero-volume snapshots. Futures supports 1m/5m/15m/30m
collection windows; longer windows are rejected rather than violating the API's
less-than-one-hour bounded-query constraint. Production uses 15m.

This repair changes the input, not component formulas, weights, thresholds or
position rules. Historical rows remain unchanged; earlier replay and gate metrics
inherit the documented stale-input limitation. Deployment and acceptance evidence:
`/home/sandro/research_snapshots/futures_orderflow_fix_20261015/`.

Both LONG and SHORT use an 8.5 action threshold. LONG wins a qualifying tie; SHORT must exceed LONG. The six weighted components are MTF 1.0, REGIME 0.8, TREND 1.3, MOMENTUM 1.0, ORDERBOOK 0.9 and STRUCTURE 0.9. No individual Gate, including the primary 15m MTF flag, is a mandatory signal veto. Scoring lives in `services/signal/`; operational settings live in `config/settings.py`.

Signals and execution permissions are separate. NO_SIGNAL selected score can display zero while both directional scores are nonzero; direction scores carry the comparison. A scored SHORT with DENIED permission is not an opened position.

## Active entry policy

Capital/exposure, total and direction slots, liquidation buffer, duplicate/cooldown/proximity, quote availability and entry-quality checks remain. LONG also has entry-location checks; SHORT has market-plan-zone checks.

A SHORT outside its required market-plan zone stays blocked: `SHORT_CONTINUATION_OVERRIDE_ENABLED=False`. The old continuation override is not active. The SHORT late-extension quality override is a different rule and still exists (at least two passed gates and score at least 9). Do not confuse these overrides.

The first LONG-to-SHORT change waits for a consecutive closed 15m SHORT confirmation. LONG flips are not subject to that delay. Exhausted timing is blocked. The SHORT adaptive stop cap applies in the configured 2.5–3.5 ATR band and caps distance at 2.5 ATR, preserving TP.

## Execution and storage

Allowed positions use a fresh Futures ticker quote. Adaptive execution TP/SL is rebuilt from the same closed-candle context at the new entry price. Orders enter `futures_orders`; lifecycle rows enter `futures_position_events`. `futures_positions` is a virtual latest-event projection, not a second persisted ledger. Mutable simulation state resides in trading SQLite.

Closed 1m bars resolve exits during the 15-minute main cycle. The first partially pre-entry bar is excluded; simultaneous TP/SL touches resolve as SL. Normal exits are TP, SL, and LONG profit lock. Old minus-rule peer force-close behavior is inactive.

LONG profit lock activates after 70% of original target distance, protects 25% from the next closed 1m bar and leaves TP fixed. SHORT does not have this policy. Full moving TP/SL for both directions is research, not deployed behavior.

## Known research questions

Current SHORT RSI scoring uses the level, not its path; some MACD counter-direction states receive credit; SHORT REGIME does not discount falling ADX; rejection confirmation is read by scoring but not produced by current indicator generation. These are open design questions, not automatically proven causes of loss.

The September 11 RSI/MACD/ADX/rejection candidate was tested and restored to v5 after worse historical replay results. It is not running. See [research status](strategy_research.md), [SL/TP](sl_tp_policy.md), and [permissions](risk_and_permissions.md).
