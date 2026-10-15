"""Predeclared LONG MOMENTUM ablations: directional RSI or positive MACD."""
import ast
import gzip
import json
from pathlib import Path
from platform_v2.tools.research import signal_lab as lab

COMPONENT='platform_v2/spot/services/signal/long_component_score_service.py'
MTF='platform_v2/spot/services/signal/mtf_context_service.py'
RULES={
    'rsi_direction':'Replace only LONG RSI ladder with +1.4 for RSI>50, else zero. Includes RSI>=72; RSI=50 abstains. Existing MACD award/check and disabled histogram remain unchanged.',
    'macd_positive':'Add MACD>0 to the existing LONG MACD>=signal and nonmissing values condition. Existing RSI ladder and disabled histogram remain unchanged. Equality with signal is still allowed if MACD>0.',
}


def candidate_source(source,variant):
    if variant not in RULES:raise ValueError('Unsupported MOMENTUM variant')
    tree=ast.parse(source)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='SpotLongComponentScoreService')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='long_momentum_score')
    checks=[n for n in method.body if isinstance(n,ast.If)]
    if len(checks)!=3 or ast.unparse(checks[0].test)!='snapshot.rsi is not None':
        raise ValueError('Unexpected LONG MOMENTUM structure')
    if variant=='rsi_direction':
        expected=ast.parse('''if 52.0 <= snapshot.rsi < 58.0:
    score += 1.0
elif 58.0 <= snapshot.rsi < 65.0:
    score += 1.4
elif 65.0 <= snapshot.rsi < 72.0:
    score += 0.8
elif 50.0 <= snapshot.rsi < 52.0:
    score += 0.5
''').body
        if ast.dump(ast.Module(body=checks[0].body,type_ignores=[]))!=ast.dump(ast.Module(body=expected,type_ignores=[])):
            raise ValueError('Unexpected RSI point ladder')
        checks[0].body=ast.parse('if snapshot.rsi > 50.0:\n    score += 1.4').body
    else:
        expected=ast.parse('snapshot.macd is not None and snapshot.macd_signal is not None and snapshot.macd >= snapshot.macd_signal',mode='eval').body
        if ast.dump(checks[1].test)!=ast.dump(expected):raise ValueError('Unexpected MACD condition')
        checks[1].test.values.append(ast.parse('snapshot.macd > 0.0',mode='eval').body)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)+'\n'


def prepare(workspace):
    root=lab.outside_live(workspace);lab.verify(root)
    payload=json.loads(gzip.decompress((root/'source/source.json.gz').read_bytes()))
    settings=payload['files']['platform_v2/spot/config/long_strategy_settings.py']
    if 'MACD_HISTOGRAM_SIGNAL_ENABLED = False' not in settings:
        raise ValueError('Study requires pinned histogram disabled')
    for variant,rules in RULES.items():
        code=candidate_source(payload['files'][COMPONENT],variant)
        for use_mtf in (False,True):
            name=('mtf_' if use_mtf else '')+f'momentum_{variant}_v1'
            folder=root/'spot_candidates'/name;folder.mkdir(parents=True,exist_ok=False)
            (folder/'component.py').write_text(code)
            overlays={COMPONENT:{'file':'component.py','sha256':lab.digest(folder/'component.py')}}
            components=['momentum']
            if use_mtf:
                mtf=root/'spot_candidates/symmetric_all/mtf.py'
                declaration=json.loads((mtf.parent/'protocol.json').read_text())
                if lab.digest(mtf)!=declaration['source_sha256']:raise ValueError('MTF hash mismatch')
                (folder/'mtf.py').write_bytes(mtf.read_bytes())
                overlays[MTF]={'file':'mtf.py','sha256':lab.digest(folder/'mtf.py')}
                components.append('mtf')
            lab.write(folder/'protocol.json',{'variant':name,'components':components,'overlays':overlays,'rules':rules,
                'reference':'symmetric_all' if use_mtf else 'baseline-next-minute',
                'unchanged':'Opposing MOMENTUM and other five components including original TREND/REGIME, weights, thresholds, disabled histogram, all filters including proximity, fees, size and native management.',
                'selection':'Four variants fixed before replay on same reused exploratory period. Not independent validation.',
                'source_market':'spot','live_changes':False,'pinned_archive_sha256':lab.digest(root/'source/source.json.gz')})
    return root/'spot_candidates'


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('workspace',type=Path)
    print(prepare(p.parse_args().workspace))
