"""Conservative local-process recovery. Never infer shutdown from missing candles."""
import json
from pathlib import Path
import socket


def exit_evidence(payload):
    if payload.get('host') != socket.gethostname():
        return None
    try:
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        if payload.get('boot_id') != boot:
            return {'process_exit_confirmed':True,'basis':'different_host_boot_id','observed_boot_id':boot}
        try:
            stat = Path(f"/proc/{int(payload['pid'])}/stat").read_text()
        except FileNotFoundError:
            return {'process_exit_confirmed':True,'basis':'pid_absent_same_host_boot'}
        ticks = stat.rsplit(')',1)[1].split()[19]
        if str(payload.get('process_start_ticks')) != ticks:
            return {'process_exit_confirmed':True,'basis':'pid_reused_same_host_boot'}
    except (OSError,ValueError,KeyError,IndexError):
        pass
    return None


def recover_exited(ledger, run_id, system):
    with ledger.connection() as db:
        runs = db.execute('SELECT run_id,payload_json FROM research_runs WHERE system=? AND run_id<>?',(system,run_id)).fetchall()
    count=0
    for row in runs:
        proof = exit_evidence(json.loads(row['payload_json']))
        if proof:
            count += ledger.recover(dead_run_id=row['run_id'],recovery_run_id=run_id,system=system,evidence=proof)
    return count
