# Frontend Backend Boundary

Status: `active principle`  
Created: `2026-05-19`  
Author: Codex  
Purpose: Define the boundary between backend metrics/content and frontend rendering.

## Rule

Frontend must display prepared data.

Frontend must not calculate:

- trading decisions
- gate effectiveness
- PnL
- fees
- capital
- ROE
- win rate
- TP/SL outcomes
- risk/permission state

If a metric is needed on a page, backend/content services must prepare it first.

## Why

This avoids hidden mismatches between:

- terminal output
- runtime JSON
- Telegram messages
- frontend pages
- analytics reports

## Allowed Frontend Work

Frontend may do presentation-only behavior:

- pagination
- expand/collapse rows
- filtering displayed rows
- formatting already-prepared values
- highlighting positive/negative values

## Not Allowed

Frontend page builders and JavaScript should not silently rebuild missing business data. If a required runtime report is missing, the correct fix is to make the backend writer create it during the cycle.

This rule applies to Spot, Futures, Telegram, and public pages.
