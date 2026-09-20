from __future__ import annotations

from platform_v2.tools.research.replay.gate_ablation_audit import (
    _gate_rows,
    _pass_count_rows,
)


def test_gate_rows_compare_pass_and_fail_pnl() -> None:
    rows = [
        {"net_pnl": 2.0, "gates": {"mtf": True}},
        {"net_pnl": -1.0, "gates": {"mtf": False}},
    ]

    result = _gate_rows(rows)["mtf"]

    assert result["passed"]["net_pnl"] == 2.0
    assert result["failed"]["net_pnl"] == -1.0
    assert result["avg_net_pnl_delta"] == 3.0


def test_pass_count_cohorts_do_not_double_count_trades() -> None:
    rows = [
        {"net_pnl": 1.0, "gates": {"mtf": True, "regime": True}},
        {"net_pnl": -1.0, "gates": {"mtf": True}},
    ]

    result = _pass_count_rows(rows)

    assert result["1"]["trades"] == 1
    assert result["2"]["trades"] == 1
