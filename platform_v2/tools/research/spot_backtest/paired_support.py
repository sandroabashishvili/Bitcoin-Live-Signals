"""Research-only matched-start helpers; no live storage access."""
from dataclasses import asdict, replace


def select_cohort(eligible, records, start, end):
    window = [t for t in eligible if start <= t <= end]
    common = [t for t in window if str(t) in records]
    if not window or not common or common[0] != start or common[-1] != end:
        raise ValueError('Matched start/end decisions must be covered and recorded')
    if any(b-a != 900000 for a,b in zip(window, window[1:])):
        raise ValueError('Matched account window must be continuously covered')
    return window, set(common)


class RecordedDecisions:
    """Exogenous persisted decisions, not a claim of causal historical replay.

    Entry quality is recalculated from THIS fresh account's signal history.
    Old execution quotes and decision timestamps are never inherited.
    """
    def __init__(self, records):
        self.records = records

    def build_signal(self, context, prior_signals=()):
        from platform_v2.spot.domain.models.signal import SignalDecision, SignalSide, GateSnapshot, TheoreticalSetup
        from platform_v2.spot.services.signal.entry_quality_service import SpotEntryQualityService
        stamp = context.latest_candle.close_time_ms
        row = dict(self.records[str(stamp)])
        if row['timestamp_ms'] != stamp or row['symbol'] != context.symbol or row['timeframe'] != context.timeframe:
            raise ValueError('Recorded decision identity mismatch')
        row['side'] = SignalSide(row['side'])
        row['gates'] = GateSnapshot(**row['gates'])
        row['theoretical_setup'] = TheoreticalSetup(**row['theoretical_setup']) if row.get('theoretical_setup') else None
        row['reasons'] = tuple(row.get('reasons', ()))
        decision = SignalDecision(**row)
        history = [dict(p, side=p.get('evaluated_direction', 'NO_SIGNAL')) for p in prior_signals]
        quality = SpotEntryQualityService().evaluate(signal_side=decision.evaluated_direction,
            timestamp_ms=stamp, prior_signals=history)
        return replace(decision, entry_quality=asdict(quality), decision_time=None,
            execution_quote_price=None, execution_quote_time_ms=None, execution_quote_source=None)
