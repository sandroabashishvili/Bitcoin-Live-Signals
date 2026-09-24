# SmartSignalHub AI Assistant

Status: `in progress - browser chat UI cleanup added on 2026-06-04`  
Created: `2026-06-03`  
Updated: `2026-06-04`  
Author: Codex  
Purpose: Define the SmartSignalHub-aware assistant, its boundaries, and the staged implementation plan.

## Decision

The trusted assistant will be a project-owned, model-agnostic tool under:

```text
platform_v2/tools/ai_assistant/
```

Runtime outputs and logs will live under:

```text
platform_v2/runtime/artifacts/ai_assistant/
platform_v2/runtime/logs/tools/
```

## Goal

The goal is a free-form SmartSignalHub chat, not a fixed menu of prepared questions.

The assistant should support natural questions such as:

```text
ბოლო სიგნალზე რას მეტყვი?
სპოტი რატომ დუმს?
ფუჩერსზე ბოლო პოზიცია რატომ გაიხსნა?
რომელმა გეითმა დაბლოკა?
დღეს რა მოხდა?
```

The assistant should choose the right reader/tool internally and answer from real project/runtime data.

## Core Principle

Facts must come from deterministic Python readers, not from the language model.

The model may explain or summarize, but it must not invent:

- file paths
- signal rows
- gate states
- permission status
- runtime ledger values
- trading conclusions

For example:

```text
user question
-> intent router
-> deterministic reader
-> facts bundle
-> optional model explanation
-> final answer
```

## Why Not Pure RAG

Plain RAG or editor indexing is not enough for this project because runtime and trading questions require exact data handling.

Examples:

- last row in a JSON ledger
- latest open Futures position
- denied-entry reason
- gate pass/fail state
- time field consistency
- score vs threshold

These must be parsed by code. A model can help explain the result after the facts are extracted.

## Current Implementation

The first version is CLI-only and reads real runtime files through deterministic Python readers:

```bash
cd ~/SmartSignalHub
source venv/bin/activate
~/workspace_tools/ai_assistant/run.sh ask "ბოლო ფუჩერს სიგნალზე რას მეტყვი?"
```

Browser chat is available with:

```bash
cd ~/SmartSignalHub
source venv/bin/activate
~/workspace_tools/ai_assistant/run.sh serve --model ollama:qwen2.5-coder:7b
```

Default local URL:

```text
http://127.0.0.1:8787
```

Local port convention:

```text
11434  Ollama model server
8787   SmartSignalHub assistant/browser chat
8080   optional static file server for public site/dashboard files
```

Avoid leaving temporary assistant ports such as `8788` or `8789` running after UI tests. The daily assistant URL should remain `http://127.0.0.1:8787`.

Browser chat layout as of `2026-06-04`:

- left side: chat transcript plus composer/input
- composer: `Project` / `General` mode toggle above the input
- right side: one `Assistant Tools` panel
- tools tabs: `Prompts`, `Actions`, `History`, `Docs`
- prompts grouped by `Signals`, `Capital`, `Diagnostics`, and `Tools`
- action preparation and pending action inspection live under `Actions`
- recent chat questions live under `History`, not on the default screen
- docs shortcuts live under `Docs`

Supported in CLI v1:

- latest Futures signal
- latest Spot signal
- latest Futures position
- latest Spot position when rows exist
- latest denied entry
- latest diagnostics report summary
- signal first-vs-latest comparison
- latest Spot/Futures metrics summary
- win/loss snapshot from metrics
- project file inventory
- local Git change snapshot
- code area lookup for signal and risk logic
- focused code explanations for MTF, proximity, entry quality, and SL/TP logic
- targeted docs/code comparison for permission, Futures signal, and SL/TP policy
- grouped Git worktree summary
- local GitHub remote/upstream fallback
- local site-analytics source discovery
- runtime health summary for Spot/Futures loops
- strategy audit for blockers, gate pressure, and Futures gate effectiveness
- Futures trade analysis from trade entry audits
- last N Futures signal permission status/reason summary
- last N Futures denied-entry reason grouping
- last N Spot signal status/failed-gate summary
- Spot blocker statistics from signal rows
- Spot latest signal block analysis
- Futures LONG vs SHORT audit performance
- biggest Futures weakness snapshot from audit evidence
- Futures permission-file path lookup
- latest denied signal vs existing open same-direction position explanation
- deep denied-entry analysis
- blocker statistics over recent denied-entry windows
- Futures trade lifecycle reconstruction by position id
- Spot trade lifecycle boundary response when position/audit ledgers are not wired
- audit recommendation snapshots from trade/research reports
- Spot audit recommendation snapshot from signals/metrics
- internal tools registry and status
- artifact index
- runtime access coverage for shared, Futures, and Spot runtime roots
- action-confirm foundation with command candidates, manual-only boundaries, risk classes, confirmation policy, and audit log target
- confirm-required action proposals for diagnostics, sitemap, news generation, research replay, Telegram bot actions, and video reels
- analytics system wrapper/action proposals for report-generating Spot/Futures analytics services
- confirm-run execution layer: pending action id, explicit confirmation, command outcome audit row
- read-only tool-runner policy
- unsupported-question safety response instead of unrelated runtime fallback
- active docs search

The first version answers without a model. Accuracy comes first.

## Planned Capabilities

Capability modules live under:

```text
platform_v2/tools/ai_assistant/capabilities/
```

Current modules:

- `runtime.py`
- `metrics.py`
- `diagnostics.py`
- `changes.py`
- `code_search.py`
- `docs_compare.py`
- `docs_search.py`
- `runtime_health.py`
- `strategy_audit.py`
- `trade_analysis.py`
- `window_analysis.py`
- `denied_deep_analysis.py`
- `blocker_statistics.py`
- `trade_lifecycle.py`
- `audit_recommendations.py`
- `artifact_index.py`
- `runtime_access.py`
- `action_confirm.py`
- `tools_registry.py`
- `tools_status.py`
- `tool_details.py`
- `tool_runner.py`
- `unsupported.py`
- `site_analytics.py`
- `github_status.py`
- `news.py`

Stage 1: runtime facts - started on `2026-06-03`

- latest Futures signal
- latest Spot signal
- latest Futures position
- latest Spot position
- latest denied entry
- passed/failed gate summary
- permission status and main blocker summary

Stage 2: intent routing - basic version started on `2026-06-03`

- Georgian and English keyword routing
- typo-tolerant routing where practical
- ambiguity handling with a short follow-up question
- no guessing when intent is unclear

Stage 3: diagnostics integration

- latest diagnostics report summary - started on `2026-06-03`
- project file inventory - started on `2026-06-03`
- top-level file inventory breakdown - started on `2026-06-03`
- runtime health summary - started on `2026-06-03`
- high/medium finding explanation
- misplaced runtime artifact checks
- frontend/backend boundary findings

Stage 4: docs/code search

- locate source modules - started on `2026-06-03`
- focused logic summaries for MTF, proximity, entry quality, and SL/TP - started on `2026-06-03`
- targeted docs/code compare started on `2026-06-03`
- search active docs - started on `2026-06-03`
- explain a specific file/function from real file content
- compare focused files only after deterministic file loading

Stage 4b: strategy and trade audit - started on `2026-06-03`

- blocker and permission-reason summary
- Futures gate effectiveness report summary
- Futures last audited trades summary
- side/timing/location attribution from trade audits
- LONG vs SHORT side performance from Futures trade audits
- biggest Futures weakness snapshot from current audit evidence

Stage 4c: runtime window analysis and safe fallback - started on `2026-06-03`

- last N Futures signals grouped by `permission_status` and `permission_reason`
- last N Futures denied entries grouped by `permission_reason`
- latest denied signal explained against an existing open same-direction position
- permission-file path lookup
- unsupported questions return an explicit unsupported answer instead of a misleading fallback

Stage 4d: tool/artifact foundation and deep trading readers - started on `2026-06-03`

- artifact index for diagnostics, research, runtime ledgers, video reels, chat history, backup archives, and tool logs
- registry of internal tools and their read/action safety mode
- read-only tool-runner policy boundary
- deep latest-denied Futures analysis
- blocker statistics over recent denied-entry windows
- Spot blocker statistics from signal rows because Spot currently has no separate denied-entry ledger
- trade lifecycle reconstruction by Futures position id
- Spot lifecycle response that clearly reports missing position/event/audit ledgers
- audit recommendation snapshot from existing audit/replay reports
- Spot recommendation snapshot from signals/metrics until Spot trade audits exist
- regression command for routing checks

Current docs/code compare targets:

- `trading/risk_and_permissions.md` vs Spot/Futures permission code
- `trading/futures_rules.md` vs Futures signal decision settings/code
- `trading/sl_tp_policy.md` vs Spot/Futures adaptive SL/TP calculators

## Current QA Plan

Next controlled model/browser test questions:

```text
What can you tell me about the latest futures signal?
Why was the latest futures signal denied?
Show current spot and futures capital.
Show open positions for spot and futures.
Compare the latest futures signal with the latest spot signal.
What does diagnostics say right now?
Can you run diagnostics?
What internal tools can you inspect?
/general What happened in World War II?
/general Explain what SEO means in simple terms.
```

Watch for:

- project numbers must not be changed by the model
- source paths must remain visible for project answers
- unsupported project questions must say they are unsupported instead of guessing
- project questions must not fall back to general model guessing
- `/general` questions must not use project files as source of truth

Near-term hardening:

- keep all project answers under the `Verdict`, `Facts`, `Sources`, and `Limitations` contract
- add a separate `Explanation` section where useful without making short answers noisy
- strengthen capital/metrics answers, including starting capital and current balance/equity questions
- prevent timestamp or numeric recalculation by the model when deterministic Python facts already exist
- continue action-confirm browser polish for diagnostics, research, Telegram, video, and analytics actions

External-source capabilities registered as source-gated modules on `2026-06-03`:

- site analytics: checks local candidate folders but does not guess visitor counts
- GitHub status: reads local git remote/branch/upstream and reports whether `gh` is available
- news

These must not guess until a trusted source is configured.

Stage 5: browser chat

Command:

```bash
~/workspace_tools/ai_assistant/run.sh serve
```

Target local URL:

```text
http://127.0.0.1:8787
```

Browser chat was added on `2026-06-03` with:

- `GET /`
- `GET /health`
- `POST /api/ask`
- daily JSONL history under `platform_v2/runtime/artifacts/ai_assistant/`

Stage 6: optional model explanation layer

Any supported local or remote model can be used only after facts are extracted by Python. The model receives a constrained facts bundle and is not allowed to alter facts.

The assistant should not depend on a single model vendor, editor extension, or chat UI. Model adapters should be replaceable.

Initial Ollama composer was added on `2026-06-03`:

```bash
~/workspace_tools/ai_assistant/run.sh ask "..." --model ollama:qwen2.5-coder:7b
~/workspace_tools/ai_assistant/run.sh serve --model ollama:qwen2.5-coder:7b
```

It is optional and disabled by default.

Unsupported handling:

- project/trading/tool-looking unsupported questions stay unsupported
- general non-project unsupported questions stay unsupported by default
- experimental general model passthrough requires explicit `/general ...` when `--model` is enabled
- project facts still require deterministic readers first

## Near-Term Plan

Priority order after the first model-composer test:

1. Project answer contract

Every project answer should be shaped as:

```text
Verdict
Facts
Explanation
Sources
Limitations
```

The exact section names may be omitted for very short answers, but the information should remain present.

First pass added on `2026-06-03`: project answers render with `Verdict`, `Facts`, `Sources`, and `Limitations`. General and unsupported answers are intentionally not wrapped.

2. Tool intelligence

The assistant should answer operational questions about:

```text
backup_system
diagnostics
github_publish_system
news_generation_system
research
runtime_reset_system
runtime_start_system
sitemap_system
telegram_bot_system
video_reels
```

The next read-only upgrade is latest log/error/artifact summary for each tool.

First pass added on `2026-06-03`: tool status includes latest tool-specific logs, modified time, and recent error/failed/exception lines when present.

Dedicated tool detail readers added on `2026-06-03`:

```text
news_generation_system -> latest news data, item count, source counts, top items, logs
github_publish_system -> latest publish log, commit/push/sitemap events, pages repo
sitemap_system -> sitemap URL count and area breakdown
telegram_bot_system -> subscriber counts and active subscribers
backup_system -> latest backup folder/zip/manifest/logs and safe future command candidate
research -> latest replay reports and summary fields
video_reels -> latest mp4/srt artifacts and current status highlights
diagnostics -> action-safe status before enabling chat-triggered runs
```

3. Action-confirm boundary

Before the assistant runs any command, add:

```text
requested_by_question
command
started_at
finished_at
exit_status
log_path
artifact_path
```

No reset/start/publish action should run from chat without explicit confirmation.

4. Regression expansion

Raise the assistant regression set from 19 to roughly 40 project-focused cases before adding automatic hybrid routing.

5. Model upgrade and hybrid routing

Keep current `/general ...` passthrough experimental. After a stronger model/hardware setup exists, test:

```text
project facts from Python
+ separate general educational context from the model
```

Hybrid answers must keep project facts and general context visibly separate.

## Telegram Boundary

The existing Telegram bot remains a notification and command surface.

Current Telegram bot location:

```text
platform_v2/tools/telegram_bot_system/
```

The AI assistant should not be mixed into the Telegram bot folder.

Future integration may add Telegram commands that call assistant readers, for example:

```text
/ask ბოლო ფუჩერს სიგნალზე რას მეტყვი?
```

But the assistant logic should stay in:

```text
platform_v2/tools/ai_assistant/
```

Telegram should remain a transport/UI layer, not the source of assistant logic.

## Folder Ownership

Assistant source:

```text
platform_v2/tools/ai_assistant/
```

Assistant runtime artifacts:

```text
platform_v2/runtime/artifacts/ai_assistant/
```

Assistant/tool logs:

```text
platform_v2/runtime/logs/tools/
```

Telegram bot:

```text
platform_v2/tools/telegram_bot_system/
```

Trading runtime is database-primary:

```text
platform_v2/runtime/database/smartsignalhub_trading.sqlite3
platform_v2/runtime/database/smartsignalhub_market_data.sqlite3
```

The assistant must read through runtime-store APIs and must not rewrite
canonical trading database records.

## Open Questions

- Should the browser UI be plain Python stdlib HTTP first, or use a small framework later?
- Should Telegram `/ask` be added after CLI is stable?
- Which questions should be part of the first acceptance test set?
- Should a model explanation layer be added in stage 1 or only after deterministic answers are trusted?

## Acceptance Tests For First Version

The first version is useful only if these free-form questions return factual answers without guessing:

```text
ბოლო ფუჩერს სიგნალზე რას მეტყვი?
ბოლო სპოტ სიგნალი რა იყო?
ბოლო პოზიცია რა მდგომარეობაშია?
რატომ არ გაიხსნა ბოლო სიგნალი?
დიაგნოსტიკა რას ამბობს?
```

If a required runtime family is missing or empty, the assistant must say that clearly.
