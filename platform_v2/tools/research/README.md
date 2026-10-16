# Research tooling

This directory contains executable research code and its tests, not disposable
database snapshots. File age alone is not a deletion criterion.

## Current frozen full-system laboratories

- `signal_lab.py`, `signal_lab_worker.py`, `portfolio_lab_support.py`:
  pinned-source signal/Futures portfolio experiments; see `SIGNAL_LAB.md`.
- `spot_lab.py`, `spot_lab_worker.py`, `spot_lab_support.py`: full Spot replay;
  see `SPOT_LAB.md`. No automatic promotion or live database writes.
- `*_rules_experiment.py`, `*_symmetry_experiment.py`: declared offline candidates,
  not automatically active production formulas.
- `snapshot.py`, `historical_indicators.py`, `paths.py`: input export and history
  preparation, with SQLite-first sources and historical JSON compatibility.

## Historical replay engines

`replay/` contains earlier snapshot-based engines and their shared policies. Many
July/August modules are still imported by one another, the recorded-run tooling
and regression tests. They are not all unused, nor are they the current pinned
full-system laboratory. Public Python module paths are retained deliberately.
Historical JSON profiles/decisions now live in `replay/profiles/`; see its README.

## Tests

`tests/` is grouped by responsibility: data export, frozen laboratories, formula
experiments, historical replay and runtime-policy parity. See `tests/README.md`.
The misplaced legacy regime test was moved from `replay/` into `tests/replay/`.

## Data and operating boundaries

Research SQLite copies and generated reports belong outside the source checkout,
normally under `/home/sandro/research_snapshots`. Some older operational releases
also live there and are referenced by systemd: do not delete or relocate them as
ordinary research output. Cleanup never authorizes production strategy changes.

2026-10-15 organization: historical profiles grouped, tests relocated without
dropping test coverage, common source path calculation centralized. The full
research suite passed 300 tests both before and after organization.
