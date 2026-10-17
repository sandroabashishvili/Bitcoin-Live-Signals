"""Predeclared exploratory BUY-only candidates; never imported by live Spot.

All windows contain CLOSED candles ending at the decision candle. Thresholds
are hypotheses, not fitted parameters or claims of independent confirmation.
"""
from dataclasses import asdict, replace
from math import isfinite

SCENARIOS = ('pullback', 'breakout', 'reversal', 'range_bounce', 'failed_break')
ISOLATED_VARIANTS = {'scenario_'+name+'_v1': name for name in SCENARIOS}
SUPPORTED_CANDIDATES = ('votes_existing_v1', 'scenarios_votes_v1', *ISOLATED_VARIANTS)
PROTOCOL = {
    'version': 'spot-votes-scenarios-v1',
    'timeframes': ['5m', '15m', '4h'], 'required_votes': 4,
    'votes_existing': 'Existing six LONG gate booleans; equal 0/1 votes, >=4 BUY, no opposing SHORT veto.',
    'scenario_windows': 'Current closed candle c; previous candle p; previous 20 closed candles exclude c. ATR is current native ATR.',
    'pullback': 'price>EMA50, EMA50 slope>0; min low of previous 3 bars <= current EMA9; c closes above EMA9 and previous close, c is bullish.',
    'breakout': 'c closes > previous-20 high + 0.1 ATR; bullish c; c volume >=1.2 times previous-20 mean volume.',
    'reversal': 'Previous 10 closes have negative endpoint change; p low <= min low of preceding 10; bullish c closes above preceding 3 highs.',
    'range_bounce': 'ADX<25; previous-20 range width between 2 and 8 ATR inclusive; c low <= prior range low+0.25 ATR; bullish c closes > range low+0.25 ATR and < range midpoint.',
    'failed_break': 'Support=min lows of 20 bars before p; min(p.low,c.low)<support-0.1 ATR; bullish c closes > support+0.1 ATR.',
    'scenario_votes': {
        'mtf': 'At least 2 of 3 CLOSED snapshots: price>EMA9 and MACD>=signal.',
        'regime': 'range_bounce: ADX<25; others ADX>=15. ATR spike fails this vote only.',
        'trend': 'pullback/breakout: price>EMA50 and EMA50 slope>0; others price>EMA9.',
        'momentum': 'RSI>=50 and MACD>=signal.',
        'orderbook': 'Positive total executed volume and buyers>sellers (not passive book depth).',
        'structure': 'The respective scenario detector is true. Also mandatory for that scenario; this overlaps its vote, not independent evidence.'},
    'selection': 'Any detected scenario with >=4 votes; first qualifying scenario in declared order labels ONE decision; retain all matches and votes.',
    'confidence': 'Preserve native weighted LONG confidence for SL/TP, sizing and other native consumers, even for newly emitted BUY. Equal weights apply to signal voting ONLY.',
    'execution': 'Native quality/permission/sizing/fees/exits unchanged. New signal history and different entry times naturally change positions and adaptive setup values.',
    'research_only': True, 'holdout': 'None; historical exploratory comparison, not out-of-sample validation.'}


def finite(*values):
    return all(isinstance(x, (int, float)) and isfinite(x) for x in values)


def detectors(snapshot, candles):
    result = dict.fromkeys(SCENARIOS, False)
    if len(candles) < 22:
        return result
    bars = candles[-22:]
    values = [v for b in bars for v in (b.open_price, b.high_price, b.low_price, b.close_price, b.volume)]
    if not finite(*values, snapshot.atr) or snapshot.atr <= 0:
        return result
    p, c = bars[-2:]
    prior = bars[-21:-1]
    high, low = max(b.high_price for b in prior), min(b.low_price for b in prior)
    atr = snapshot.atr
    bullish = c.close_price > c.open_price
    result['pullback'] = bool(finite(snapshot.ema9, snapshot.ema50, snapshot.ema50_slope)
        and c.close_price > snapshot.ema50 and snapshot.ema50_slope > 0
        and min(b.low_price for b in bars[-4:-1]) <= snapshot.ema9
        and c.close_price > snapshot.ema9 and c.close_price > p.close_price and bullish)
    result['breakout'] = bool(bullish and c.close_price > high + .1*atr
        and c.volume >= 1.2*sum(b.volume for b in prior)/20)
    result['reversal'] = bool(bullish and bars[-2].close_price < bars[-11].close_price
        and p.low_price <= min(b.low_price for b in bars[-12:-2])
        and c.close_price > max(b.high_price for b in bars[-4:-1]))
    result['range_bounce'] = bool(finite(snapshot.adx) and snapshot.adx < 25
        and 2*atr <= high-low <= 8*atr and c.low_price <= low+.25*atr
        and bullish and low+.25*atr < c.close_price < (high+low)/2)
    support = min(b.low_price for b in bars[-22:-2])
    result['failed_break'] = bool(min(p.low_price, c.low_price) < support-.1*atr
        and bullish and c.close_price > support+.1*atr)
    return result


def scenario_votes(context, snapshots):
    s = context.latest_snapshot
    found = detectors(s, context.recent_candles)
    aligned = sum(bool(finite(t.price, t.ema9, t.macd, t.macd_signal)
        and t.price > t.ema9 and t.macd >= t.macd_signal) for t in snapshots.values())
    b = context.latest_orderbook
    flow = bool(b is not None and finite(b.buyers, b.sellers)
        and b.buyers >= 0 and b.sellers >= 0 and b.buyers+b.sellers > 0 and b.buyers > b.sellers)
    votes = {}
    for name in SCENARIOS:
        trending = name in ('pullback', 'breakout')
        votes[name] = {
            'mtf': len(snapshots) == 3 and aligned >= 2,
            'regime': bool(finite(s.adx) and (s.adx < 25 if name == 'range_bounce' else s.adx >= 15) and not s.atr_spike),
            'trend': bool(finite(s.price, s.ema50, s.ema50_slope) and s.price > s.ema50 and s.ema50_slope > 0) if trending
                else bool(finite(s.price, s.ema9) and s.price > s.ema9),
            'momentum': bool(finite(s.rsi, s.macd, s.macd_signal) and s.rsi >= 50 and s.macd >= s.macd_signal),
            'orderbook': flow, 'structure': found[name]}
    return found, votes


class CandidateSignalService:
    def __init__(self, variant):
        if variant not in SUPPORTED_CANDIDATES:
            raise ValueError('Unknown research candidate: '+variant)
        from platform_v2.spot.services.signal.independent_long_signal_service import IndependentLongSignalService
        self.native = IndependentLongSignalService()
        self.variant = variant
        self.snapshots = {}
        self.last_diagnostics = {}

    def build_signal(self, context, timestamp_ms=None, prior_signals=()):
        from platform_v2.spot.domain.models.signal import GateSnapshot, SignalSide
        from platform_v2.spot.services.signal.entry_quality_service import SpotEntryQualityService
        base = self.native.build_signal(context, timestamp_ms=timestamp_ms, prior_signals=prior_signals)
        found, votes = scenario_votes(context, self.snapshots)
        qualified = [name for name in SCENARIOS if found[name] and sum(votes[name].values()) >= 4]
        isolated = ISOLATED_VARIANTS.get(self.variant)
        eligible = [name for name in qualified if isolated is None or name == isolated]
        selected = eligible[0] if eligible else None
        gates = asdict(base.gates) if self.variant == 'votes_existing_v1' else votes[selected or isolated or SCENARIOS[0]]
        count = sum(gates.values())
        buy = count >= 4 and (self.variant == 'votes_existing_v1' or selected is not None)
        direction = 'LONG' if buy else 'NO_SIGNAL'
        setup = self.native._setups.build_theoretical_setup(side=SignalSide.BUY,
            entry_price=context.latest_snapshot.price, snapshot=context.latest_snapshot,
            confidence=base.setup_confidence) if buy else None
        valid = setup is not None and 0 < setup.stop_loss < setup.entry_price < setup.take_profit
        history = [dict(row, side=row.get('evaluated_direction', 'NO_SIGNAL')) for row in prior_signals]
        quality = SpotEntryQualityService().evaluate(signal_side=direction, timestamp_ms=base.timestamp_ms, prior_signals=history)
        self.last_diagnostics = {'variant': self.variant, 'detected': found, 'scenario_votes': votes,
            'qualified': qualified, 'selected': selected if self.variant != 'votes_existing_v1' else None,
            'votes': gates, 'vote_count': count, 'raw_buy': buy, 'setup_valid': valid,
            'native_long_score': base.score, 'native_direction': base.evaluated_direction}
        if isolated is not None:
            self.last_diagnostics['active_scenarios'] = [isolated]
        return replace(base, side=SignalSide.BUY if buy and valid else SignalSide.NO_SIGNAL,
            score=float(count), threshold=4., gates=GateSnapshot(**gates),
            reasons=(f'Research {self.variant}: {count}/6; scenario={selected}; raw_buy={buy}; setup_valid={valid}.',),
            component_scores={name: float(value) for name, value in gates.items()},
            component_weights=dict.fromkeys(gates, 1.), theoretical_setup=setup,
            evaluated_direction=direction, direction_scores={'long': float(count), 'short': 0.}, entry_quality=asdict(quality))
