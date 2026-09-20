# Diagnostics

Status: `active - backend architecture and SQLite parity checks`  
Created: `2026-05-19`  
Author: Codex  
Purpose: Define what diagnostics should and should not check.
Updated: `2026-09-12`

## Run Command

Default operational profile:

```bash
cd ~/SmartSignalHub
source venv/bin/activate
python3 -m platform_v2.tools.diagnostics
```

Full profile:

```bash
python3 -m platform_v2.tools.diagnostics --profile full
```

Reports are written under:

```text
platform_v2/runtime/artifacts/diagnostics/
```

## Diagnostics Should Check

- missing runtime families
- malformed JSON
- missing frontend generated outputs
- stale docs/path references where practical
- frontend/backend boundary violations
- oversized generated pages where relevant
- broken imports/syntax
- Spot/Futures runtime schema and integrity drift
- public-site SEO/head/sitemap issues
- exact duplicated Python function bodies across backend modules
- unreachable backend statements after unconditional control flow
- reverse dependencies from shared backend into a strategy subsystem
- services whose size and responsibility mix require architectural review
- JSON/SQLite document parity and stale database documents

## Diagnostics Should Not Pretend To Decide

These are analytics/backtesting/research topics, not basic diagnostics:

- trading edge quality
- gate weights correctness
- TP/SL profitability
- sample size sufficiency
- business logic quality

Diagnostics can detect suspicious conditions, but final tuning requires audit/replay/research.

## Desired Direction

Diagnostics should help find engineering/system problems earlier:

- frontend calculating values that backend should provide
- missing runtime reports required by pages
- stale path names after migrations
- malformed generated JSON
- syntax/import errors
- generated pages that are unexpectedly huge

Trading research belongs in analytics/replay/audit modules.

## Profiles

`operational` is the default profile. It suppresses lower-value cleanup noise such as broad excepts, oversized files, dead CSS candidates, unused helpers, and similar maintainability hints.

`full` includes AST/code-smell findings, dead-code candidates, circular imports, and more noisy cleanup signals.

Pytest/unittest modules and their test functions are excluded from dead-code
and orphan-module candidates. A `dead_python_candidate` remains a review hint,
not proof that deletion is safe; references by configuration, CLI discovery,
or generated entrypoints still require manual verification.

## Active Check Families

Diagnostics currently runs:

- Python compile/parse checks
- runtime structure/schema/integrity checks
- Futures runtime structure/schema/integrity checks
- top-level structure checks
- Spot frontend checks
- Futures frontend checks
- frontend payload checks
- unused HTML hook checks
- SEO checks
- semantic ownership checks

Full profile additionally runs deeper AST/dead-code/circular-import scans.

Size and complexity findings are review signals, not automatic deletion rules:

```text
function > 120 lines          high review priority
function complexity > 35     high review priority
Python file > 600 lines       high review priority
```

The duplicate scanner reports exact bodies of meaningful size. A duplicate
may be consolidated only after ownership and subsystem configuration are
checked; identical-looking trading rules are not merged blindly.

## Known Limits

Diagnostics is not a trading edge evaluator.

It does not decide:

- whether gate weights are profitable
- whether TP/SL policy has edge
- whether sample size is enough for tuning
- whether LONG/SHORT strategy is good

Those belong to analytics, audit reports, and replay tools.

Diagnostics can still flag engineering smells that lead to trading confusion, such as frontend calculating metrics that backend should provide.

September 12 adds published-page canonical validation, including dashboard roots. An operational clean result is not proof of strategy profitability or Google indexing. Current verified counts and remaining maintenance candidates are in `platform_v2/tools/diagnostics/current_status.md`.
