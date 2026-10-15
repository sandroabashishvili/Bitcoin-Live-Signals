import ast
from pathlib import Path
from types import SimpleNamespace
import pytest
from platform_v2.tools.research.trend_rules_experiment import candidate_source
from platform_v2.spot.services.signal.long_component_score_service import SpotLongComponentScoreService

SOURCE=Path(__file__).parents[3]/'spot/services/signal/long_component_score_service.py'


def candidate(variant):
    namespace={}
    exec(candidate_source(SOURCE.read_text(),variant),namespace)
    return namespace['SpotLongComponentScoreService']


@pytest.mark.parametrize('variant,index',[('alignment',1),('dmi',3)])
def test_only_the_two_declared_predicates_change(variant,index):
    original=ast.parse(SOURCE.read_text()); altered=ast.parse(candidate_source(SOURCE.read_text(),variant))
    for tree in (original,altered):
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
        for name in ('long_trend_score','short_trend_score'):
            method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name)
            checks=[n for n in method.body if isinstance(n,ast.If)]
            checks[index].test=ast.Constant(value=True)
    assert ast.dump(original)==ast.dump(altered)


def test_alignment_can_reward_bullish_ribbon_during_pullback():
    snapshot=SimpleNamespace(ema50=100,ema200=90,ema50_slope=1,adx=25,plus_di=30,minus_di=10)
    assert SpotLongComponentScoreService.long_trend_score(snapshot,95)==pytest.approx(1.6)
    assert candidate('alignment').long_trend_score(snapshot,95)==pytest.approx(2.4)
    assert candidate('alignment').long_trend_score(snapshot,105)==pytest.approx(3.1)


def test_alignment_mirrors_bearish_ribbon_without_changing_point_awards():
    snapshot=SimpleNamespace(ema50=100,ema200=110,ema50_slope=-1,adx=25,plus_di=10,minus_di=30)
    assert SpotLongComponentScoreService.short_trend_score(snapshot,105)==2
    assert candidate('alignment').short_trend_score(snapshot,105)==3


@pytest.mark.parametrize('adx',[None,19.,20.])
def test_dmi_without_strength_gate_keeps_direction_check(adx):
    snapshot=SimpleNamespace(ema50=None,ema200=None,ema50_slope=None,adx=adx,plus_di=30,minus_di=10)
    cls=candidate('dmi')
    assert cls.long_trend_score(snapshot,100)==.8
    assert cls.short_trend_score(snapshot,100)==0


def test_missing_di_and_neutral_equalities_do_not_create_points():
    for variant in ('alignment','dmi'):
        cls=candidate(variant)
        snapshot=SimpleNamespace(ema50=100,ema200=100,ema50_slope=0,adx=None,plus_di=None,minus_di=None)
        assert cls.long_trend_score(snapshot,100)==cls.short_trend_score(snapshot,100)==0


def test_unknown_variant_is_rejected():
    with pytest.raises(ValueError,match='Unsupported'):candidate_source(SOURCE.read_text(),'all')


@pytest.mark.parametrize('variant',['alignment','dmi'])
@pytest.mark.parametrize('price',[95,100,105])
def test_neither_variant_changes_scores_when_old_dependencies_are_satisfied(variant,price):
    cls=candidate(variant)
    # Both EMA directions neutral, so removing the price dependency adds no points.
    # ADX>=20 satisfies the original DI strength dependency.
    snapshot=SimpleNamespace(ema50=100,ema200=100,ema50_slope=1,adx=25,plus_di=30,minus_di=10)
    assert cls.long_trend_score(snapshot,price)==SpotLongComponentScoreService.long_trend_score(snapshot,price)
    assert cls.short_trend_score(snapshot,price)==SpotLongComponentScoreService.short_trend_score(snapshot,price)


def test_generator_fails_if_strength_formula_is_not_the_expected_one():
    source=SOURCE.read_text().replace('snapshot.adx >= settings.REGIME_ADX_MIN','snapshot.adx > settings.REGIME_ADX_MIN')
    with pytest.raises(ValueError,match='Unexpected DI ADX dependency'):
        candidate_source(source,'dmi')
