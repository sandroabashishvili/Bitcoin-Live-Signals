import pytest
from platform_v2.tools.research.replay.score_calibration import *

BASE=dict(zip(COMPONENTS,(1,0.8,1.3,1,0.9,0.9)))


def test_relative_weights_preserve_scale_and_other_direction():
    c=Calibration('x',component='trend',multiplier=1.25)
    w=weights_for(BASE,c,'SHORT')
    assert sum(w.values()) == pytest.approx(sum(BASE.values()))
    assert w['trend']/w['mtf'] == pytest.approx(BASE['trend']/BASE['mtf']*1.25)
    assert weights_for(BASE,c,'LONG')==BASE
    assert BASE['trend']==1.3


def test_counter_momentum_changes_score_without_veto():
    c=Calibration('x',adjustment='macd_no_counter_reward')
    scores=dict(zip(COMPONENTS,(4,2,4,2.2,0,1.9)))
    out=components_for(scores,c,'SHORT',dict(macd=-89.64,macd_signal=-122.15,atr=217.63))
    assert out['momentum']==pytest.approx(1.4)
    assert weighted_score(out,BASE)==13.91
    assert scores['momentum']==2.2


def test_missing_confirmation_not_treated_as_rejection_failure():
    c=Calibration('x',adjustment='structure_no_rejection_discount')
    assert components_for({'structure':2},c,'SHORT',{})['structure']==2


def test_candidate_grid_is_small_unique_and_baseline_is_identity():
    grid=list(candidates())
    assert len(grid)==28 and len({x.name for x in grid})==28
    assert weights_for(BASE,grid[0],'SHORT')==BASE


def test_archived_total_survives_loss_of_component_float_precision():
    scores=dict(zip(COMPONENTS,(0,0,3.1,1.6,1.85,0)))
    assert weighted_score(scores,BASE)==7.3
    assert archived_score_delta(7.29,scores,BASE,scores,BASE)==7.29
