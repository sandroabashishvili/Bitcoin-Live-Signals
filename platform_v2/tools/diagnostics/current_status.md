# Diagnostics Current Status

Updated: 2026-10-26.

Operational diagnostics now requires all three SQLite databases, runs `quick_check`, and validates stored trading rows without requiring JSON exports. Required Spot/Futures keys use the existing family registries, updated to match current cycle, order, and denied-entry writers. Hedge rows are checked for valid JSON objects, not a complete domain schema.

High-severity findings produce exit status 1. Full-profile complexity/size findings remain maintenance signals, not proof of trading corruption.

SQLite ledger checks now cover decision duplicates, order/position links, exit fields, position counts, PnL/fee/capital identities and Hedge source relationships. Overview equity payloads are checked against backend contracts and source series. Legacy JSON checks remain for exports/parity; this is not complete coverage of every historical check or every dashboard cell. The periodic runtime-health monitor remains responsible for freshness and cycle-gap checks.

Run `python3 -m platform_v2.tools.diagnostics` for current results. Reports use `platform_v2/runtime/artifacts/diagnostics/`. Old September counts and references to deleted research archives have been removed because they do not describe the current runtime.

No strategy rules, execution state, or historical records are changed by these checks.
