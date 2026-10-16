"""Predeclared LONG STRUCTURE ablations; captured inputs and live rules unchanged."""
import ast
import gzip
import json
from pathlib import Path
from platform_v2.tools.research import signal_lab as lab

STRUCTURE='platform_v2/spot/services/signal/long_structure_score_service.py'
MTF='platform_v2/spot/services/signal/mtf_context_service.py'
RULES={
    'room':'Only LONG headroom >=1.5 ATR receives the same +0.8 as 1–1.5 ATR, instead of +0.1. Lower-room bands remain original.',
    'distance':'Only LONG distance ladder becomes: [1,1.5):0.8; [1.5,2.5):1.0; [2.5,4):0.5; [4,6):0.2; otherwise zero. Peak unchanged at 1.0.',
    'combined':'Apply exactly the room and distance ablations together. No additional changes.',
}


def _ladder_points(node):
    values=[]
    while isinstance(node,ast.If):
        if len(node.body)!=1 or not isinstance(node.body[0],ast.AugAssign):raise ValueError('Unexpected STRUCTURE award')
        award=node.body[0]
        value=ast.literal_eval(award.value)
        values.append(-value if isinstance(award.op,ast.Sub) else value)
        node=node.orelse[0] if len(node.orelse)==1 else None
    return values


def candidate_source(source,variant):
    if variant not in RULES:raise ValueError('Unsupported STRUCTURE variant')
    tree=ast.parse(source)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SpotLongStructureScoreService')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='long_score')
    checks=[n for n in method.body if isinstance(n,ast.If)]
    if (len(checks)!=5 or ast.unparse(checks[0].test)!='atr_spike_block'
            or _ladder_points(checks[2])!=[1.0,.8,.2,.1]
            or _ladder_points(checks[3])!=[.8,.1,-.8,.1]):
        raise ValueError('Unexpected STRUCTURE schedule')
    if variant in ('room','combined'):
        last=checks[3]
        while last.orelse:last=last.orelse[0]
        last.body[0].value=ast.Constant(value=.8)
    if variant in ('distance','combined'):
        replacement=ast.parse('''
if 1.0 <= distance_from_low_atr < 1.5:
    score += 0.8
elif 1.5 <= distance_from_low_atr < 2.5:
    score += 1.0
elif 2.5 <= distance_from_low_atr < 4.0:
    score += 0.5
elif 4.0 <= distance_from_low_atr < 6.0:
    score += 0.2
''').body[0]
        method.body[method.body.index(checks[2])]=replacement
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)+'\n'


def prepare(workspace):
    root=lab.outside_live(workspace);lab.verify(root)
    validation=json.loads((root/'orderbook_input_validation.json').read_text())
    if not validation['all_raw_pages_verified']:raise ValueError('Unverified corrected-input cohort')
    payload=json.loads(gzip.decompress((root/'source/source.json.gz').read_bytes()))
    for variant,rule in RULES.items():
        code=candidate_source(payload['files'][STRUCTURE],variant)
        for use_mtf in (False,True):
            name=('mtf_' if use_mtf else '')+f'structure_{variant}_v1'
            folder=root/'spot_candidates'/name;folder.mkdir(parents=True,exist_ok=False)
            (folder/'structure.py').write_text(code)
            overlays={STRUCTURE:{'file':'structure.py','sha256':lab.digest(folder/'structure.py')}}
            if use_mtf:
                mtf=root/'spot_candidates/symmetric_all/mtf.py'
                declaration=json.loads((mtf.parent/'protocol.json').read_text())
                if lab.digest(mtf)!=declaration['source_sha256']:raise ValueError('MTF hash mismatch')
                (folder/'mtf.py').write_bytes(mtf.read_bytes())
                overlays[MTF]={'file':'mtf.py','sha256':lab.digest(folder/'mtf.py')}
            lab.write(folder/'protocol.json',{'variant':name,'overlays':overlays,'components':['structure']+(['mtf'] if use_mtf else []),
                'rules':rule,'reference':'symmetric_all' if use_mtf else 'baseline-next-minute',
                'selection':'Three variants declared before replay on the same 135 corrected-input cycles. Exploratory, reused period, no holdout.',
                'unchanged':'Opposing SHORT structure, ATR-spike block, missing-input guard, bounce bonus, clipping, other components apart from declared MTF, weights, thresholds, all filters, fees, sizing and native exits.',
                'source_market':'spot','live_changes':False,'pinned_archive_sha256':lab.digest(root/'source/source.json.gz')})
    return root/'spot_candidates'


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('workspace',type=Path)
    print(prepare(p.parse_args().workspace))
