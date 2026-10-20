"""Small shared utilities for the single supported offline Spot backtest."""
import hashlib
import json
from pathlib import Path
import subprocess

LIVE = Path(__file__).resolve().parents[3] / 'runtime'


def digest(path):
    checksum = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False)+'\n')


def outside_live(path):
    path = Path(path).expanduser().resolve()
    if path == LIVE or path.is_relative_to(LIVE) or LIVE.is_relative_to(path):
        raise ValueError('Research destination must be separate from live runtime')
    return path


def launch_recorded(command, output):
    with (output/'console.log').open('x') as log:
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as process:
            for line in process.stdout:
                log.write(line)
                log.flush()
                print(line, end='', flush=True)
            return process.wait()
