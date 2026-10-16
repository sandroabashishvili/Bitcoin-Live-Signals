import pytest
from platform_v2.tools.research.spot_permission_audit import audit_rows, failed_checks, summarize


def row(oid=1, checks=None, status='DENIED', reason='proximity_block', side='BUY'):
    return {'observation_id': oid, 'clock_ms': 0, 'signal': {'side': side},
            'permission': {'status': status, 'reason': reason, 'checks': checks or {}}}


def test_overlaps_and_sole_failures_are_distinct():
    rows = [row(1, {'proximity': False, 'cooldown': False}),
            row(2, {'proximity': False, 'cooldown': True}),
            row(3, {'proximity': True, 'cooldown': True}, 'ALLOWED', 'allowed'),
            row(4, side='NO_SIGNAL')]
    result = audit_rows(rows, {0: 100, 3600000: 101}, 20000000)
    assert result['all_BUY']['BUY_cycles'] == 3
    assert result['allowed']['BUY_cycles'] == 1
    assert result['denied']['BUY_cycles'] == 2
    assert result['checks']['proximity']['failed_including_overlaps']['BUY_cycles'] == 2
    assert result['checks']['proximity']['sole_failed_check']['BUY_cycles'] == 1
    assert result['checks']['cooldown']['sole_failed_check']['BUY_cycles'] == 0


def test_exact_labels_no_interpolation_and_no_future_period():
    result = summarize([row()], {0: 100, 900000: 102, 3599999: 999, 14400000: 200}, 14400000)
    assert result['forward_returns']['15']['mean_pct'] == pytest.approx(2)
    assert result['forward_returns']['60']['missing'] == {'endpoint_minute_missing': 1}
    assert result['forward_returns']['240']['missing'] == {'outside_frozen_period': 1}


def test_empty_groups_do_not_claim_zero_return():
    assert summarize([], {}, 999)['forward_returns']['15']['mean_pct'] is None


def test_missing_permissions_fail_closed():
    with pytest.raises(ValueError, match='permission evidence'):
        failed_checks({'permission': None})
