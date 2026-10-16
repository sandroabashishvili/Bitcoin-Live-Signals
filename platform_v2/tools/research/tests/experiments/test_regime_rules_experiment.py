import ast
from types import SimpleNamespace
import pytest
from platform_v2.tools.research.regime_rules_experiment import candidate_source
from platform_v2.spot.services.signal.long_component_score_service import SpotLongComponentScoreService as Original

from platform_v2.tools.research.tests.paths import PLATFORM_ROOT

SOURCE = PLATFORM_ROOT / 'spot/services/signal/long_component_score_service.py'


def candidate(variant):
    namespace={};exec(candidate_source(SOURCE.read_text(),variant),namespace)
    return namespace['SpotLongComponentScoreService']


def snapshot(adx,**overrides):
    result=dict(adx=adx,plus_di=None,minus_di=None,adx_slope=None,atr_growth_20=None)
    result.update(overrides)
    return SimpleNamespace(**result)


@pytest.mark.parametrize('variant',['monotonic','strength'])
def test_no_other_method_changes(variant):
    trees=[ast.parse(SOURCE.read_text()),ast.parse(candidate_source(SOURCE.read_text(),variant))]
    for tree in trees:
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='long_regime_score')
        method.body=[ast.Pass()]
    assert ast.dump(trees[0])==ast.dump(trees[1])


def test_monotonic_changes_only_two_original_base_constants():
    trees=[ast.parse(SOURCE.read_text()),ast.parse(candidate_source(SOURCE.read_text(),'monotonic'))]
    for tree in trees:
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='long_regime_score')
        node=next(n for n in ast.walk(method) if isinstance(n,ast.If) and ast.unparse(n.test)=='adx < 30.0')
        node.body[0].value=ast.Constant(value=0)
        node.orelse[0].value=ast.Constant(value=0)
    assert ast.dump(trees[0])==ast.dump(trees[1])


@pytest.mark.parametrize('adx',[None,14.,15.,18.,19.9,20.,24.9])
def test_monotonic_preserves_lower_adx_bands(adx):
    s=snapshot(adx)
    for spike in (False,True):
        assert candidate('monotonic').long_regime_score(s,atr_spike_block=spike)==Original.long_regime_score(s,atr_spike_block=spike)


@pytest.mark.parametrize('adx',[25.,29.9,30.,50.])
def test_monotonic_base_stays_at_existing_1_6_above_25(adx):
    assert candidate('monotonic').long_regime_score(snapshot(adx),atr_spike_block=False)==1.6


@pytest.mark.parametrize('adx,expected',[(None,0),(14.,.5),(17.9,.5),(18.,1),(19.9,1),(20.,2),(25.,2),(50.,2)])
def test_shared_strength_is_exact_existing_direction_neutral_schedule(adx,expected):
    cls=candidate('strength');s=snapshot(adx,plus_di=5,minus_di=30,adx_slope=1,atr_growth_20=.5)
    assert cls.long_regime_score(s,atr_spike_block=False)==cls.regime_score(s,atr_spike_block=False)==expected
    assert cls.long_regime_score(s,atr_spike_block=True)==0


def test_monotonic_keeps_adjustments_and_score_clip():
    cls=candidate('monotonic')
    assert cls.long_regime_score(snapshot(26,plus_di=25,minus_di=20,atr_growth_20=0),atr_spike_block=False)==2
    assert cls.long_regime_score(snapshot(26,plus_di=25,minus_di=20,atr_growth_20=0),atr_spike_block=True)==1.5


def test_unknown_variant_rejected():
    with pytest.raises(ValueError,match='Unsupported'):candidate_source(SOURCE.read_text(),'all')


def test_generator_rejects_drifted_base_schedule():
    source=SOURCE.read_text().replace('score += 0.7','score += 0.6')
    with pytest.raises(ValueError,match='Unexpected high-ADX'):candidate_source(source,'monotonic')
