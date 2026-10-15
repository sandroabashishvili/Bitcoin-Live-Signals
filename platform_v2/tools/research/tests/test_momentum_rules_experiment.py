import ast
from pathlib import Path
from types import SimpleNamespace
import pytest
from platform_v2.tools.research.momentum_rules_experiment import candidate_source
from platform_v2.spot.services.signal.long_component_score_service import SpotLongComponentScoreService as Original

SOURCE=Path(__file__).parents[3]/'spot/services/signal/long_component_score_service.py'


def candidate(variant):
    namespace={};exec(candidate_source(SOURCE.read_text(),variant),namespace)
    return namespace['SpotLongComponentScoreService']()


def snapshot(rsi,macd=None,signal=None):
    return SimpleNamespace(rsi=rsi,macd=macd,macd_signal=signal,extras={'macd_histogram':[1,2,3]},atr=1)


@pytest.mark.parametrize('variant',['rsi_direction','macd_positive'])
def test_no_other_method_changes(variant):
    trees=[ast.parse(SOURCE.read_text()),ast.parse(candidate_source(SOURCE.read_text(),variant))]
    for tree in trees:
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='long_momentum_score')
        method.body=[ast.Pass()]
    assert ast.dump(trees[0])==ast.dump(trees[1])


@pytest.mark.parametrize('variant,index',[('rsi_direction',0),('macd_positive',1)])
def test_exactly_the_declared_rule_changes(variant,index):
    trees=[ast.parse(SOURCE.read_text()),ast.parse(candidate_source(SOURCE.read_text(),variant))]
    for tree in trees:
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='long_momentum_score')
        checks=[n for n in method.body if isinstance(n,ast.If)]
        if index==0:checks[0].body=[ast.Pass()]
        else:checks[1].test=ast.Constant(value=True)
    assert ast.dump(trees[0])==ast.dump(trees[1])


@pytest.mark.parametrize('rsi,points',[(None,0),(49,0),(50,0),(50.1,1.4),(58,1.4),(65,1.4),(72,1.4),(90,1.4)])
def test_directional_rsi_boundary_and_no_upper_cutoff(rsi,points):
    assert candidate('rsi_direction').long_momentum_score(snapshot(rsi))==points


@pytest.mark.parametrize('macd,signal,points',[(None,1,0),(1,None,0),(-1,-2,0),(0,0,0),(1,2,0),(2,1,.8),(1,1,.8)])
def test_positive_macd_requires_zero_axis_without_changing_original_equality(macd,signal,points):
    assert candidate('macd_positive').long_momentum_score(snapshot(None,macd,signal))==points


@pytest.mark.parametrize('variant',['rsi_direction','macd_positive'])
def test_histogram_disabled_and_peak_not_increased(variant):
    cls=candidate(variant)
    assert not cls.has_rising_macd_histogram(snapshot(60,2,1))
    assert cls.long_momentum_score(snapshot(60,2,1))==pytest.approx(2.2)
    assert cls.short_momentum_score(snapshot(40,-2,-1))==Original.short_momentum_score(snapshot(40,-2,-1))


def test_positive_macd_preserves_original_rsi_bands():
    cls=candidate('macd_positive')
    for rsi in (None,49,50,52,58,65,72,90):
        assert cls.long_momentum_score(snapshot(rsi,2,1))==Original().long_momentum_score(snapshot(rsi,2,1))


def test_original_gate_is_narrow_rsi_band_with_disabled_histogram():
    for rsi in (50,51,52,57.9,65,71.9,72,90):
        assert Original().long_momentum_score(snapshot(rsi,2,1))<2
    for rsi in (58,60,64.9):
        assert Original().long_momentum_score(snapshot(rsi,2,1))>=2


def test_generator_rejects_unknown_variant_and_drifted_formula():
    with pytest.raises(ValueError,match='Unsupported'):candidate_source(SOURCE.read_text(),'all')
    with pytest.raises(ValueError,match='Unexpected RSI'):candidate_source(SOURCE.read_text().replace('score += 1.4','score += 1.5'),'rsi_direction')
