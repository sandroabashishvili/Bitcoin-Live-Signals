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

The health cron must enter the project root before using `python -m`; cron
otherwise starts in the user's home, where `platform_v2` cannot be imported.
Keep stderr in a local log so launcher errors are not discarded by cron:

```cron
5,20,35,50 * * * * cd /home/sandro/SmartSignalHub && /usr/bin/flock -n /home/sandro/SmartSignalHub/platform_v2/runtime/research-monitor.lock /usr/bin/env PYTHONDONTWRITEBYTECODE=1 LD_LIBRARY_PATH=/home/sandro/SmartSignalHub/platform_v2/shared/native/sqlite /home/sandro/SmartSignalHub/venv/bin/python -m platform_v2.tools.runtime_start_system.monitor >> /home/sandro/SmartSignalHub/platform_v2/runtime/logs/tools/runtime_monitor.log 2>&1
```

Health details are in `platform_v2/runtime/research_health/latest.json` and the
bounded daily JSONL history. A nonzero exit can mean a reported health warning,
not a launcher failure; read `latest.json` before diagnosing the exit code.

Native SQLite is in `platform_v2/shared/native/sqlite/`; it is a required library,
not another strategy. Live databases remain in `platform_v2/runtime/database/`.
Restarting must never invoke the reset utility.

Spot and Futures orderflow reads use the shared public HTTP client: at most
three attempts per page, with 1s/2s backoff and Binance `Retry-After` respected.
Retries keep the same closed window/cursor and share the existing 120s
collection budget. Each request uses at most 15s (less when the budget is low);
socket timeouts are not hard wall-clock cancellation, so late responses are
also rejected. Incomplete collections never publish a snapshot or a decision.
Historical missed decisions remain missing; a restart does not reconstruct them.
