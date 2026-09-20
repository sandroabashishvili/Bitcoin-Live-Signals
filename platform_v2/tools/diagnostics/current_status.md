# Diagnostics Current Status

Updated: 2026-09-12.

After the maintenance fixes, operational diagnostics reports **0 findings** on the local tree. The full profile reports **383 findings**, severity counts `{'high': 20, 'medium': 211, 'low': 152}`. Its 20 high findings are size/complexity flags; this does not establish trading corruption. Full diagnostics remains a maintenance backlog, not a clean code certificate.

Resolved this pass: seven missing content batches restored from retained public snapshots after backup; local sitemap custom-domain coverage regenerated; four Spot canonical identities fixed in renderers and local publication HTML; two unused helpers and confirmed unused imports removed. Published canonical coverage is now checked explicitly.

The isolated publication preview passes internal-link, sitemap, canonical and analytics-ID checks. Remote publishing has not been performed by this audit, so local clean diagnostics does not prove the public site has received the fix.

Reports: `platform_v2/runtime/artifacts/diagnostics/v2_code_diagnostics_2026-09-12.json` and `v2_code_diagnostics_full_2026-09-12.json`. Evidence and change backups: `/home/sandro/research_snapshots/system_review_20260912/`.

Two SnapshotFormat imports are intentional re-exports, and the Spot signal-decision alias is referenced by assistant code lookup. These were retained. Similar independently owned Spot/Futures functions were not merged solely to silence duplication findings.
