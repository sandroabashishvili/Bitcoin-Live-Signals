# Historical snapshot replay engines

This package is older than the pinned full-system laboratories documented in
`../SIGNAL_LAB.md` and `../SPOT_LAB.md`, but remains executable and regression-tested.
Do not infer production strategy state from historical candidate names or dates.

- `signal_only_replay.py`, `historical_component_replay.py`: historical decisions.
- `execution_replay.py`, `portfolio_state_replay.py`, `portfolio_replay_*.py`:
  execution/accounting simulations and shared adapters.
- `candidate_*.py`, `component_weight_candidates.py`: candidate policies/profiles.
- `*_what_if.py`, `*_audit.py`, `*_screen.py`, `*_grid_replay.py`: focused studies.
- `profiles/`: JSON candidate specs and dated promotion/calibration records.
- `replay_research_tools.md`: detailed historical engine commands and limitations.

Python module import/CLI paths are retained, including recorded-run consumers.
The default forward-shadow spec now resolves from `profiles/`. Tests belong in
`../tests/replay/`; no test modules remain mixed into this implementation package.
