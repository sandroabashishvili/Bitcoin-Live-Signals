# Operational deployment

This directory owns the operational launch configuration. Research datasets and
experiments must not be required to start the service or its health monitor.

- `deploy/activation.json`: the explicitly selected, hash-verified Python source.
- `releases/<sha256>/`: the selected immutable code snapshot and its launcher.
- `sqlite/`: the native SQLite library required by that snapshot.
- `deploy/start.py`: the systemd entry point; retains the existing single-writer lock.
- `deploy/check-health.py`: scheduled monitor, using the same selected code.
- `migration/`: before/after evidence and rollback configuration for the relocation.

The October 2026 relocation preserves the running code hash, trading epoch,
strategy settings and all three live databases. It does not reset accounts or
deploy a research candidate. Editing working-tree Python still requires an
explicit reviewed code promotion and service restart; relocation is not promotion.

Only one source snapshot is selected here. The former research deployment is
temporarily retained as a rollback copy, not an active launch dependency.

Service: `systemctl --user status smartsignalhub-runtime.service`

Monitor: `venv/bin/python platform_v2/deployment/deploy/check-health.py`

Do not run `runtime_reset_system` merely to restart or relocate the service.
