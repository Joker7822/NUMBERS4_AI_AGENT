from datetime import date, timedelta
from random import Random
import unittest
from unittest.mock import patch

from numbers4_agent import payout_research as p
from numbers4_agent.benchmark_payout_totals import ReferenceTotals


class PayoutTotalsTests(unittest.TestCase):
    def test_exact_estimates_for_every_prefix_and_eviction(self):
        rng = Random(20261126)
        fast, slow = p.PayoutTotals(), ReferenceTotals()
        for _ in range(1500):
            self.assertEqual(fast.estimates(), slow.estimates())
            self.assertEqual(len(fast), len(slow))
            value = rng.randrange(1, 20000001)
            fast.append(value)
            slow.append(value)
        self.assertEqual(fast.estimates(), slow.estimates())

    def test_invalid_values_fail_without_state_change(self):
        fast = p.PayoutTotals()
        for _ in range(100):
            fast.append(900000)
        before = fast.estimates()
        for bad in (0, -1, True, None, 1.5):
            with self.assertRaises(ValueError):
                fast.append(bad)
            self.assertEqual(fast.estimates(), before)
            self.assertEqual(len(fast), 100)

    def test_complete_report_exact_with_all_box_patterns(self):
        rng = Random(12)
        start = date(2020, 1, 1)
        numbers = ("0123", "0012", "0011", "0001", "0000")
        rows, straight, box = [], [], []
        for i in range(1200):
            number = numbers[i % 5]
            rows.append({"round": i+1, "draw_date": (start+timedelta(days=i)).isoformat(),
                         "winning_number": number})
            straight.append(rng.randrange(200000, 2000001))
            box.append(None if number == "0000" else rng.randrange(1000, 1000000))
        result = p.evaluate(rows, straight, box, split_round=700)
        with patch.object(p, "PayoutTotals", ReferenceTotals):
            reference = p.evaluate(rows, straight, box, split_round=700)
        self.assertEqual(result, reference)
        self.assertEqual(result["groups"]["straight"]["all"]["evaluated_observations"], 1100)
        self.assertEqual(result["groups"]["box_31"]["all"]["evaluated_observations"], 140)

    def test_past_only_and_bounded_windows(self):
        fast = p.PayoutTotals()
        for _ in range(100):
            fast.append(100)
        self.assertEqual(fast.estimates(), p.prior_estimates([100]*100))
        for _ in range(200):
            fast.append(200)
        self.assertEqual(fast.estimates(), p.prior_estimates([100]*100+[200]*200))
        self.assertEqual(len(fast._windows[30]), 30)
        self.assertEqual(len(fast._windows[100]), 100)


if __name__ == "__main__":
    unittest.main()
