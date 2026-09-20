from platform_v2.tools.diagnostics.checks import futures_runtime_checks as checks


def test_missing_entry_signal_is_reported(monkeypatch):
    monkeypatch.setattr(checks, "load_family_rows_all", lambda *args: [
        {"position_id": "FUT-1", "entry_signal": {}},
        {"position_id": "FUT-2", "entry_signal": {"side": "SHORT"}},
    ])
    findings = []
    checks._check_entry_audit_signal_coverage(findings)
    assert len(findings) == 1
    assert findings[0].issue == "futures_entry_audit_signal_missing"
    assert "1/2" in findings[0].detail


def test_empty_or_linked_audits_do_not_raise_false_alarm(monkeypatch):
    for rows in ([], [{"entry_signal": {"side": "SHORT", "gates": {"mtf": False}}}]):
        monkeypatch.setattr(checks, "load_family_rows_all", lambda *args: rows)
        findings = []
        checks._check_entry_audit_signal_coverage(findings)
        assert findings == []


def test_sqlite_only_runtime_checks_audits_without_json_tree(monkeypatch, tmp_path):
    monkeypatch.setattr(checks, "_RUNTIME_DATA", tmp_path / "absent_json_tree")
    monkeypatch.setattr(checks, "load_family_rows_all", lambda *args: [{"entry_signal": {}}])
    findings = checks.futures_runtime_integrity_findings()
    assert len(findings) == 1
    assert findings[0].issue == "futures_entry_audit_signal_missing"
