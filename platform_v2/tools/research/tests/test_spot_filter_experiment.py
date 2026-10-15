import ast
from pathlib import Path
from platform_v2.tools.research.spot_filter_experiment import candidate_source

SOURCE=Path(__file__).parents[3]/'spot/services/permission/permission_decision_service.py'


def test_only_proximity_method_body_changes():
    before=ast.parse(SOURCE.read_text())
    after=ast.parse(candidate_source(SOURCE.read_text()))
    for tree in (before,after):
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_passes_proximity')
        method.body=[ast.Pass()]
    assert ast.dump(before)==ast.dump(after)


def test_proximity_ablation_does_not_disable_capital_exposure_or_slots():
    source=candidate_source(SOURCE.read_text())
    namespace={}
    exec(source,namespace)
    cls=namespace['PermissionDecisionService']
    assert cls._passes_proximity(live_entry_price=100,last_entry_price=100,proximity_pct=.5)
    from platform_v2.spot.domain.models.signal import SignalDecision,SignalSide
    signal=SignalDecision(timestamp_ms=1,symbol='BTCUSDT',timeframe='15m',side=SignalSide.BUY,snapshot_price=100,score=9,threshold=8.5)
    service=cls()
    assert service.evaluate(signal,100,available_balance=0).checks.capital is False
    assert service.evaluate(signal,100,current_open_exposure=10000).checks.exposure is False
    assert service.evaluate(signal,100,open_positions_count=999).checks.position_slots is False
    assert service.evaluate(signal,100,cooldown_active=True).checks.cooldown is False
