from types import SimpleNamespace

from platform_v2.spot.config import settings
from platform_v2.tools.research.replay import legacy_spot_signal
from platform_v2.tools.research.replay.legacy_spot_signal import SignalDecisionService


def _decision(monkeypatch, regime_score):
    service = SignalDecisionService()
    context = SimpleNamespace(
        latest_snapshot=SimpleNamespace(timestamp_text="2026-09-09 12:00:00"),
        latest_candle=SimpleNamespace(close_time_ms=1000),
        mtf_direction="BUY", mtf_signals={"5m": "BUY"},
    )
    monkeypatch.setattr(service, "_buy_atr_spike_block", lambda snapshot: False)
    monkeypatch.setattr(service, "_build_buy_component_scores", lambda context: {
        "mtf": 4.0, "trend": 4.0, "regime": regime_score,
        "momentum": 2.0, "orderbook": 2.0, "structure": 2.0,
    })
    monkeypatch.setattr(service, "_build_directional_decision", lambda **kwargs: ("BUY", kwargs))
    monkeypatch.setattr(service, "_build_no_signal_decision", lambda **kwargs: ("NO_SIGNAL", kwargs))
    return service.build_signal(context)


def test_high_score_cannot_bypass_failed_regime(monkeypatch):
    monkeypatch.setattr(legacy_spot_signal, "BUY_REQUIRE_REGIME", True)
    kind, detail = _decision(monkeypatch, 0.5)
    assert kind == "NO_SIGNAL"
    assert detail["buy_score"] > settings.BUY_THRESHOLD
    assert any("regime confirmation is required" in reason for reason in detail["reasons"])


def test_confirmed_regime_still_allows_qualified_buy(monkeypatch):
    kind, _ = _decision(monkeypatch, settings.REGIME_RAW_GATE_MIN)
    assert kind == "BUY"


def test_regime_confirmation_does_not_bypass_score():
    assert not SignalDecisionService._buy_is_actionable(
        context=None, buy_score=settings.BUY_THRESHOLD-0.01, regime_passed=True,
    )


def test_legacy_control_can_be_reconstructed(monkeypatch):
    monkeypatch.setattr(legacy_spot_signal, "BUY_REQUIRE_REGIME", False)
    kind, _ = _decision(monkeypatch, 0.5)
    assert kind == "BUY"
