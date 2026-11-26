from datetime import date, timedelta
from random import Random
import unittest
from unittest.mock import patch

from numbers4_agent import box_calibration as box
from numbers4_agent.benchmark_box_moments import ReferenceMoments, max_difference


class BoxMomentsTests(unittest.TestCase):
    def test_each_signature_matches_full_vector_before_and_after_updates(self):
        fast, slow = box.PosteriorMoments(), ReferenceMoments()
        rng = Random(20261126)
        for i in range(1000):
            actual = rng.randrange(len(box.SIGNATURES))
            for alpha in box.PRIOR_STRENGTHS:
                self.assertLessEqual(max_difference(fast.evaluate(actual, alpha),
                                                    slow.evaluate(actual, alpha)), 1e-12)
            fast.observe(actual)
            slow.observe(actual)
        for actual in range(len(box.SIGNATURES)):
            self.assertLessEqual(max_difference(fast.evaluate(actual, 100),
                                                slow.evaluate(actual, 100)), 1e-12)

    def test_invalid_index_or_prior_does_not_mutate_counts(self):
        fast = box.PosteriorMoments()
        fast.observe(box.INDEX["0000"])
        before = fast.evaluate(0, 100)
        for actual in (-1, 715, True):
            with self.assertRaises(ValueError):
                fast.observe(actual)
            with self.assertRaises(ValueError):
                fast.evaluate(actual, 100)
        for alpha in (0, -1, True):
            with self.assertRaises(ValueError):
                fast.evaluate(0, alpha)
        self.assertEqual(fast.evaluate(0, 100), before)

    def test_all_patterns_and_four_equal_are_included(self):
        fast, slow = box.PosteriorMoments(), ReferenceMoments()
        for value in ("0123", "0012", "0011", "0001", "0000") * 20:
            actual = box.INDEX[value]
            fast.observe(actual)
            slow.observe(actual)
            for alpha in box.PRIOR_STRENGTHS:
                self.assertLessEqual(max_difference(fast.evaluate(actual, alpha),
                                                    slow.evaluate(actual, alpha)), 1e-12)
                self.assertAlmostEqual(sum(fast.evaluate(actual, alpha)[2]), 1)

    def test_full_report_matches_reference(self):
        rng = Random(123)
        start = date(2020, 1, 1)
        rows = [{"round": i+1, "draw_date": (start+timedelta(days=i)).isoformat(),
                 "winning_number": f"{rng.randrange(10000):04d}"} for i in range(500)]
        result = box.evaluate(rows, split_round=300)
        with patch.object(box, "PosteriorMoments", ReferenceMoments):
            reference = box.evaluate(rows, split_round=300)
        self.assertLessEqual(max_difference(result, reference), 1e-12)


if __name__ == "__main__":
    unittest.main()
