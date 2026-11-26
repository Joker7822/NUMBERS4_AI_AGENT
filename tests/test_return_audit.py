import tempfile
import unittest
from pathlib import Path

from numbers4_agent.return_audit import audit, benchmark, recovery_percent, uniform_events


class ReturnAuditTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"round": 1, "winning_number": "1111"},
            {"round": 2, "winning_number": "0123"},
            {"round": 3, "winning_number": "0011"},
            {"round": 4, "winning_number": "0000"},
        ]
        self.straight = [900000] * 4
        self.box = [None, 37500, 150000, None]

    def test_exact_straight_moments(self):
        events = uniform_events(self.rows, self.straight, self.box, "straight")
        self.assertEqual(events, [(0.0001, 900000)] * 3)
        result = benchmark(events, simulations=100, seed=7)
        self.assertAlmostEqual(result["expected_gross_recovery_percent"], 45)
        self.assertAlmostEqual(result["expected_net_roi_percent"], -55)
        self.assertAlmostEqual(result["expected_hits"], 0.0003)

    def test_box_permutations_and_all_equal(self):
        events = uniform_events(self.rows, self.straight, self.box, "box")
        self.assertEqual(events, [(24/9990, 37500), (6/9990, 150000), (0, 0)])
        result = benchmark(events, simulations=100, seed=7)
        self.assertEqual(result["hypothetical_spend_yen"], 600)
        self.assertAlmostEqual(result["expected_payout_yen"], 1800000/9990)

    def test_seed_is_reproducible(self):
        events = [(0.01, 10000)] * 20
        a = benchmark(events, simulations=1000, seed=42)
        b = benchmark(events, simulations=1000, seed=42)
        self.assertEqual(a, b)
        q = a["simulated_gross_recovery_quantiles_percent"]
        self.assertLessEqual(q["p025"], q["p50"])
        self.assertLessEqual(q["p50"], q["p975"])

    def test_zero_probability_and_zero_spend(self):
        result = benchmark([(0, 0)] * 3, simulations=10)
        self.assertEqual(result["expected_gross_recovery_percent"], 0)
        self.assertEqual(result["simulated_zero_payout_fraction"], 1)
        self.assertIsNone(recovery_percent(0, 0))

    def test_missing_or_ineligible_payout_fails(self):
        with self.assertRaises(ValueError):
            uniform_events(self.rows, self.straight, [None, None, 150000, None], "box")
        with self.assertRaises(ValueError):
            uniform_events(self.rows, self.straight, [None, 37500, 150000, 500], "box")

    def test_invalid_input_fails(self):
        for invalid in (0, -1, 100001, True):
            with self.assertRaises(ValueError):
                benchmark([(0.1, 1)], simulations=invalid)
        with self.assertRaises(ValueError):
            benchmark([(1.1, 100)])
        with self.assertRaises(ValueError):
            uniform_events(self.rows, self.straight, self.box, "set")

    def test_missing_archive_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                audit(Path(directory))


if __name__ == "__main__":
    unittest.main()
