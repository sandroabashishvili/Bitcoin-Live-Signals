# Diagnostics Current Status

Updated: 2026-09-12.

After the maintenance fixes, operational diagnostics reports **0 findings** on the local tree. The full profile reports **383 findings**, severity counts `{'high': 20, 'medium': 211, 'low': 152}`. Its 20 high findings are size/complexity flags; this does not establish trading corruption. Full diagnostics remains a maintenance backlog, not a clean code certificate.

Resolved this pass: seven missing content batches restored from retained public snapshots after backup; local sitemap custom-domain coverage regenerated; four Spot canonical identities fixed in renderers and local publication HTML; two unused helpers and confirmed unused imports removed. Published canonical coverage is now checked explicitly.

The isolated publication preview passes internal-link, sitemap, canonical and analytics-ID checks. Remote publishing has not been performed by this audit, so local clean diagnostics does not prove the public site has received the fix.

Retention update, 2026-10-18: the historical September 12 diagnostic output files were deliberately deleted with user approval. The counts above describe the dated audit, not a newly verified current result. Separate evidence/change backups remain at `/home/sandro/runtime_archives/trading_epoch_2026-10-18_v1/retired_metadata/research_snapshots_2026-10-18/system_review_20260912/`. Fresh diagnostics still use the normal runtime artifact output directory.

Two SnapshotFormat imports are intentional re-exports, and the Spot signal-decision alias is referenced by assistant code lookup. These were retained. Similar independently owned Spot/Futures functions were not merged solely to silence duplication findings.
