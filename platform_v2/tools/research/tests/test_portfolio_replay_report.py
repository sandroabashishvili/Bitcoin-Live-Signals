from platform_v2.tools.research.replay.portfolio_replay_report import _empty_side


def test_empty_side_supports_sparse_forward_period_reports() -> None:
    side = _empty_side()

    assert side["closed"]["net_pnl"] == 0.0
    assert side["train"]["net_pnl"] == 0.0
    assert side["test"]["net_pnl"] == 0.0
