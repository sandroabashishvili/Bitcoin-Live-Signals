import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
from platform_v2.tools.research.trend_symmetry_experiment import candidate_source
from platform_v2.spot.services.signal.long_component_score_service import SpotLongComponentScoreService


SOURCE = Path(__file__).parents[3]/'spot/services/signal/long_component_score_service.py'


def candidate():
    namespace = {}
    exec(candidate_source(SOURCE.read_text()), namespace)
    return namespace['SpotLongComponentScoreService']


def test_only_short_trend_constants_change():
    original = ast.parse(SOURCE.read_text())
    changed = ast.parse(candidate_source(SOURCE.read_text()))
    for tree in (original, changed):
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name=='short_trend_score')
        for node in ast.walk(method):
            if isinstance(node, ast.AugAssign):node.value = ast.Constant(value=0)
    assert ast.dump(original) == ast.dump(changed)


@pytest.mark.parametrize('present', [False, True])
@pytest.mark.parametrize('adx', [None, 19., 20., 30.])
def test_mirrored_inputs_have_identical_scores(present, adx):
    cls = candidate()
    long = SimpleNamespace(ema50=100 if present else None, ema200=90 if present else None,
        ema50_slope=1 if present else None, adx=adx, plus_di=30, minus_di=10)
    short = SimpleNamespace(ema50=100 if present else None, ema200=110 if present else None,
        ema50_slope=-1 if present else None, adx=adx, plus_di=10, minus_di=30)
    assert cls.long_trend_score(long, 105) == cls.short_trend_score(short, 95)
    assert cls.long_trend_score(long, 105) == SpotLongComponentScoreService.long_trend_score(long,105)


def test_neutral_equalities_abstain_and_maximum_is_unchanged_long_max():
    cls = candidate()
    neutral = SimpleNamespace(ema50=100, ema200=100, ema50_slope=0, adx=25, plus_di=20, minus_di=20)
    assert cls.long_trend_score(neutral,100) == cls.short_trend_score(neutral,100) == 0
    bullish = SimpleNamespace(ema50=100, ema200=90, ema50_slope=1, adx=25, plus_di=30, minus_di=10)
    assert cls.long_trend_score(bullish,105) == pytest.approx(3.1)


def test_generator_rejects_unexpected_short_formula():
    source = SOURCE.read_text().replace('score += 1.0', 'score += 1.1')
    with pytest.raises(ValueError, match='Unexpected'):candidate_source(source)
