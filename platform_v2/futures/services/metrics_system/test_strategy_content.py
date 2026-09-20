from platform_v2.futures.services.metrics_system.strategy_content import StrategyPageContentService


def test_embedded_denied_permission_is_visible_without_legacy_denied_row() -> None:
    signal = {
        "side": "SHORT",
        "permission_status": "DENIED",
        "permission_reason": "cooldown_block",
    }

    status_html = StrategyPageContentService.execution_result_html(signal, [])
    reason_html = StrategyPageContentService.denial_reason_cell_html(signal, [])

    assert "Denied" in status_html
    assert "Cooldown active" in reason_html


def test_embedded_allowed_permission_is_visible_as_opened() -> None:
    signal = {"side": "LONG", "permission_status": "ALLOWED"}

    status_html = StrategyPageContentService.execution_result_html(signal, [])

    assert "Opened" in status_html
