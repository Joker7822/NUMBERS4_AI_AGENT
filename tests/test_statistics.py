"""Regression tests for descriptive chance benchmarks, not forecasting claims."""
import math
import unittest
from datetime import date, timedelta

from numbers4_agent.statistics import binomial_right_tail
from numbers4_agent.online_learning import replay


class StatisticalAuditTests(unittest.TestCase):
    def test_binomial_survival_exact_small_cases(self):
        self.assertAlmostEqual(binomial_right_tail(2, 1, 0.5), 0.75)
        self.assertAlmostEqual(binomial_right_tail(2, 2, 0.5), 0.25)
        self.assertAlmostEqual(binomial_right_tail(10, 1, 0.1), 1 - 0.9**10)
        self.assertEqual(binomial_right_tail(10, 0, 0.1), 1.0)
        self.assertEqual(binomial_right_tail(10, 1, 0.0), 0.0)
        self.assertEqual(binomial_right_tail(10, 1, 1.0), 1.0)
        self.assertAlmostEqual(binomial_right_tail(7103, 5, 0.0005),
                               0.284292006, places=8)

    def test_input_validation(self):
        for trials, hits, probability in [
            (-1, 0, 0.5), (2, -1, 0.5), (2, 3, 0.5),
            (2, 1, -0.1), (2, 1, 1.1), (True, 1, 0.5),
        ]:
            with self.assertRaises(ValueError):
                binomial_right_tail(trials, hits, probability)

    def test_replay_reports_honest_descriptive_scope(self):
        start=date(1994, 10, 7)
        rows=[{'round':i,
               'draw_date':(start+timedelta(days=i-1)).isoformat(),
               'winning_number':f'{(i * 7919) % 10000:04d}'}
              for i in range(1, 127)]
        report, grades=replay(rows)
        audit=report['research_statistical_audit']
        self.assertEqual(audit['scope'],
                         'descriptive_historical_reconstruction_not_preregistered')
        self.assertFalse(audit['statistical_significance_is_prospective_proof'])
        self.assertEqual(audit['nonuniform_model_selected_rounds'],
                         sum(g['selected_model']!='uniform' for g in grades))
        self.assertEqual(audit['selected_only_hits_vs_uniform_reference'],
                         sum(g['selected_hit'] and not g['uniform_hit'] for g in grades))
        self.assertEqual(audit['uniform_reference_only_hits_vs_selected'],
                         sum(g['uniform_hit'] and not g['selected_hit'] for g in grades))
        self.assertAlmostEqual(
            audit['selected_hit_tail_probability_given_uniform_null'],
            binomial_right_tail(125, report['selected_straight_hits'], .0001),
            places=8,
        )


if __name__ == '__main__':
    unittest.main()
