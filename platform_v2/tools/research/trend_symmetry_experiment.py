"""Research-only Spot TREND ablation; never patches production source."""
import ast
import gzip
import json
from pathlib import Path

from platform_v2.tools.research import signal_lab as lab

COMPONENT = 'platform_v2/spot/services/signal/long_component_score_service.py'


def candidate_source(source):
    """Keep LONG and every condition intact; mirror its weights onto SHORT."""
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SpotLongComponentScoreService')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'short_trend_score')
    additions = sorted((n for n in ast.walk(method) if isinstance(n, ast.AugAssign)
                        and isinstance(n.target, ast.Name) and n.target.id == 'score'), key=lambda n:n.lineno)
    if len(additions) != 4 or any(not isinstance(n.value, ast.Constant) or n.value.value != 1.0 for n in additions):
        raise ValueError('Unexpected pinned SHORT TREND formula')
    lines = source.splitlines(keepends=True)
    for node, weight in zip(additions, (0.7, 0.8, 0.8, 0.8)):
        line = lines[node.lineno-1]
        lines[node.lineno-1] = line[:node.col_offset] + f'score += {weight}' + line[node.end_col_offset:]
    code = ''.join(lines)
    ast.parse(code)
    return code


def prepare(workspace):
    root = lab.outside_live(workspace)
    lab.verify(root)
    payload = json.loads(gzip.decompress((root/'source/source.json.gz').read_bytes()))
    code = candidate_source(payload['files'][COMPONENT])
    for name, components in [('trend_mirror_v1', ['trend']), ('mtf_trend_mirror_v1', ['mtf', 'trend'])]:
        folder = root/'spot_candidates'/name
        folder.mkdir(parents=True, exist_ok=False)
        (folder/'component.py').write_text(code)
        overlays = {COMPONENT: {'file':'component.py', 'sha256':lab.digest(folder/'component.py')}}
        if 'mtf' in components:
            mtf = root/'spot_candidates/symmetric_all/mtf.py'
            protocol = json.loads((mtf.parent/'protocol.json').read_text())
            if lab.digest(mtf) != protocol['source_sha256']:
                raise ValueError('MTF candidate hash mismatch')
            (folder/'mtf.py').write_bytes(mtf.read_bytes())
            overlays['platform_v2/spot/services/signal/mtf_context_service.py'] = {'file':'mtf.py', 'sha256':lab.digest(folder/'mtf.py')}
        lab.write(folder/'protocol.json', {'variant':name, 'source_market':'spot', 'components':components,
            'overlays':overlays, 'pinned_source_sha256':lab.digest(root/'source/source.json.gz'),
            'rules':'SHORT TREND weights 1/1/1/1 become 0.7/0.8/0.8/0.8, matching unchanged LONG. Conditions, thresholds, global weight and all management unchanged.',
            'hypothesis':'Does unequal directional weighting suppress useful BUY signals?',
            'selection':'Predeclared two-variant ablation; reused exploratory period, not independent validation',
            'live_changes':False})
    return root/'spot_candidates'


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', type=Path)
    print(prepare(parser.parse_args().workspace))
