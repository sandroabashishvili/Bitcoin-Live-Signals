from pathlib import Path
import subprocess
import sys
import pytest
from .release import build


def test_pinned_source_survives_disk_edit_and_rejects_new_import(tmp_path):
    root=tmp_path/'project';package=root/'platform_v2';package.mkdir(parents=True)
    (package/'__init__.py').write_text('')
    (package/'value.py').write_text('VALUE="original"\n')
    (package/'probe.py').write_text('''
from .value import VALUE
print(VALUE)
try:
 import platform_v2.injected
except ModuleNotFoundError:
 print('BLOCKED')
''')
    release,digest=build(root,tmp_path/'releases')
    (package/'value.py').write_text('VALUE="changed"\n')
    (package/'injected.py').write_text('raise RuntimeError("must not run")\n')
    command=[sys.executable,str(release/'run.py'),'--release',str(release/'source.json.gz'),'--sha256',digest,'--module','platform_v2.probe']
    result=subprocess.run(command,text=True,capture_output=True)
    assert result.returncode==0,result.stderr
    assert result.stdout=='original\nBLOCKED\n'
    command[command.index('--sha256')+1]='bad'
    result=subprocess.run(command,text=True,capture_output=True)
    assert result.returncode!=0 and 'release hash mismatch' in result.stderr
    # pytest cleanup needs write permissions restored on this temporary fixture.
    release.chmod(0o755)
    for p in release.iterdir():p.chmod(0o644)
