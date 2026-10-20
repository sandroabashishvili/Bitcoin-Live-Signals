# SmartSignalHub — prepared service operation

Checkpoint: 2026-09-28. **Service enabled and active.** Old terminal parent and
children stopped cleanly. Linger enabled. Windows task SmartSignalHub-WSL registered
and its action tested; local cron installed. Activation started 06:00:10 UTC
(08:00:10 Europe/Berlin), first collection candle 05:59:59.999 UTC.
Two controlled service restarts skipped already committed cycles. Live monitor
reports no issues. A real Windows reboot/sign-in test is still pending; overall
long-run signoff remains NOT_READY until that acceptance and continued cycles.

## Monitoring schedule

Installed cron: minute 05, 20, 35 and 50 every hour. This leaves approximately four
minutes after the normal xx:01/16/31/46 cycle start. No existing cron entry is
replaced. The check uses its own nonblocking lock and pinned Python source.

## Commands to use now

In Ubuntu/WSL:

```bash
# State
systemctl --user status smartsignalhub-runtime.service --no-pager

# Current cycle logs; Ctrl+C exits the viewer only
journalctl --user -u smartsignalhub-runtime.service -f

# Last 100 log lines
journalctl --user -u smartsignalhub-runtime.service -n 100 --no-pager

# Intentional stop (systemd will not restart an explicitly stopped service)
systemctl --user stop smartsignalhub-runtime.service

# Start the same service; repeated start requests do not create extra copies
systemctl --user start smartsignalhub-runtime.service

# Controlled restart
systemctl --user restart smartsignalhub-runtime.service

# Latest independent monitor result, after cron is enabled
cat ~/SmartSignalHub/platform_v2/runtime/research_health/latest.json
```

Do not also run the old `python3 -m platform_v2.tools.runtime_start_system` command.
The service owns one parent with Spot, Futures and Telegram children. Closing a
log viewer does not stop them. A machine reboot terminates old processes; it does
not accumulate copies. Windows startup is at current-user sign-in, not before
sign-in. The prepared Windows task uses IgnoreNew, and its WSL keeper has a lock.

## Remaining acceptance

Close the old, now-idle terminal if desired. Do not run the legacy runtime command.
After a real Windows reboot and sign-in, open Ubuntu and check service status and
journal with the commands above. Keep the host on for the next 15-minute cycle,
then inspect research_health/latest.json. The service and Windows task should each
have only one active instance. Report failures rather than starting a legacy copy.

Windows logon task can be inspected in Task Scheduler as SmartSignalHub-WSL.
It starts Ubuntu under sandro and holds one sleeping WSL session. It does not
start before Windows sign-in. Intentional service stop remains stopped during the
same session; an enabled service starts again on the next manager boot/sign-in.

The monitor automatically selects the latest manifest covering all three DBs
under ~/backups/smartsignalhub, including subsequent manual full backups when the
listed DB files exist. It checks manifest age/coverage, not a full restore on each
invocation. Backups remain manual. Keep release/library directories referenced by
activation.json. Final activation evidence and remaining reboot acceptance:
/home/sandro/research_snapshots/readiness_R21_20260928/REPORT.md
