# Fees

Status: `active baseline`  
Created: `2026-05-19`  
Author: Codex  
Purpose: Current fee policy used by simulation and metrics.

## Futures Current Policy

Based on the latest agreed simulation model:

```text
open position = taker
TP close      = maker
SL close      = maker
profit lock   = maker
force close   = taker
```

For Futures regular user fee assumptions:

```text
taker = 0.0500%
maker = 0.0200%
```

Example for $500 notional:

```text
entry taker fee = $0.25
TP/SL/profit-lock maker fee = $0.10
round trip TP/SL fees = $0.35
force close round trip fees = $0.50
```

This matches the current assumption that normal planned exits use maker-style fees, while entry and forced market exit use taker-style fees.

## To Verify

- Spot fee policy and whether it should stay symmetric or move to maker/taker
- fee fields in runtime positions/orders/events
- frontend metric names
- Telegram formatting
