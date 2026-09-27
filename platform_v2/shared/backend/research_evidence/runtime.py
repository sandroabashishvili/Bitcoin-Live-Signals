"""Observer hooks. No trading retries, execution decisions or silent activation.

Recorder failures are fail-open for existing trading, visibly reported to stderr,
and invalidate the attempt's research completeness. Cutover remains a separate gate.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from functools import wraps
import hashlib
import importlib.metadata
import marshal
import os
from pathlib import Path
import socket
import sys
import types
from urllib.parse import parse_qs, urlsplit

from .ledger import Ledger, canonical, now_ms

ACTIVE = ContextVar('research_attempt', default=None)
ORIGIN = ContextVar('research_acquisition_origin', default='CURRENT_FETCH')
ENABLED = os.environ.get('SSH_RESEARCH_EVIDENCE') == '1'
RUNS = {}
SENSITIVE = ('TOKEN', 'PASSWORD', 'SECRET', 'API_KEY', 'CREDENTIAL')


def config_value(value):
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        return {str(k): ('[REDACTED]' if any(t in str(k).upper() for t in SENSITIVE) else config_value(v))
                for k,v in value.items()}
    if isinstance(value,(list,tuple)):
        return [config_value(v) for v in value]
    if value is None or isinstance(value,(str,int,float,bool)):
        return value
    return {'type':type(value).__qualname__}


def provenance():
    """Hash actual loaded code objects; disk source is not claimed as loaded code.

    Functions loaded later and mutable globals are an explicit remaining limitation.
    Config is captured from loaded config modules again for every attempt.
    """
    code = {}
    config = {}
    for name,module in tuple(sys.modules.items()):
        if not name.startswith('platform_v2.') or module is None:
            continue
        for key,value in tuple(vars(module).items()):
            if isinstance(value,types.FunctionType) and value.__module__ == name:
                code[name+'.'+key] = marshal.dumps(value.__code__).hex()
            elif isinstance(value,type) and value.__module__ == name:
                for attr,member in tuple(vars(value).items()):
                    if isinstance(member,(staticmethod,classmethod)):
                        member = member.__func__
                    if isinstance(member,types.FunctionType):
                        code[name+'.'+key+'.'+attr] = marshal.dumps(member.__code__).hex()
        if '.config' in name:
            config[name] = config_value({k:v for k,v in vars(module).items() if k.isupper()})
    return {'loaded_code_objects':code,'effective_config':config,
            'identity_scope':'loaded Python function/method bytecode; NOT a pinned full release',
            'release_verified':False}


@dataclass
class Attempt:
    ledger: Ledger
    run_id: str
    system: str
    attempt_id: str
    cycle_key: str
    input_refs: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def safe(self, operation, *args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except Exception as exc:
            self.errors.append(type(exc).__name__)
            print(f'[research-evidence] {self.system} {self.attempt_id}: {type(exc).__name__}; evidence incomplete',
                  file=sys.stderr, flush=True)
            return None

    def event(self, table, kind, payload, **extra):
        return self.ledger.append(table,run_id=self.run_id,system=self.system,
            attempt_id=self.attempt_id,cycle_key=self.cycle_key,kind=kind,payload=payload,**extra)

    def capture_input(self, identity, rows):
        # Content-addressed chunks avoid duplicating complete series each cycle.
        chunks = self.ledger.blobs([rows[i:i+256] for i in range(0,len(rows),256)])
        ref = self.ledger.blob({'identity':list(identity),'chunks':chunks,'count':len(rows)})
        self.event('research_input_revisions','READ',{'ref':ref,'identity':list(identity),
            'row_count':len(rows),'origin':'OBSERVED_STORED_REVISION',
            'historic_first_seen':'UNKNOWN'})
        if ref not in self.input_refs:
            self.input_refs.append(ref)
        return ref


def observe_input(identity, rows):
    attempt = ACTIVE.get()
    if attempt:
        attempt.safe(attempt.capture_input,identity,rows)


def observe_decision(system, family, row):
    attempt = ACTIVE.get()
    if not attempt or system != attempt.system or family not in ('signals','futures_signals'):
        return
    def record():
        value = row.get('candle_close_time')
        parsed = datetime.fromisoformat(str(value).replace('Z','+00:00')) if value else None
        if parsed is not None and parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        close = int(parsed.timestamp()*1000) if parsed else None
        # Legacy readable timestamps have second precision (xx:xx:59).
        if close is not None and close % 1000 == 0:
            close += 999
        if close is None:
            raise ValueError('missing decision candle close; do not substitute expected slot')
        if not row.get('symbol') or row.get('timeframe') != '15m' or close % 900000 != 899999:
            raise ValueError('invalid decision candle identity')
        cycle = f"{row.get('symbol')}:{row.get('timeframe')}:{close}"
        refs = list(attempt.input_refs)
        for ref in refs:
            manifest = attempt.ledger.load_blob(ref)
            for chunk in manifest['chunks']:
                attempt.ledger.load_blob(chunk)
        attempt.ledger.decision(run_id=attempt.run_id,system=system,attempt_id=attempt.attempt_id,
            cycle_key=cycle,payload=row,input_refs=refs,evidence_complete=not attempt.errors)
    attempt.safe(record)


def observe_acquisition(url, callback):
    attempt = ACTIVE.get()
    if not attempt:
        return callback()
    parsed = urlsplit(url)
    params = parse_qs(parsed.query)
    start = now_ms()
    request_id = attempt.safe(attempt.event,'market_acquisition_events','REQUESTED',
        {'endpoint':parsed.scheme+'://'+parsed.netloc+parsed.path,'params':params,
         'request_ms':start,'origin':ORIGIN.get()})
    try:
        payload = callback()
    except BaseException as exc:
        attempt.safe(attempt.event,'market_acquisition_events','ERROR',
            {'request_id':request_id,'request_ms':start,'response_ms':now_ms(),
             'error_type':type(exc).__name__,'http_status':getattr(exc,'code',None),
             'count':None,'completeness':'FAILED','origin':ORIGIN.get()})
        raise
    def record():
        ref = attempt.ledger.blob(payload)
        count = len(payload) if isinstance(payload,list) else None
        limit = int(params.get('limit',['0'])[0])
        attempt.event('market_acquisition_events','RESPONSE',{
            'request_id':request_id,'request_ms':start,'response_ms':now_ms(),'content_ref':ref,
            'count':count,'origin':ORIGIN.get(),
            'completeness':('POSSIBLY_TRUNCATED' if limit and count is not None and count >= limit
                            else 'UNKNOWN_WINDOW_COVERAGE'),
            'payload_type':type(payload).__name__})
    attempt.safe(record)
    return payload


@contextmanager
def acquisition_origin(origin):
    if origin not in ('CURRENT_FETCH','BACKFILLED'):
        raise ValueError(origin)
    token = ORIGIN.set(origin)
    try:
        yield
    finally:
        ORIGIN.reset(token)


def initialize_run(system):
    """Call explicitly from the loop startup, not retroactively on first decision."""
    if not ENABLED:
        if os.environ.get('SSH_RESEARCH_ATOMIC_SIMULATION') == '1':
            raise RuntimeError('atomic simulation requires evidence activation')
        return None
    key = (os.getpid(),system)
    if key in RUNS:
        return RUNS[key]
    from platform_v2.shared.backend.persistence.database_paths import TRADING_DATABASE_PATH
    ledger = Ledger(TRADING_DATABASE_PATH)
    run_id = os.urandom(16).hex()
    captured = provenance()
    pinned = getattr(sys, '_ssh_pinned_release', None)
    verified = bool(pinned and pinned.get('finder') in sys.meta_path)
    release_ref = ledger.blob(pinned['source_bundle']) if verified else None
    ref = ledger.blob(captured)
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    process_start_ticks = Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]
    ledger.append('research_runs',run_id=run_id,system=system,kind='STARTED',event_key=run_id,
        payload={'startup_capture_ms':now_ms(),'provenance_ref':ref,
            'config_sha256':hashlib.sha256(canonical(captured['effective_config']).encode()).hexdigest(),
            'loaded_code_sha256':hashlib.sha256(canonical(captured['loaded_code_objects']).encode()).hexdigest(),
            'release_verified':verified,'release_source_ref':release_ref,
            'release_sha256':pinned['sha256'] if verified else None,
            'python':sys.version,'executable':sys.executable,
            'dependencies':sorted((d.metadata['Name'],d.version) for d in importlib.metadata.distributions() if d.metadata['Name']),
            'host':socket.gethostname(),'boot_id':boot,'pid':os.getpid(),'process_start_ticks':process_start_ticks,
            'atomic_simulation':os.environ.get('SSH_RESEARCH_ATOMIC_SIMULATION') == '1',
            'backfill':os.environ.get('SSH_RESEARCH_BACKFILL') == '1',
            'activation_close_ms':os.environ.get('SSH_RESEARCH_ACTIVATION_CLOSE_MS')})
    from .recovery import recover_exited
    recover_exited(ledger,run_id,system)
    RUNS[key] = (ledger,run_id)
    import signal
    import threading
    if threading.current_thread() is threading.main_thread():
        def terminate(signum, frame):
            raise SystemExit(0)
        signal.signal(signal.SIGTERM, terminate)
    return ledger,run_id


def recorded_cycle(system):
    def decorate(method):
        @wraps(method)
        def wrapped(self, *args, **kwargs):
            run = RUNS.get((os.getpid(),system))
            # Only explicitly started runtime loops are LIVE observers. Offline tools
            # importing/calling MainCycleService cannot silently create LIVE evidence.
            if not run:
                return method(self,*args,**kwargs)
            ledger,run_id = run
            profile = kwargs.get('profile')
            symbol = getattr(profile,'symbol',kwargs.get('symbol','BTCUSDT'))
            timeframe = getattr(profile,'timeframe',kwargs.get('timeframe','15m'))
            if timeframe != '15m':
                raise ValueError('R2 recorder supports the audited 15m schedule only')
            try:
                attempt_id,cycle = ledger.start(run_id=run_id,system=system,symbol=symbol,timeframe=timeframe)
                attempt = Attempt(ledger,run_id,system,attempt_id,cycle)
            except Exception as exc:
                print(f'[research-evidence] STARTED failed: {type(exc).__name__}; collection invalid',file=sys.stderr,flush=True)
                if os.environ.get('SSH_RESEARCH_ATOMIC_SIMULATION') == '1':
                    raise RuntimeError('atomic simulation requires durable STARTED') from exc
                return method(self,*args,**kwargs)
            token = ACTIVE.set(attempt)
            # Explicit activation boundary prevents relabelling legacy/pre-recorder gaps.
            activation = os.environ.get('SSH_RESEARCH_ACTIVATION_CLOSE_MS')
            if activation:
                attempt.safe(lambda: ledger.detect_gaps(run_id=run_id,system=system,symbol=symbol,
                    timeframe=timeframe,activation_close_ms=int(activation),
                    through_close_ms=now_ms()//900000*900000-900001))
            attempt.safe(lambda: attempt.event('cycle_attempt_events','CONFIG',
                         {'arguments':config_value(kwargs),'loaded_config':provenance()['effective_config']}))
            try:
                result = method(self,*args,**kwargs)
            except BaseException as exc:
                attempt.safe(ledger.terminal,run_id=run_id,system=system,attempt_id=attempt_id,cycle_key=cycle,
                    kind='INTERRUPTED' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'FAILED',
                    payload={'error_type':type(exc).__name__,'recorder_errors':attempt.errors,
                             'side_effects':'UNKNOWN_REQUIRES_RECONCILIATION'})
                raise
            else:
                attempt.safe(ledger.terminal,run_id=run_id,system=system,attempt_id=attempt_id,cycle_key=cycle,
                    kind='COMMITTED',payload={'skipped':bool(getattr(result,'skipped',False)),
                        'skip_reason':getattr(result,'skip_reason',None),
                        'actual_cycle_key':getattr(result,'cycle_key',None),
                        'recorder_errors':attempt.errors,
                        'meaning':'main cycle returned; NOT atomic execution commit'})
                return result
            finally:
                ACTIVE.reset(token)
        return wrapped
    return decorate


def recorded_read(category):
    """Capture the exact returned runtime/fallback value, including absent inputs."""
    def decorate(method):
        @wraps(method)
        def wrapped(*args,**kwargs):
            result=method(*args,**kwargs)
            if ACTIVE.get():
                observe_input((category,canonical(config_value(kwargs))),[result])
            return result
        return wrapped
    return decorate
