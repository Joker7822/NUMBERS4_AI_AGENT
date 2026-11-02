"""Anti-leakage and online selection regression tests."""
import unittest
import random
import math
from datetime import date,timedelta
from numbers4_agent.online_learning import replay,best_five,uniform_numbers,grade_prob,positional_probs,VERSION


def fixture(n=125):
    start=date(1994,10,7)
    return [{'round':i,'draw_date':(start+timedelta(days=i-1)).isoformat(),
             'winning_number':f'{((7919*i) % 10000):04d}'} for i in range(1,n+1)]


class OnlineLearningTests(unittest.TestCase):
    def test_round_two_is_first_prediction_no_lookahead(self):
        rows=fixture(125)
        report,grades=replay(rows)
        self.assertEqual(report['evaluated_draws'],124)
        self.assertEqual((grades[0]['round'],grades[0]['data_cutoff_round']),(2,1))
        self.assertEqual(grades[-1]['data_cutoff_round'],124)
        self.assertEqual(report['genuine_prospective_verified_draws'],0)
        self.assertFalse(report['prediction_skill_confirmed'])
        self.assertFalse(report['forecast_grading_authorized'])
        self.assertEqual(report['version'],VERSION)
        self.assertEqual(set(grades[0]['selected_numbers'].split()),set(uniform_numbers(2)))
        self.assertEqual(len(grades),124)
        self.assertEqual(sum(x['selected_hit'] for x in grades), report['selected_straight_hits'])

    def test_future_edits_cannot_change_earlier_predictions(self):
        rows=fixture(122)
        _,before=replay(rows)
        rows[-1]['winning_number']='0000' if rows[-1]['winning_number']!='0000' else '0001'
        _,after=replay(rows)
        self.assertEqual(before[:-1],after[:-1])
        self.assertEqual(before[-1]['selected_numbers'],after[-1]['selected_numbers'])
        self.assertEqual(before[-1]['uniform_numbers'],after[-1]['uniform_numbers'])

    def test_critical_history_integrity(self):
        rows=fixture(15)
        del rows[5]
        with self.assertRaisesRegex(ValueError,'complete and sequential'):
            replay(rows)
        rows=fixture(15);rows[4]['winning_number']='123'
        with self.assertRaises(ValueError):replay(rows)
        rows=fixture(15);rows[3]['draw_date']=rows[2]['draw_date']
        with self.assertRaises(ValueError):replay(rows)

    def test_fast_exact_top5_matches_brute_force(self):
        for seed in range(12):
            rng=random.Random(seed)
            q=[]
            for _ in range(4):
                values=[rng.randrange(1,100) for _ in range(10)]
                total=sum(values)
                q.append([x/total for x in values])
            want=sorted((f'{n:04d}' for n in range(10000)),
                        key=lambda n:(-math.prod(q[i][int(d)] for i,d in enumerate(n)),n))[:5]
            self.assertEqual(best_five(q),want)
        self.assertEqual(best_five([[.1]*10 for _ in range(4)]),['0000','0001','0002','0003','0004'])

    def test_baseline_prob_and_determinism(self):
        q=[[.1]*10 for _ in range(4)]
        self.assertAlmostEqual(grade_prob(q,'0000')[0],0,places=12)
        self.assertAlmostEqual(grade_prob(q,'0000')[1],0,places=12)
        self.assertEqual(uniform_numbers(100),uniform_numbers(100))
        self.assertEqual(len(set(uniform_numbers(100))),1)
        self.assertNotEqual(uniform_numbers(100),uniform_numbers(101))
        self.assertTrue(all(len(n)==4 for n in uniform_numbers(100)))
        self.assertTrue(all(len(p)==10 and abs(sum(p)-1)<1e-9 for p in positional_probs(['0000','1299'],5)))


if __name__ == '__main__':unittest.main()
