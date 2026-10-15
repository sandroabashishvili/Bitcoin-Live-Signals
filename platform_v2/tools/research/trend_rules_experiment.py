"""Two predeclared TREND predicate ablations, on pinned Spot and MTF context."""
import ast
import gzip
import json
from pathlib import Path
from platform_v2.tools.research import signal_lab as lab

COMPONENT = 'platform_v2/spot/services/signal/long_component_score_service.py'
MTF = 'platform_v2/spot/services/signal/mtf_context_service.py'
RULES = {
    'alignment': 'EMA50/EMA200 alignment earns its existing points independently of price relative to EMA50; price check retains its separate points.',
    'dmi': 'DI direction earns its existing points without requiring nonmissing ADX or ADX>=20; REGIME and all other checks remain unchanged.',
}


def candidate_source(source, variant):
    if variant not in RULES:raise ValueError('Unsupported TREND predicate variant')
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name=='SpotLongComponentScoreService')
    for name, operator in [('long_trend_score','>'),('short_trend_score','<')]:
        method = next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name)
        checks = [n for n in method.body if isinstance(n,ast.If)]
        if len(checks)!=4:raise ValueError('Unexpected TREND predicate count')
        test = checks[1 if variant=='alignment' else 3].test
        if not isinstance(test,ast.BoolOp) or not isinstance(test.op,ast.And):
            raise ValueError('Unexpected TREND predicate shape')
        if variant=='alignment':
            if len(test.values)!=4 or ast.unparse(test.values[-1])!=f'price {operator} snapshot.ema50':
                raise ValueError('Unexpected EMA price dependency')
            test.values = test.values[:-1]
        else:
            if len(test.values)!=5 or ast.unparse(test.values[0])!='snapshot.adx is not None' or ast.unparse(test.values[3])!='snapshot.adx >= settings.REGIME_ADX_MIN':
                raise ValueError('Unexpected DI ADX dependency')
            test.values = [test.values[i] for i in (1,2,4)]
    return ast.unparse(tree)+'\n'


def prepare(workspace):
    root=lab.outside_live(workspace)
    lab.verify(root)
    payload=json.loads(gzip.decompress((root/'source/source.json.gz').read_bytes()))
    for variant,rules in RULES.items():
        code=candidate_source(payload['files'][COMPONENT],variant)
        for use_mtf in (False,True):
            name=('mtf_' if use_mtf else '')+f'trend_{variant}_v1'
            folder=root/'spot_candidates'/name
            folder.mkdir(parents=True,exist_ok=False)
            (folder/'component.py').write_text(code)
            overlays={COMPONENT:{'file':'component.py','sha256':lab.digest(folder/'component.py')}}
            components=['trend']
            if use_mtf:
                mtf=root/'spot_candidates/symmetric_all/mtf.py'
                declaration=json.loads((mtf.parent/'protocol.json').read_text())
                if lab.digest(mtf)!=declaration['source_sha256']:raise ValueError('MTF hash mismatch')
                (folder/'mtf.py').write_bytes(mtf.read_bytes())
                overlays[MTF]={'file':'mtf.py','sha256':lab.digest(folder/'mtf.py')}
                components.append('mtf')
            lab.write(folder/'protocol.json',{'variant':name,'components':components,'overlays':overlays,
                'rules':rules,'source_market':'spot','live_changes':False,
                'reference':'symmetric_all' if use_mtf else 'baseline-next-minute',
                'unchanged':'Original directional point awards (LONG max3.1 / SHORT max4), global weights, thresholds, other five components, all permissions/management.',
                'selection':'Four variants fixed before this experiment; previously reused exploratory period, not independent validation.',
                'pinned_archive_sha256':lab.digest(root/'source/source.json.gz')})
    return root/'spot_candidates'


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace',type=Path)
    print(prepare(parser.parse_args().workspace))
