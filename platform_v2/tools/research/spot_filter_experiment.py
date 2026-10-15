"""Isolated proximity-filter ablation; frozen research only."""
import ast
import gzip
import json
from pathlib import Path
from platform_v2.tools.research import signal_lab as lab

PERMISSION = 'platform_v2/spot/services/permission/permission_decision_service.py'
MTF = 'platform_v2/spot/services/signal/mtf_context_service.py'


def candidate_source(source):
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'PermissionDecisionService')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_passes_proximity')
    if not any(isinstance(n, ast.Name) and n.id == 'distance_pct' for n in ast.walk(method)):
        raise ValueError('Unexpected proximity formula')
    lines = source.splitlines(keepends=True)
    first, last = method.body[0].lineno, method.end_lineno
    return ''.join(lines[:first-1] + ['        return True  # Research-only proximity ablation\n'] + lines[last:])


def prepare(workspace):
    root = lab.outside_live(workspace)
    lab.verify(root)
    payload = json.loads(gzip.decompress((root/'source/source.json.gz').read_bytes()))
    code = candidate_source(payload['files'][PERMISSION])
    for name, use_mtf in [('proximity_off_v1',False), ('mtf_proximity_off_v1',True)]:
        folder = root/'spot_candidates'/name
        folder.mkdir(parents=True, exist_ok=False)
        (folder/'permission.py').write_text(code)
        overlays = {PERMISSION:{'file':'permission.py','sha256':lab.digest(folder/'permission.py')}}
        components = ['permission_proximity']
        if use_mtf:
            mtf = root/'spot_candidates/symmetric_all/mtf.py'
            declared = json.loads((mtf.parent/'protocol.json').read_text())
            if lab.digest(mtf) != declared['source_sha256']:raise ValueError('MTF hash mismatch')
            (folder/'mtf.py').write_bytes(mtf.read_bytes())
            overlays[MTF] = {'file':'mtf.py','sha256':lab.digest(folder/'mtf.py')}
            components.append('mtf')
        lab.write(folder/'protocol.json',{'variant':name,'components':components,'overlays':overlays,
            'rules':'Disable only proximity permission check; signal rules, all other filters, capital, exits, size, fees unchanged.',
            'selection':'Exploratory choice after descriptive audit on reused period. Not independent validation.',
            'source_market':'spot','live_changes':False})
    return root/'spot_candidates'


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('workspace',type=Path)
    print(prepare(p.parse_args().workspace))
