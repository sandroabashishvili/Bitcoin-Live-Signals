# Spot Metrics System

Status: `active`
Created: `2026-04-11`
Updated: `2026-09-12`
Author: Codex
Purpose: Spot runtime-computed metrics truth and frontend metric payload preparation.

Central home for runtime-computed metrics truth.

Current scope:
- portfolio/strategy summary metrics
- metrics persistence into trading SQLite, Spot `metrics` family
- backend-prepared grouped metric items for frontend pages
- backend-prepared page content helpers for runtime frontend pages

Current entrypoint:
- [summary_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/metrics_system/summary_service.py)

Design intent:
- business metric semantics live here
- frontend renderers should not invent metric logic
- page builders may consume grouped metric payloads prepared from this layer

Current modules:
- [summary_service.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/metrics_system/summary_service.py)
- [grouped_payloads.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/metrics_system/grouped_payloads.py)
- [portfolio_content.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/metrics_system/portfolio_content.py)
- [overview_content.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/metrics_system/overview_content.py)
- [strategy_content.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/metrics_system/strategy_content.py)
- [orderbook_content.py](/home/sandro/SmartSignalHub/platform_v2/spot/services/metrics_system/orderbook_content.py)

Current boundary status:
- `Portfolio` content truth moved here for cards/tables/chart payload
- `Overview` content truth moved here for snapshots/chart/timeframe/health payload
- `Strategy` content truth moved here for same-day filtering, snapshots, recent signals, and logic payload
- `Orderbook` content truth moved here for KPI/history/chart payload

Rule:
- if content must still make sense without `frontend/`, it belongs here or another backend layer first
- if it is purely visual layout, it stays in `frontend/`
