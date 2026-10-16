import ast
from types import SimpleNamespace
import pytest
from platform_v2.tools.research.structure_rules_experiment import candidate_source,RULES
from platform_v2.spot.services.signal.long_structure_score_service import SpotLongStructureScoreService as Original

from platform_v2.tools.research.tests.paths import PLATFORM_ROOT

SOURCE = PLATFORM_ROOT / 'spot/services/signal/long_structure_score_service.py'


def candidate(variant):
    namespace={};exec(compile(candidate_source(SOURCE.read_text(),variant),str(SOURCE),'exec'),namespace)
    return namespace['SpotLongStructureScoreService']


def snapshot(distance=1.25,room=1.25,bounce=False,atr=1):
    return SimpleNamespace(swing_low=100-distance,swing_high=100+room,atr=atr,bounce_confirmed=bounce,extras={})


@pytest.mark.parametrize('variant',RULES)
def test_only_long_structure_method_changes(variant):
    trees=[ast.parse(SOURCE.read_text()),ast.parse(candidate_source(SOURCE.read_text(),variant))]
    for tree in trees:
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
        next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='long_score').body=[ast.Pass()]
    assert ast.dump(trees[0])==ast.dump(trees[1])


@pytest.mark.parametrize('room',[-1,0,.49,.5,.99,1,1.49,1.5,2,10])
def test_room_only_removes_large_headroom_discount(room):
    s=snapshot(room=room)
    expected=Original.long_score(s,100,False)+(.7 if room>=1.5 else 0)
    assert candidate('room').long_score(s,100,False)==pytest.approx(expected)


@pytest.mark.parametrize('distance,points',[(0,0),(.99,0),(1,.8),(1.49,.8),(1.5,1),(2.49,1),(2.5,.5),(3.99,.5),(4,.2),(5.99,.2),(6,0),(9,0)])
def test_distance_ladder_boundaries(distance,points):
    # Fixed original headroom award of 0.8.
    assert candidate('distance').long_score(snapshot(distance=distance),100,False)==pytest.approx(points+.8)


@pytest.mark.parametrize('variant',RULES)
def test_spike_missing_input_and_bounce_unchanged(variant):
    cls=candidate(variant)
    assert cls.long_score(snapshot(),100,True)==0
    for atr in (None,0,-1):assert cls.long_score(snapshot(atr=atr),100,False)==0
    for field in ('swing_low','swing_high'):
        s=snapshot();setattr(s,field,None);assert cls.long_score(s,100,False)==0
    assert cls.long_score(snapshot(bounce=True),100,False)==pytest.approx(cls.long_score(snapshot(),100,False)+.2)


@pytest.mark.parametrize('variant',RULES)
def test_opposing_short_rule_and_peak_not_changed(variant):
    cls=candidate(variant)
    for distance in (.25,1,1.5,2.5,4,6):
        for room in (.25,.75,1.25,2,5):
            s=snapshot(distance,room,True)
            assert cls.short_score(s,100,False)==Original.short_score(s,100,False)
            assert 0<=cls.long_score(s,100,False)<=2


def test_combined_is_exact_sum_of_two_deltas():
    for distance in (.5,1.25,2,3,5,7):
        for room in (.25,.75,1.25,2,5):
            s=snapshot(distance,room)
            original=Original.long_score(s,100,False)
            # Test unclipped positive room so additive ablations are identifiable.
            if room>=1:
                expected=candidate('room').long_score(s,100,False)+candidate('distance').long_score(s,100,False)-original
                assert candidate('combined').long_score(s,100,False)==pytest.approx(expected)


def test_generator_rejects_drift_and_unknown_variants():
    with pytest.raises(ValueError):candidate_source(SOURCE.read_text(),'unknown')
    with pytest.raises(ValueError,match='Unexpected'):candidate_source(SOURCE.read_text().replace('score += 1.0','score += 2.0'),'room')
