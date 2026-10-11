import unittest

from platform_v2.tools.research.replay.futures_component_screen import (
    choose, changed_scores, next_minute, summarize, evaluate, COMPONENTS,
)


def record():
    return {'direction_scores': {'long': 9.01, 'short': 8.6},
            'direction_thresholds': {'long': 8.5, 'short': 8.5},
            'direction_component_scores': {d: {c: 2.0 for c in COMPONENTS} for d in ('long','short')},
            'direction_component_weights': {d: {c: 1.0 for c in COMPONENTS} for d in ('long','short')},
            'direction_gates': {d: {c: True for c in COMPONENTS} for d in ('long','short')}}


class ComponentScreenTests(unittest.TestCase):
    def test_long_wins_qualifying_tie(self):
        self.assertEqual('LONG', choose({'long': 8.5, 'short': 8.5}, {'long': 8.5, 'short': 8.5}))

    def test_short_must_qualify_and_exceed_long(self):
        self.assertEqual('SHORT', choose({'long': 8.4, 'short': 8.6}, {'long': 8.5, 'short': 8.5}))
        self.assertEqual('NO_SIGNAL', choose({'long': 8.4, 'short': 8.3}, {'long': 8.5, 'short': 8.5}))

    def test_weight_removal_keeps_other_direction_and_residual(self):
        source = record()
        scores = changed_scores(source, 'long', 'momentum', 0)
        self.assertEqual({'long': 7.01, 'short': 8.6}, scores)
        self.assertEqual(9.01, source['direction_scores']['long'])

    def test_half_and_increase_are_relative_to_persisted_weight(self):
        source = record()
        source['direction_component_weights']['short']['mtf'] = .8
        self.assertEqual(7.8, changed_scores(source, 'short', 'mtf', .5)['short'])
        self.assertEqual(9.4, changed_scores(source, 'short', 'mtf', 1.5)['short'])

    def test_baseline_retains_exact_scores(self):
        self.assertEqual(record()['direction_scores'], changed_scores(record()))

    def test_next_minute_strictly_after_availability(self):
        self.assertEqual(120000, next_minute(60000))
        self.assertEqual(120000, next_minute(119999))

    def test_empty_stats_unknown_not_zero_success(self):
        self.assertIsNone(summarize([])['positive_rate_pct'])
        self.assertEqual(50, summarize([-1,1])['positive_rate_pct'])

    def test_missing_exact_endpoint_not_interpolated(self):
        protocol = {'components': list(COMPONENTS), 'directions': ['long','short'],
                    'relative_weight_factors': [0,.5,1.5], 'horizons_minutes': [15,60,240]}
        eligible = [{'observation_id': 1, 'available_ms': 60001, 'entry_ms': 120000, 'record': record()}]
        result = evaluate(protocol, eligible, 0, {120000:100, 960000:101})
        self.assertEqual(0, result['label_availability']['15']['usable_decisions'])
        self.assertEqual(1, result['label_availability']['15']['excluded']['missing_endpoint'])
        self.assertEqual(37, len(result['results']))
        self.assertFalse(any(c['qualifies_for_replay_screen_only'] for contexts in result['replay_screen_leads'].values() for c in contexts.values()))


if __name__ == '__main__':
    unittest.main()
