# SmartSignalHub assistant integration contract

Updated: 2026-09-25

## Ownership

Implementation and internal design belong to `/home/sandro/workspace_tools/ai_assistant`.
Internal design: `/home/sandro/workspace_tools/ai_assistant/docs/internal_design.md` (local workspace document, not shipped in this public repository).
Run `~/workspace_tools/ai_assistant/run.sh --help` for supported commands.
Mr.B's public knowledge pack remains in `../product/mr_b/` and is not this internal assistant.

## Project boundary

The launcher selects SmartSignalHub using `SMARTSIGNALHUB_ROOT` (default `~/SmartSignalHub`) and its Python environment, unless `WORKSPACE_PYTHON` overrides it. Project readers depend on SmartSignalHub's storage APIs, settings and public frontend.
Canonical trading/market data stays in `platform_v2/runtime/database/`; readers use the project's runtime-store/persistence APIs. Reading reports must not rewrite trading records or open positions.
Assistant conversation/research references use `platform_v2/runtime/artifacts/ai_assistant/`, `platform_v2/runtime/artifacts/research/replay/` and tool logs under `platform_v2/runtime/logs/tools/`. Moving these paths requires updating assistant readers too.

## Action boundary

Read-only explanations and action execution are distinct. Commands that publish, generate artifacts or change state must retain the assistant's explicit action-confirmation checks. No new execution authority is granted by this documentation change.
Telegram remains a separate transport under `platform_v2/tools/telegram_bot_system`; a planned Telegram assistant integration is not a claim of implemented functionality.

## Maintenance

Validate changed storage/report contracts against assistant readers and regression checks. Keep internal UI, model-provider, intent-routing and operation details in the workspace tool documentation. Keep source-of-truth data and trading policy in SmartSignalHub.
