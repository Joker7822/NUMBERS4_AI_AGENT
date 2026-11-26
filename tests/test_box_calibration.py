from datetime import date, timedelta
from math import fsum
from pathlib import Path
import tempfile
import unittest

from numbers4_agent.box_calibration import (
    BASE_PATTERN_PROBS, INDEX, SIGNATURES, UNIFORM, audit, evaluate,
    posterior, score, signature,
)


def fixture(n=102):
    start = date(2020, 1, 1)
    return [{"round": i+1, "draw_date": (start+timedelta(days=i)).isoformat(),
             "winning_number": "0123"} for i in range(n)]


class BoxCalibrationTests(unittest.TestCase):
    def test_full_outcome_space_and_nonuniform_signature_baseline(self):
        self.assertEqual(len(SIGNATURES), 715)
        self.assertAlmostEqual(fsum(UNIFORM), 1)
        self.assertEqual(UNIFORM[INDEX["0123"]], .0024)
        self.assertEqual(UNIFORM[INDEX["0012"]], .0012)
        self.assertEqual(UNIFORM[INDEX["0011"]], .0006)
        self.assertEqual(UNIFORM[INDEX["0001"]], .0004)
        self.assertEqual(UNIFORM[INDEX["0000"]], .0001)

    def test_signature_preserves_zero_and_ignores_order(self):
        self.assertEqual(signature("3102"), "0123")
        with self.assertRaises(ValueError):
            signature("123")

    def test_pattern_probabilities(self):
        for actual, expected in zip(BASE_PATTERN_PROBS, (.504, .432, .027, .036, .001)):
            self.assertAlmostEqual(actual, expected)

    def test_prior_and_proper_score(self):
        counts = [0] * 715
        q = posterior(counts, 100)
        self.assertAlmostEqual(fsum(q), 1)
        a = INDEX["0123"]
        for edge in score(q, a):
            self.assertAlmostEqual(edge, 0)
        counts[a] = 10
        q = posterior(counts, 100)
        self.assertTrue(all(p > 0 for p in q))
        self.assertAlmostEqual(fsum(q), 1)
        self.assertGreater(score(q, a)[0], 0)
        self.assertLess(score(q, INDEX["0000"])[0], 0)

    def test_past_only_prefix_and_equal_scoring_counts(self):
        rows = fixture()
        first = evaluate(rows, split_round=101)
        rows[-1]["winning_number"] = "0000"
        changed = evaluate(rows, split_round=101)
        for name in first["models"]:
            self.assertEqual(first["models"][name]["development"],
                             changed["models"][name]["development"])
            self.assertEqual(changed["models"][name]["all"]["evaluated_draws"], 2)
            self.assertEqual(changed["models"][name]["late_historical"]
                             ["pattern_calibration"]["4"]["observed_frequency"], 1)

    def test_warmup_and_invalid_history(self):
        r = evaluate(fixture(99))
        self.assertEqual(r["models"]["uniform_ordered"]["all"]["evaluated_draws"], 0)
        rows = fixture()
        rows[-1]["round"] = 1
        with self.assertRaises(ValueError):
            evaluate(rows)
        with self.assertRaises(ValueError):
            posterior([0] * 715, 0)
        with self.assertRaises(ValueError):
            score(tuple([0.0] * 715), 0)

    def test_missing_archive_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                audit(Path(directory))


if __name__ == "__main__":
    unittest.main()
