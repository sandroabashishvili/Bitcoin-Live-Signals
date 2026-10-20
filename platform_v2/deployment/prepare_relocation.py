"""One-time preparation of the existing operational snapshot, without a restart.

Copies only the selected release, SQLite runtime, and deployment files. Existing
targets are rejected. The old deployment is kept intact for rollback.
"""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

OLD = Path('/home/sandro/research_snapshots/readiness_R21_20260927')
NEW = Path(__file__).resolve().parent
UNIT = Path('/home/sandro/.config/systemd/user/smartsignalhub-runtime.service')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    activation = json.loads((OLD/'deploy/activation.json').read_text())
    release = Path(activation['release'])
    expected = activation['release_sha256']
    assert release.parent == OLD/'releases'
    assert hashlib.sha256(gzip.decompress((release/'source.json.gz').read_bytes())).hexdigest() == expected
    assert sha(Path(activation['sqlite_library'])) == activation['sqlite_library_sha256']
    for name in ('deploy', 'releases', 'sqlite', 'migration'):
        if (NEW/name).exists():
            raise RuntimeError('Already exists: '+str(NEW/name))
    evidence = NEW/'migration'
    evidence.mkdir()
    shutil.copy2(UNIT, evidence/'service.before')
    cron = subprocess.check_output(['crontab', '-l'], text=True)
    (evidence/'crontab.before').write_text(cron)
    shutil.copytree(OLD/'deploy', NEW/'deploy', ignore=shutil.ignore_patterns('__pycache__'))
    (NEW/'releases').mkdir()
    shutil.copytree(release, NEW/'releases'/release.name)
    (NEW/'sqlite').mkdir()
    for name in ('libsqlite3.so.0', 'verification.json'):
        shutil.copy2(OLD/'sqlite'/name, NEW/'sqlite'/name)
    # Mechanical path relocation only. Never rewrite the immutable source bundle.
    for path in (NEW/'deploy').iterdir():
        if path.is_file():
            path.write_text(path.read_text().replace(str(OLD), str(NEW)))
    unit = UNIT.read_text().replace(str(OLD), str(NEW))
    unit = unit.replace('# Prepared user service; NOT installed or enabled.',
                        '# Operational user service; managed configuration in platform_v2/deployment.')
    (evidence/'service.after').write_text(unit)
    (evidence/'crontab.after').write_text(cron.replace(str(OLD), str(NEW)))
    updated = json.loads((NEW/'deploy/activation.json').read_text())
    for key in activation:
        if key not in ('release', 'sqlite_library'):
            assert updated[key] == activation[key], key
    assert sha(NEW/'sqlite/libsqlite3.so.0') == activation['sqlite_library_sha256']
    for path in release.iterdir():
        assert sha(path) == sha(NEW/'releases'/release.name/path.name)
    manifest = {'old_root': str(OLD), 'new_root': str(NEW),
                'release_sha256': expected, 'activation_close_ms': activation['activation_close_ms'],
                'state': 'PREPARED_NOT_SWITCHED',
                'preserved_files': {str(p.relative_to(NEW)): sha(p)
                    for folder in ('releases', 'sqlite') for p in (NEW/folder).rglob('*') if p.is_file()}}
    (evidence/'preparation.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
