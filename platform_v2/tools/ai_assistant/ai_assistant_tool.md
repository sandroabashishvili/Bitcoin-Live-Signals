# SmartSignalHub AI Assistant Tool

Status: `in progress`
Created: `2026-06-03`
Updated: `2026-06-12`
Author: Codex
Purpose: Deterministic SmartSignalHub assistant CLI with capability routing.

## Command

CLI ask:

```bash
cd ~/SmartSignalHub
source venv/bin/activate
python3 -m platform_v2.tools.ai_assistant ask "ბოლო ფუჩერს სიგნალზე რას მეტყვი?"
```

Optional model composer:

```bash
python3 -m platform_v2.tools.ai_assistant ask "ბოლო ფუჩერს სიგნალზე რას მეტყვი?" --model ollama:qwen2.5-coder:7b
```

Regression checks:

```bash
python3 -m platform_v2.tools.ai_assistant regression
```

Browser chat:

```bash
cd ~/SmartSignalHub
source venv/bin/activate
python3 -m platform_v2.tools.ai_assistant serve
```

Default local URL:

```text
http://127.0.0.1:8787
```

Optional port override:

```bash
python3 -m platform_v2.tools.ai_assistant serve --port 8790
```

Optional browser model composer:

```bash
python3 -m platform_v2.tools.ai_assistant serve --model ollama:qwen2.5-coder:7b
```

## Current Scope

- latest Futures signal
- latest Spot signal
- latest Futures/Spot position status
- latest denied entry
- latest diagnostics report summary
- first-vs-latest signal comparison
- latest metrics summary
- win/loss snapshot from metrics
- project file inventory
- local Git change snapshot
- source area lookup for signal/risk logic
- focused code explanations for MTF, proximity, entry quality, and SL/TP
- targeted docs/code comparison for permission, Futures signal, and SL/TP policy
- grouped Git worktree summary
- local GitHub remote/upstream fallback
- local site-analytics source discovery
- runtime health summary
- strategy blocker/gate audit
- Futures trade audit summary
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
- dedicated tool details for news generation, GitHub publish, sitemap, Telegram, backup, research, video reels, and diagnostics action-safe status
- artifact index
- runtime access coverage for shared, Futures, and Spot runtime roots
- action-confirm foundation with command candidates, manual-only boundaries, risk classes, confirmation policy, and audit log target
- confirm-required action proposals for diagnostics, sitemap, news generation, research replay, Telegram bot actions, and video reels
- analytics system wrapper/action proposals for report-generating Spot/Futures analytics services
- confirm-run execution layer: pending action id, explicit confirmation, command outcome audit row
- read-only tool-runner policy
- active docs search
- unsupported-question safety response instead of unrelated runtime fallback

## Capabilities

```text
capabilities/runtime.py
capabilities/metrics.py
capabilities/diagnostics.py
capabilities/changes.py
capabilities/code_search.py
capabilities/docs_compare.py
capabilities/docs_search.py
capabilities/site_analytics.py
capabilities/github_status.py
capabilities/news.py
capabilities/runtime_health.py
capabilities/strategy_audit.py
capabilities/trade_analysis.py
capabilities/window_analysis.py
capabilities/denied_deep_analysis.py
capabilities/blocker_statistics.py
capabilities/trade_lifecycle.py
capabilities/audit_recommendations.py
capabilities/artifact_index.py
capabilities/runtime_access.py
capabilities/action_confirm.py
capabilities/tools_registry.py
capabilities/tools_status.py
capabilities/tool_details.py
capabilities/tool_runner.py
capabilities/unsupported.py
```

`site_analytics`, `github_status`, and `news` are source-gated. They provide local fallback/source requirements and do not guess without configured trusted sources.

`docs_compare` currently runs a targeted deterministic audit across trading docs and selected code modules.

## Boundary

Facts are extracted by Python readers from real runtime files.

Project answers are wrapped in a standard first-pass contract:

```text
Verdict
Facts
Sources
Limitations
```

General and unsupported answers are not wrapped.

Language models are optional adapters. They may explain extracted facts, but must not parse canonical runtime ledgers directly or invent facts.

Current model adapter:

```text
model_adapter.py
```

It is disabled by default. When enabled with `--model ollama:<model>`, the deterministic assistant answer remains the source of truth.

Unsupported non-project questions stay unsupported by default. Experimental general model passthrough is available only with an explicit `/general ...` prefix when `--model ollama:<model>` is enabled.

## Browser Server

Endpoints:

```text
GET  /
GET  /health
POST /api/ask
```

Chat history is written to:

```text
platform_v2/runtime/artifacts/ai_assistant/chat_history_YYYY-MM-DD.jsonl
```

Action audit rows are written to:

```text
platform_v2/runtime/artifacts/ai_assistant/action_audit_YYYY-MM-DD.jsonl
```

Action flow:

```text
prepare/run <allowed action with required input>
-> pending action id
-> confirm action <action_id>
-> started/outcome audit rows
```
