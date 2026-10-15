"""Bounded REGIME study: one point ablation and one shared-strength model."""
import ast
import gzip
import json
from pathlib import Path
from platform_v2.tools.research import signal_lab as lab

COMPONENT='platform_v2/spot/services/signal/long_component_score_service.py'
MTF='platform_v2/spot/services/signal/mtf_context_service.py'
RULES={
    'monotonic':'LONG ADX base awards for 25<=ADX<30 and ADX>=30 become 1.6, matching the existing 20<=ADX<25 award. All DI/slope/ATR adjustments and opposing REGIME unchanged.',
    'strength':'LONG REGIME uses the existing opposing direction-neutral strength helper: 0 if ATR spike or missing ADX; 2 if ADX>=20, 1 if ADX>=18, else 0.5. Removes LONG-only DI/slope/ATR-growth shaping and changes LONG spike penalty into the existing hard-zero policy.',
}


def candidate_source(source,variant):
    if variant not in RULES:raise ValueError('Unsupported REGIME variant')
    tree=ast.parse(source)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SpotLongComponentScoreService')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='long_regime_score')
    if variant=='monotonic':
        targets=[n for n in ast.walk(method) if isinstance(n,ast.If) and ast.unparse(n.test)=='adx < 30.0']
        if len(targets)!=1:raise ValueError('Unexpected ADX base schedule')
        node=targets[0]
        if len(node.body)!=1 or len(node.orelse)!=1:raise ValueError('Unexpected ADX awards')
        for statement,expected in zip((node.body[0],node.orelse[0]),(.7,1.1)):
            if not isinstance(statement,ast.AugAssign) or ast.unparse(statement.target)!='score' or not isinstance(statement.value,ast.Constant) or statement.value.value!=expected:
                raise ValueError('Unexpected high-ADX point values')
            statement.value=ast.Constant(value=1.6)
    else:
        shared=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='regime_score')
        expected=ast.parse('''def regime_score(snapshot, *, atr_spike_block: bool) -> float:
    if atr_spike_block:
        return 0.0
    if snapshot.adx is None:
        return 0.0
    if snapshot.adx >= settings.REGIME_ADX_MIN:
        return 2.0
    if snapshot.adx >= (settings.REGIME_ADX_MIN - 2.0):
        return 1.0
    return 0.5
''').body[0]
        if ast.dump(ast.Module(body=shared.body,type_ignores=[]))!=ast.dump(ast.Module(body=expected.body,type_ignores=[])):
            raise ValueError('Unexpected shared REGIME strength helper')
        method.body=ast.parse('return SpotLongComponentScoreService.regime_score(snapshot, atr_spike_block=atr_spike_block)').body
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)+'\n'


def prepare(workspace):
    root=lab.outside_live(workspace);lab.verify(root)
    payload=json.loads(gzip.decompress((root/'source/source.json.gz').read_bytes()))
    for variant,rules in RULES.items():
        code=candidate_source(payload['files'][COMPONENT],variant)
        for use_mtf in (False,True):
            name=('mtf_' if use_mtf else '')+f'regime_{variant}_v1'
            folder=root/'spot_candidates'/name;folder.mkdir(parents=True,exist_ok=False)
            (folder/'component.py').write_text(code)
            overlays={COMPONENT:{'file':'component.py','sha256':lab.digest(folder/'component.py')}}
            components=['regime']
            if use_mtf:
                mtf=root/'spot_candidates/symmetric_all/mtf.py'
                declaration=json.loads((mtf.parent/'protocol.json').read_text())
                if lab.digest(mtf)!=declaration['source_sha256']:raise ValueError('MTF hash mismatch')
                (folder/'mtf.py').write_bytes(mtf.read_bytes())
                overlays[MTF]={'file':'mtf.py','sha256':lab.digest(folder/'mtf.py')}
                components.append('mtf')
            lab.write(folder/'protocol.json',{'variant':name,'components':components,'overlays':overlays,
                'rules':rules,'reference':'symmetric_all' if use_mtf else 'baseline-next-minute',
                'unchanged':'Other five component rules (including original TREND), global weights/thresholds, all permission filters (including proximity), position management, fees and size.',
                'selection':'Four variants declared before this experiment; same previously reused exploratory period, not independent validation.',
                'caveat':'strength is a whole LONG REGIME replacement, not an isolated causal test of each removed term.',
                'source_market':'spot','live_changes':False,'pinned_archive_sha256':lab.digest(root/'source/source.json.gz')})
    return root/'spot_candidates'


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace',type=Path)
    print(prepare(parser.parse_args().workspace))
