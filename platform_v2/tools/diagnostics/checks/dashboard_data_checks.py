"""Validate backend chart contracts embedded in generated local dashboards.

This is not a browser test and does not certify every rendered table cell.
JavaScript finance reductions are review candidates, not proven bugs.
"""

import json
from pathlib import Path
import re
import time
import sqlite3

from platform_v2.shared.backend.chart_payloads import build_equity_chart_payload
from platform_v2.tools.diagnostics.core.config import V2_ROOT
from platform_v2.tools.diagnostics.core.models import add_finding


_EQUITY_ASSIGNMENT = re.compile(r'window\.__SSH_OVERVIEW_EQUITY__\s*=\s*')
_FINANCIAL_FIELD = re.compile(r'\b(?:net_pnl|gross_pnl|win_rate|fees_paid|total_positions|equity|netPnl|winRate)\b')


def dashboard_data_findings(root: Path = V2_ROOT, *, expected_equity=None):
    findings = []
    if expected_equity is None:
        try:
            expected_equity = _backend_equity_rows() if root == V2_ROOT else {}
        except (OSError, sqlite3.Error, ValueError, TypeError) as exc:
            add_finding(findings, str(root), 'dashboard_backend_comparison_unavailable', str(exc), 'medium')
            expected_equity = {}
    for subsystem in ('spot', 'futures', 'futures_hedge'):
        dashboard = root / subsystem / 'dashboard'
        for path in sorted(dashboard.rglob('*.html')):
            try:
                text = path.read_text(encoding='utf-8')
            except OSError as exc:
                add_finding(findings, str(path), 'dashboard_data_unreadable', str(exc), 'high')
                continue
            for match in _EQUITY_ASSIGNMENT.finditer(text):
                try:
                    payload, _ = json.JSONDecoder().raw_decode(text[match.end():].lstrip())
                    if not isinstance(payload, dict) or not isinstance(payload.get('rows'), list):
                        raise ValueError('equity payload must be an object with rows')
                    rows = payload['rows']
                    if any(not isinstance(row, dict) for row in rows):
                        raise ValueError('equity rows must be objects')
                    expected = build_equity_chart_payload(rows)
                    for key in ('version', 'rows', 'axis_min', 'axis_max', 'max_point', 'min_point'):
                        if payload.get(key) != expected[key]:
                            add_finding(findings, str(path), 'dashboard_equity_contract_mismatch',
                                        f'{key} differs from backend chart contract', 'high')
                    # Pages are written after the ledger commit. Do not flag the
                    # brief generation window as a broken trading calculation.
                    source_rows = expected_equity.get(subsystem)
                    if source_rows is not None and time.time() - path.stat().st_mtime > 120:
                        source_points = build_equity_chart_payload(source_rows)['rows']
                        actual = [(r.get('timestamp_ms'), r.get('equity')) for r in rows]
                        wanted = [(r.get('timestamp_ms'), r.get('equity')) for r in source_points]
                        if actual != wanted:
                            add_finding(findings, str(path), 'dashboard_equity_source_out_of_sync',
                                        'Embedded equity series differs from current backend source; check page generation time', 'medium')
                except (ValueError, TypeError, OverflowError) as exc:
                    add_finding(findings, str(path), 'dashboard_equity_payload_invalid', str(exc), 'high')
        # Only flag explicit data reductions alongside financial fields.
        # Layout, tooltip formatting and timestamps are intentionally not banned.
        for path in sorted(dashboard.rglob('*.js')):
            text = path.read_text(encoding='utf-8')
            if re.search(r'\.reduce\s*\(', text) and _FINANCIAL_FIELD.search(text):
                add_finding(findings, str(path), 'frontend_financial_calculation_candidate',
                            'Review financial reduction: authoritative aggregates must come from backend', 'medium')
    return findings


def _backend_equity_rows():
    """Reuse read-only source builders, never build_and_store or Hedge replay."""
    from platform_v2.spot.services.metrics_system.overview_content import OverviewPageContentService
    from platform_v2.shared.backend.runtime_store.spot import load_latest_document
    from platform_v2.futures.dashboard.overview_futures.py.page_builder import OverviewFuturesPageBuilder
    from platform_v2.futures_hedge.services.overview_content import FuturesHedgeOverviewContentService
    from platform_v2.shared.backend.runtime_store.hedge import load_family_rows_all

    hedge_rows = load_family_rows_all('hedge_basket_snapshots') or load_family_rows_all('hedge_equity_timeline')
    return {
        'spot': OverviewPageContentService()._build_capital_curve(metrics=load_latest_document('metrics') or {}),
        'futures': OverviewFuturesPageBuilder()._load_equity_chart_rows(),
        'futures_hedge': FuturesHedgeOverviewContentService._equity_chart_rows(hedge_rows),
    }
