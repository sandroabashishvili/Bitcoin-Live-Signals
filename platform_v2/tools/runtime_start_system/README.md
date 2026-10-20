# Runtime startup

The user service runs the normal project directly:
`/home/sandro/SmartSignalHub/venv/bin/python -m platform_v2.tools.runtime_start_system`.
There is no operational code snapshot or release selection.

`service.env` retains collection, atomic simulation, the October 18 epoch and
the required native SQLite library. The installed user service uses the adjacent
service template. Windows sign-in calls `wsl-session.sh` to start that same service.

After reviewed code changes, run
`systemctl --user restart smartsignalhub-runtime.service`. No export, source copying
or account reset is required. The supervisor lock rejects a second normal launcher.

`expectations.json` and `monitor.py` check the running system. Source mode is
honestly recorded as `WORKING_TREE`, not an immutable verified release. Loaded-code
and effective-config identities remain recorded in the trading DB. Do not edit
running strategy code mid-cycle; make reviewed changes and restart the service.

Native SQLite is in `platform_v2/shared/native/sqlite/`; it is a required library,
not another strategy. Live databases remain in `platform_v2/runtime/database/`.
Restarting must never invoke the reset utility.
