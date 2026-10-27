import json
import os
import time

from platform_v2.shared.backend.chart_payloads import build_equity_chart_payload
from platform_v2.tools.diagnostics.checks.dashboard_data_checks import dashboard_data_findings


def test_backend_chart_passes_and_tampered_percentage_fails(tmp_path):
    directory = tmp_path / 'spot/dashboard/overview_spot'
    directory.mkdir(parents=True)
    path = directory / 'index.html'
    payload = build_equity_chart_payload([{'datetime': '2026-10-26T00:00:00Z', 'equity': 3010., 'starting_capital': 3000.}])
    def write():
        path.write_text('<script>window.__SSH_OVERVIEW_EQUITY__ = ' + json.dumps(payload) + ';</script>')
    write()
    assert dashboard_data_findings(tmp_path) == []
    payload['rows'][0]['chart_point'][1] = 99
    write()
    assert any(f.issue == 'dashboard_equity_contract_mismatch' for f in dashboard_data_findings(tmp_path))


def test_invalid_payload_and_financial_reduction_are_visible(tmp_path):
    directory = tmp_path / 'futures/dashboard/overview_futures'
    directory.mkdir(parents=True)
    (directory / 'index.html').write_text('<script>window.__SSH_OVERVIEW_EQUITY__ = {broken};</script>')
    (directory / 'finance.js').write_text('const net_pnl = rows.reduce((a,b) => a + b.net_pnl, 0);')
    codes = {f.issue for f in dashboard_data_findings(tmp_path)}
    assert codes == {'dashboard_equity_payload_invalid', 'frontend_financial_calculation_candidate'}


def test_backend_mismatch_is_reported_after_generation_grace(tmp_path):
    directory = tmp_path / 'spot/dashboard/overview_spot'
    directory.mkdir(parents=True)
    path = directory / 'index.html'
    rows = [{'datetime': '2026-10-26T00:00:00Z', 'equity': 3010., 'starting_capital': 3000.}]
    payload = build_equity_chart_payload(rows)
    path.write_text('<script>window.__SSH_OVERVIEW_EQUITY__ = ' + json.dumps(payload) + ';</script>')
    expected = {'spot': [{**rows[0], 'equity': 3009.}]}
    assert dashboard_data_findings(tmp_path, expected_equity=expected) == []
    os.utime(path, (time.time()-180, time.time()-180))
    assert any(f.issue == 'dashboard_equity_source_out_of_sync' for f in dashboard_data_findings(tmp_path, expected_equity=expected))
