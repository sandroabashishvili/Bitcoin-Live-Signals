"""Small, explicit score-only research candidates; no mandatory component gates."""
from dataclasses import dataclass
import math

COMPONENTS = ('mtf', 'regime', 'trend', 'momentum', 'orderbook', 'structure')


@dataclass(frozen=True)
class Calibration:
    name: str
    side: str = 'SHORT'
    component: str | None = None
    multiplier: float = 1.0
    adjustment: str | None = None


def candidates():
    yield Calibration('baseline')
    for side in ('LONG', 'SHORT'):
        for component in COMPONENTS:
            for multiplier in (0.75, 1.25):
                yield Calibration(f'{side}_{component}_{multiplier}', side, component, multiplier)
    for adjustment in ('macd_no_counter_reward', 'regime_slope_discount', 'structure_no_rejection_discount'):
        yield Calibration(adjustment, adjustment=adjustment)


def weights_for(base, candidate, side):
    weights = dict(base)
    if side != candidate.side or candidate.component is None:
        return weights
    if candidate.multiplier <= 0 or not math.isfinite(candidate.multiplier):
        raise ValueError('Weight multiplier must be positive and finite')
    weights[candidate.component] *= candidate.multiplier
    factor = sum(base.values()) / sum(weights.values())
    return {name: value*factor for name, value in weights.items()}


def components_for(base, candidate, side, snapshot):
    scores = dict(base)
    if side != candidate.side:
        return scores
    if candidate.adjustment == 'macd_no_counter_reward':
        macd, signal, atr = snapshot.get('macd'), snapshot.get('macd_signal'), snapshot.get('atr')
        if macd is not None and signal is not None and atr and macd > signal:
            spread = (signal-macd)/atr
            scores['momentum'] = max(0.0, scores['momentum']-(0.8 if spread >= -0.2 else 0.2))
    elif candidate.adjustment == 'regime_slope_discount':
        slope = snapshot.get('adx_slope')
        if slope is not None and slope < 0:
            scores['regime'] *= 0.5
    elif candidate.adjustment == 'structure_no_rejection_discount':
        # Unknown confirmation is not assumed false.
        rejection = snapshot.get('rejection_confirmed')
        if rejection is False:
            scores['structure'] *= 0.75
    return scores


def weighted_score(components, weights):
    # Preserve the production left-to-right addition order.
    total = 0.0
    for name in COMPONENTS:
        total += components.get(name, 0.0)*weights[name]
    return round(total, 2)


def archived_score_delta(stored_total, original_components, original_weights,
                         candidate_components, candidate_weights):
    """Preserve archived controls despite rounded serialized components.

    This is an archived-score experiment, not a fresh runtime signal replay.
    """
    return round(stored_total + weighted_score(candidate_components, candidate_weights)
                 - weighted_score(original_components, original_weights), 2)
