# Spot Rules

Updated: 2026-09-12. Active version: `spot-independent-direction-quality-v5`.

Spot is a BUY-only simulation with its own Binance Spot candles, indicators, orderbook, signal history, permissions and positions. It does not wait for Futures signals or open events. Its scoring foundation was copied from Futures and is owned locally; later Futures edits do not automatically alter Spot.

## Direction and scoring

`services/signal/independent_long_signal_service.py` computes both LONG and SHORT scores from Spot context. SHORT is opposing context, never a Spot short position. LONG is selected when its score is at least 8.5 and at least the SHORT score. SHORT context wins only when at least 8.5 and strictly greater. A BUY also needs valid positive entry/SL/TP geometry; otherwise the result is NO_SIGNAL.

| Component | Weight |
|---|---:|
| MTF | 1.0 |
| REGIME | 0.8 |
| TREND | 1.3 |
| MOMENTUM | 1.0 |
| ORDERBOOK | 0.9 |
| STRUCTURE | 0.9 |

The weighted sum is rounded to two decimals in a fixed arithmetic order. Gate pass flags describe components; none is a mandatory final veto. REGIME and the primary MTF flag are not compulsory. Capital, location, quote and other execution checks remain separate.

Spot owns copied scoring parameters in `config/long_strategy_settings.py`, operational defaults in `config/settings.py`, component logic in `services/signal/long_component_score_service.py`, structure logic in `long_structure_score_service.py`, and history-based timing in `entry_quality_service.py`.

Entry quality uses previous **Spot evaluated directions**, including opposing SHORT context, to distinguish fresh, continued, late and exhausted signals. It does not read Futures history. Entry location and account permissions can deny a scored BUY; a signal is not a filled trade.

## Position lifecycle

Defaults: 3,000 USDT starting balance, 100 USDT per entry, no leverage. The old weak-open-position blocker and peer force-close behavior are disabled (`WEAK_OPEN_POSITION_BLOCK_ENABLED=False`, `PEER_FORCE_CLOSE_ENABLED=False`). Compatibility readers and historical exit labels do not mean those rules are active.

Allowed entries use a fresh Spot ticker quote. Adaptive TP/SL is rebuilt at this price. Closed 1m bars supply exit evidence during each 15-minute cycle. LONG profit-lock policy activates at 70% of original TP distance and protects 25% from the following closed 1m bar. TP stays fixed; this is not full trailing TP/SL.

Orders and position rows live in trading SQLite under system `spot`. Spot derives current state from this history. See [SL/TP policy](sl_tp_policy.md), [permissions](risk_and_permissions.md) and [runtime flow](../system/runtime_flow.md).

Matching scoring foundations do not guarantee matching Spot/Futures results: their market data, quotes, history, available capital, permissions, fees and execution geometry differ. Compare entry lineage and net results; win rate alone does not establish profitability.
