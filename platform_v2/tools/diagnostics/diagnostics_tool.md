# Diagnostics

Status: `active`
Created: `2026-05-19`
Updated: `2026-10-26`
Author: Codex
Purpose: Operational and full-profile diagnostics for SmartSignalHub code/runtime/frontend checks.

ეს ფოლდერი არის `platform_v2`-ის შიდა code diagnostics სისტემა.
ამ ეტაპზე სკანი ფარავს Spot, Futures და Futures Hedge runtime რეალობას.

მთავარი გაშვების ბრძანება:

```bash
cd ~/SmartSignalHub
source venv/bin/activate
python3 -m platform_v2.tools.diagnostics
```

პროფილები:
- `operational` (default): focus რეალურ runtime/frontend პრობლემებზე (Spot + Futures), ნაკლები noise.
- `full`: სრულად მოიცავს code-smell/AST აღმოჩენებსაც.

```bash
python3 -m platform_v2.tools.diagnostics --profile full
```

სისტემა აგენერირებს ორ report-ს whole-platform diagnostics ფოლდერში:
- [/home/sandro/SmartSignalHub/platform_v2/runtime/artifacts/diagnostics/](/home/sandro/SmartSignalHub/platform_v2/runtime/artifacts/diagnostics)

## Structure

- [__main__.py](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/__main__.py)
  - package entrypoint
- [orchestrator.py](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/orchestrator.py)
  - diagnostics run orchestration
- [checks](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/checks)
  - rule families
- [core](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/core)
  - config, models, report writing, shared helpers

## What It Checks

SQLite-primary checks require all three runtime databases (trading, market data,
content), run `quick_check`, and validate stored trading rows against the existing
Spot/Futures family registries without requiring JSON exports. Hedge rows are
checked for valid JSON objects; Hedge has no equivalent required-key registry.
Legacy JSON checks remain for explicit exports and parity comparisons.

Exit status is `1` when the selected profile contains high-severity findings,
otherwise `0`. A successful report write is not a clean-health certificate.

### SQLite ledger relationships and accounting

`sqlite_accounting_checks.py` reads trading rows and Futures engine state within
one read-only SQLite transaction. It checks:

- Unique signal decisions by system, symbol, timeframe, and candle timestamp.
- Duplicate same-day Spot position records and duplicate Futures lifecycle events;
  repeated position snapshots on different days and distinct updates are allowed.
- FILLED orders linked to exactly one position and reverse position/order links.
  Futures uses position IDs; Spot uses recorded fill time plus symbol because its
  order payload does not store a position ID.
- OPEN/CLOSED exit-field consistency and position counts versus latest metrics.
- Closed net/gross PnL, Futures recorded entry/exit fees, and account equity identities.
  Futures aggregate fees describe closed trades; open entry fees are read separately
  from engine state. No historical fee rate is hard-coded.
- Hedge entry/reset identities, source Futures positions, summary counts, fee totals,
  realized PnL, equity and available-capital identities.
- Spot force-close ledger counts, unique Futures closed-trade audit identities and
  counts, and Futures-to-Hedge entry totals (moved out of analytics baseline).

Diagnostics owns integrity verdicts. Analytics owns descriptive result reports;
diagnostics does not regenerate indicator/analytics snapshots or run a backtest.

These checks assume retained history covers the current trading epoch. Imported
partial histories can produce missing-link/accounting findings; investigate rather
than silently ignoring them. Monetary comparisons allow 0.021 USDT for rounding.

### Generated dashboard data

`dashboard_data_checks.py` validates embedded Overview equity chart values against
the backend chart contract and compares Spot/Futures/Hedge equity series to their
current backend source builders. A two-minute generation grace avoids flagging a
freshly written page mid-update. Source differences are medium-severity out-of-sync
warnings, not proof of accounting corruption.

Dashboard JavaScript reductions referencing financial fields are medium-severity
manual-review candidates. This intentionally conservative source heuristic does not
prove all JavaScript is calculation-free. These checks do not replace browser tests
or verify every table cell, chart type, published remote copy, or DOM mutation.

სისტემა ახლა ამოწმებს ამ ფენებს:
- `app`
- `config`
- `domain`
- `frontend`
- `futures`
- `infrastructure`
- `runtime`
- `services`
- `shared`
- `storage`
- `tools`

სისტემა ამოწმებს ამ ოჯახის პრობლემებს:

- Python compile / parse errors
- oversized files
- oversized functions
- complex functions
- broad `except`
- silent fallback `except`
- unused imports
- unused private helpers
- unused module constants
- duplicate top-level defs
- duplicate class method names
- orphan module candidates
- circular imports
- dead Python candidates
- layer violations
- runtime structure / schema drift
- runtime integrity / cross-file consistency
- runtime file growth / retention pressure signals
- top-level workspace structure drift
- frontend page / asset checks
- dead CSS candidates
- unused HTML hooks
- stale payload candidates
- explanation coverage checks
- SEO checks

## SEO Coverage

SEO checks ახლა მოიცავს:
- missing title
- missing meta description
- missing favicon
- missing canonical
- canonical mismatch
- missing OG core tags
- missing Twitter card tags
- accidental `noindex`
- duplicate titles
- duplicate descriptions
- weak title length
- weak description length
- missing JSON-LD schema
- missing sitemap
- missing sitemap coverage

## What It Does Not Check Well Yet

ეს სისტემა ჯერ კარგად არ ამოწმებს:
- რეალურ behavioural bugs-ს
- runtime correctness-ს live market context-ში
- UI/UX wording quality-ს
- CSS visual regressions
- JS runtime interaction bugs browser-ში
- accessibility audit-ს
- performance profiling-ს
- test coverage-ს
- external dependency health-ს
- design consistency-ს

მაგრამ უკვე ამოწმებს runtime integrity-ის ნაწილს:
- filled order-ს position მოჰყვა თუ არა
- metrics counts რეალურ latest position state-ს ემთხვევა თუ არა
- daily summary raw rows-ს ემთხვევა თუ არა
- runtime families ზრდის თვალსაზრისით საეჭვოდ ხომ არ მძიმდება

ანუ ეს არის ძლიერი static-smell detector, მაგრამ არა სრული reviewer ან test suite.

## Rule Modules

- [ast_checks.py](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/checks/ast_checks.py)
  - AST orchestration, layer rules, circular imports
- [ast_scan_helpers.py](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/checks/ast_scan_helpers.py)
  - AST parse helpers
- [ast_scan_state.py](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/checks/ast_scan_state.py)
  - top-level state collection
- [ast_scan_rules.py](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/checks/ast_scan_rules.py)
  - node-level AST rules
- [ast_scan_rule_utils.py](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/checks/ast_scan_rule_utils.py)
  - AST rule utilities
- [ast_scan_postprocess.py](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/checks/ast_scan_postprocess.py)
  - post-scan finding helpers
- [dead_code_checks.py](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/checks/dead_code_checks.py)
  - dead Python candidate detection
- [frontend_checks.py](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/checks/frontend_checks.py)
  - frontend structure, drift, CSS checks
- [html_hook_checks.py](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/checks/html_hook_checks.py)
  - unused `id` / `data-*` hooks
- [payload_checks.py](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/checks/payload_checks.py)
  - stale payload candidates
- [runtime_checks.py](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/checks/runtime_checks.py)
  - runtime family, schema, integrity, and growth checks
- [futures_runtime_checks.py](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/checks/futures_runtime_checks.py)
  - futures runtime family/schema/integrity checks
- [hedge_runtime_checks.py](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/checks/hedge_runtime_checks.py)
  - Hedge runtime families, schemas, duplicate IDs, orphan snapshots, and summary/timeline consistency
- [futures_dashboard_checks.py](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/checks/futures_dashboard_checks.py)
  - futures dashboard structure/drift/payload/CSS checks
- [seo_checks.py](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/checks/seo_checks.py)
  - SEO/head/sitemap/schema checks

## Notes

- findings ყოველთვის არ არის bug
- `low` ხშირად არის cleanup hint
- `medium` ხშირად არის maintainability risk
- `high` არის პირველ რიგში დასახური

## Recent Diagnostics Upgrades

ბოლო pass-ებში დაემატა:
- runtime integrity checks
  - filled order vs opened position
  - metrics vs latest position state
  - daily summary vs raw runtime rows
- runtime growth checks
  - family day-count pressure
  - latest JSON size pressure
  - latest JSON row-count pressure
- package-aware coverage
  - `services/ops/main_cycle/` package უკვე სწორად სკანდება როგორც family, არა როგორც დაკარგული მოდული

მიმდინარე მდგომარეობა ცალკე წერია აქ:
- [current_status.md](/home/sandro/SmartSignalHub/platform_v2/tools/diagnostics/current_status.md)

September 12 adds published-page canonical validation, including dashboard roots. An operational clean result is not proof of strategy profitability or Google indexing. Current verified counts and remaining maintenance candidates are in `platform_v2/tools/diagnostics/current_status.md`.
