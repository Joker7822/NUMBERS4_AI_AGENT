"""Regression tests for exact, past-only rolling count updates."""
from collections import deque
from datetime import date, timedelta
from random import Random
import unittest
from unittest.mock import patch

from numbers4_agent import ensemble_audit, online_learning
from numbers4_agent.online_learning import RollingPositionCounts, positional_probs


class ReferenceWindow:
    """Original full-rescan implementation, used for exact equivalence tests."""
    def __init__(self, length):
        self.values = deque(maxlen=length)

    def append(self, number):
        self.values.append(number)

    def probabilities(self, alpha):
        return positional_probs(self.values, alpha)


def fixture(n):
    rng = Random(20261126)
    start = date(2020, 1, 1)
    return [{"round": i+1, "draw_date": (start+timedelta(days=i)).isoformat(),
             "winning_number": f"{rng.randrange(10000):04d}"} for i in range(n)]


class RollingCountsTests(unittest.TestCase):
    def test_exact_marginals_before_and_after_eviction(self):
        numbers = [r["winning_number"] for r in fixture(1105)]
        for length, alpha in ((1, 1), (60, 10), (250, 5), (1000, 20)):
            fast = RollingPositionCounts(length)
            slow = ReferenceWindow(length)
            self.assertEqual(fast.probabilities(alpha), slow.probabilities(alpha))
            for number in numbers:
                self.assertEqual(fast.probabilities(alpha), slow.probabilities(alpha))
                fast.append(number)
                slow.append(number)
            self.assertEqual(fast.probabilities(alpha), slow.probabilities(alpha))

    def test_invalid_append_is_atomic(self):
        window = RollingPositionCounts(1)
        window.append("0000")
        before = window.probabilities(1)
        for number in ("123", "abcd", "12345"):
            with self.assertRaises(ValueError):
                window.append(number)
            self.assertEqual(window.probabilities(1), before)
        with self.assertRaises(ValueError):
            window.probabilities(0)
        with self.assertRaises(ValueError):
            RollingPositionCounts(0)

    def test_repeated_digits_and_leading_zero(self):
        window = RollingPositionCounts(2)
        for number in ("0000", "1111", "0099"):
            window.append(number)
        self.assertEqual(window.probabilities(10), positional_probs(["1111", "0099"], 10))

    def test_full_replay_exactly_matches_original(self):
        rows = fixture(1200)
        result = online_learning.replay(rows)
        with patch.object(online_learning, "RollingPositionCounts", ReferenceWindow):
            reference = online_learning.replay(rows)
        self.assertEqual(result, reference)

    def test_ensemble_exactly_matches_original(self):
        rows = fixture(1200)
        result = ensemble_audit.evaluate(rows, split_round=1100)
        with patch.object(ensemble_audit, "RollingPositionCounts", ReferenceWindow):
            reference = ensemble_audit.evaluate(rows, split_round=1100)
        self.assertEqual(result, reference)


if __name__ == "__main__":
    unittest.main()
