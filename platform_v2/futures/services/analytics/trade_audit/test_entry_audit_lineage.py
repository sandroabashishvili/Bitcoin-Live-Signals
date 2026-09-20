from platform_v2.futures.services.analytics.trade_audit.entry_audit_service import FuturesTradeEntryAuditService


def test_execution_delay_keeps_original_signal_and_timing(monkeypatch):
    service = FuturesTradeEntryAuditService()
    signal_ts = 1787380199999
    execution_ts = 1787380296083
    signal = {
        "timestamp_ms": signal_ts, "side": "SHORT", "score": 10.74,
        "gates": {"mtf": True, "orderbook": False},
        "entry_quality": {"timing_type": "FRESH_REENTRY", "direction_signal_age": 2},
        "market_plan_permission": {"alignment": "OUTSIDE_ZONE_CONTINUATION_OVERRIDE"},
    }
    seen = []
    def snapshot(**kwargs):
        seen.append(kwargs["entry_ts"])
        return {}
    monkeypatch.setattr(service, "_entry_snapshot", snapshot)
    row = service._build_audit_row(
        opened={"timestamp_ms": execution_ts, "candle_close_time": "2026-08-22 06:29:59Z", "entry_price": 77199.7},
        closed={"side": "SHORT", "timestamp_ms": execution_ts + 900000, "net_pnl": -11.83},
        signal_by_ts_side=service._index_signals([signal]), signals_sorted=[signal],
        market_plans_sorted=[], position_id="FUT-000067",
    )
    assert row["entry_timestamp_ms"] == execution_ts
    assert row["entry_signal_timestamp_ms"] == signal_ts
    assert row["entry_signal"]["gates"]["mtf"] is True
    assert row["entry_timing_type"] == "FRESH_REENTRY"
    assert row["entry_market_plan_permission"]["alignment"] == "OUTSIDE_ZONE_CONTINUATION_OVERRIDE"
    assert seen == [signal_ts]


def test_missing_source_does_not_match_neighbor_or_opposite_direction():
    signals = [{"timestamp_ms": 1787380199999, "side": "LONG"},
               {"timestamp_ms": 1787379299999, "side": "SHORT"}]
    result = FuturesTradeEntryAuditService._entry_signal(
        opened={"candle_close_time": "2026-08-22 06:29:59Z"}, closed={}, side="SHORT",
        entry_ts=1787380296083,
        signal_by_ts_side=FuturesTradeEntryAuditService._index_signals(signals),
    )
    assert result == {}


def test_legacy_exact_timestamp_is_supported():
    signal = {"timestamp_ms": 1234, "side": "SHORT"}
    assert FuturesTradeEntryAuditService._entry_signal(
        opened={}, closed={}, side="SHORT", entry_ts=1234,
        signal_by_ts_side={(1234, "SHORT"): signal},
    ) == signal


def test_missing_open_event_uses_closed_signal_lineage():
    signal = {"timestamp_ms": 1787380199999, "side": "SHORT"}
    assert FuturesTradeEntryAuditService._entry_signal(
        opened={}, closed={"signal_candle_close_time": "2026-08-22 06:29:59Z"},
        side="SHORT", entry_ts=1787380296083,
        signal_by_ts_side={(1787380199999, "SHORT"): signal},
    ) == signal
