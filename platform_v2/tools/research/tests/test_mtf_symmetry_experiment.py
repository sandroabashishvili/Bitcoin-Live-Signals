from types import SimpleNamespace

import pytest

from platform_v2.tools.research.mtf_symmetry_experiment import HELPERS, candidate_source


def service():
    ns = {'settings': SimpleNamespace(REGIME_ADX_MIN=20)}
    exec('class Candidate:\n' + HELPERS, ns)
    return ns['Candidate']


def snapshot(**kw):
    values = dict(rsi=60, price=110, vwap=100, adx=25, ema50_slope=1,
                  tenkan=110, kijun=100, ema50=110, ema200=100)
    values.update(kw)
    return SimpleNamespace(**values)


@pytest.mark.parametrize('tf', ['5m', '15m', '4h'])
def test_exact_mirror_long_and_short(tf):
    assert service()._symmetric_signal(tf, snapshot()) == 'LONG'
    assert service()._symmetric_signal(tf, snapshot(rsi=40, price=90, ema50_slope=-1, tenkan=90, ema50=90)) == 'SHORT'


@pytest.mark.parametrize('adx', [None, 20, 19, float('nan')])
def test_adx_is_a_shared_filter_not_directional_vote(adx):
    s = service()
    assert s._symmetric_signal('5m', snapshot(adx=adx)) == 'NO_SIGNAL'
    assert s._symmetric_signal('5m', snapshot(adx=adx, rsi=40, price=90)) == 'NO_SIGNAL'


@pytest.mark.parametrize('tf', ['5m', '15m'])
def test_rsi_equality_missing_and_conflicting_votes_abstain(tf):
    for rsi in [None, 50, float('nan'), 40]:
        assert service()._symmetric_signal(tf, snapshot(rsi=rsi)) == 'NO_SIGNAL'


def test_higher_requires_two_valid_votes():
    assert service()._symmetric_signal('4h', snapshot(rsi=None)) == 'LONG'
    assert service()._symmetric_signal('4h', snapshot(rsi=None, tenkan=None)) == 'NO_SIGNAL'


def test_original_dispatch_preserved_for_other_timeframes():
    original = '''class MultiTimeframeContextService:
    @staticmethod
    def _signal_for_timeframe(*, timeframe, snapshot):
        if snapshot is None:
            return "NO_SIGNAL"
        if timeframe == "5m":
            return "legacy_5m"
        if timeframe == "4h":
            return "legacy_4h"
        return "legacy_15m"
'''
    ns = {'settings': SimpleNamespace(REGIME_ADX_MIN=20)}
    exec(candidate_source(original, ['4h']), ns)
    s = ns['MultiTimeframeContextService']
    assert s._signal_for_timeframe(timeframe='5m', snapshot=snapshot()) == 'legacy_5m'
    assert s._signal_for_timeframe(timeframe='15m', snapshot=snapshot()) == 'legacy_15m'
    assert s._signal_for_timeframe(timeframe='4h', snapshot=snapshot()) == 'LONG'
    assert s._signal_for_timeframe(timeframe='4h', snapshot=None) == 'NO_SIGNAL'
