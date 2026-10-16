# Research regression tests

These tests validate code; they are not dated trading results or disposable logs.

- `data/`: snapshot export and historical indicator preparation.
- `frozen_lab/`: pinned signal/portfolio/Spot labs and input/permission audits.
- `experiments/`: candidate generation, formula boundaries and isolation of changes.
- `replay/`: historical replay engines, candidate policies and their shared helpers.
- `runtime_parity/`: timing, flip confirmation and native runtime-policy contracts.
- `paths.py`: common production-source boundary, independent of test folder depth.

From `/home/sandro/SmartSignalHub`, using the configured SQLite library:

```bash
LD_LIBRARY_PATH=/home/sandro/research_snapshots/readiness_R21_20260927/sqlite venv/bin/python -m pytest platform_v2/tools/research -q
```

Use the whole `research` path for the full 300-test suite. File paths changed in
the 2026-10-15 organization; old dated commands targeting a single flat test file
must use the matching new subfolder. No test assertions were removed.
