# Phase 1 — minimal cleanup and reproducibility preparation

Date: 2026-09-25. No signal edge analysis, live runtime start, reset, strategy tuning or database rewrite performed.

## Changes

- `tools/tools_system.md`: corrected backup/publishing/assistant workspace ownership.
- `tools/research/replay/replay_research_tools.md` and `tools/research/__main__.py`: documented SQLite-first snapshot export and historical JSON compatibility.
- `docs/system/ai_assistant.md`: retained project integration contract. Full internal design notes preserved in `/home/sandro/workspace_tools/ai_assistant/docs/internal_design.md`; workspace assistant README links to them. No new public link depends on that local-only document.
- `tools/research/recorded_run.py`: new opt-in recorder for five snapshot-based replay CLIs, with their default options. Replay implementations, candidate profiles, thresholds and existing tests were not edited.
- `tools/research/test_recorded_run.py`: synthetic provenance/boundary tests.

## Deferred archival

`tools/research/artifacts/entry_timing_20260916` remains in place. Its script reads a mutable current database and imports current entry-quality policy. The original input snapshot and code revision have not been established; today's hash would not establish historical reproducibility. No historical metadata was invented. Existing references remain valid. Mr.B, sitemap, replay implementations and the large runtime research artifact tree remain untouched.

## Metadata contract

`run_metadata.json`, format `smartsignalhub-research-run-v1`:

- `started_at`, `finished_at`, `status`, optional `error_type`;
- `command`;
- `source`: Git revision/status if available, source/config SHA-256 inventory, Python version;
- `parameters`: JSON-serializable Spot/Futures settings excluding credential fields, plus resolved candidate profile dataclasses (including weights, thresholds and policy IDs);
- `dataset`: frozen snapshot root, manifest hash, validated per-file hashes and observed `timestamp_ms` bounds/counts per file;
- `limitations`.

Metadata is persisted before execution, finalized on success or failure, and source/snapshot stability is checked after successful execution. Unlisted JSON inputs, modified snapshot content, overlapping input/output trees and live-runtime output are rejected. Dataset coverage does not establish feature availability, strategy-version homogeneity or usable sample size. Those are Phase 2 work.

## Validation

- Research, analytics and diagnostics test suites plus initial recorder tests: 130 passed.
- Final recorder tests after two additional boundary cases: 10 passed.
- Research and recorded-run CLI help/import smoke: passed.
- `git diff --check`: passed.
- No operational diagnostics against live databases and no live runtime smoke were run. Diagnostics validation here means its isolated test suite.

## Remaining limitations

- Existing direct replay invocations bypass the new recorder. Only the five explicitly allowed default-option snapshot CLIs are supported by the recorded launcher; custom grids, legacy date/root CLIs and forward-shadow specifications require separate provenance integration before use in a new audit.
- Metadata identifies but does not archive executable source or install dependencies. Retain the exact source checkout and snapshot; dirty source cannot be reconstructed from a commit ID alone.
- Snapshot export uses multiple persistence reads, not an established atomic cross-database snapshot. Consistency and data coverage must be checked before analysis.
- Historical audit archival remains deferred as explained above.

Checkpoint: stop after Phase 1; Phase 2 requires owner confirmation.
