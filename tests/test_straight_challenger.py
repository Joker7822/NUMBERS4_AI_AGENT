"""Regression coverage for no-lookahead, exact rolling counts and honest research labels."""
from collections import deque
from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest

from numbers4_agent.online_learning import positional_probs, uniform_numbers
from numbers4_agent.straight_challenger import (
    RollingDigits, GUARD_LOOKBACK, BASELINE, GATED, SPECS,
    evaluate, guard_choice, write_report,
)


def fixture(n=340):
    start = date(1994, 10, 7)
    return [
        {"round": i, "draw_date": (start + timedelta(days=i - 1)).isoformat(),
         "winning_number": f"{(7919 * i + 37) % 10000:04d}"}
        for i in range(1, n + 1)
    ]


class StraightChallengerTests(unittest.TestCase):
    def test_rolling_counts_match_reference_even_after_eviction(self):
        for size, alpha in [(3, 1), (60, 10), (250, 20)]:
            rolling = RollingDigits(size, alpha)
            seen = []
            for i in range(size + 25):
                value = f"{(i * 7919) % 10000:04d}"
                seen.append(value)
                rolling.append(value)
                expected = positional_probs(seen[-size:], alpha)
                for a, b in zip(rolling.probabilities(), expected):
                    for x, y in zip(a, b):
                        self.assertAlmostEqual(x, y, places=14)

    def test_guard_requires_past_positive_evidence(self):
        prior = {name: deque([-0.1] * GUARD_LOOKBACK,
                             maxlen=GUARD_LOOKBACK) for name, _, _ in SPECS}
        self.assertEqual(guard_choice(prior), BASELINE)
        prior[SPECS[0][0]] = deque([0.2] * GUARD_LOOKBACK,
                                  maxlen=GUARD_LOOKBACK)
        self.assertEqual(guard_choice(prior), SPECS[0][0])
        prior[SPECS[0][0]] = deque([0.2] * (GUARD_LOOKBACK - 1),
                                  maxlen=GUARD_LOOKBACK)
        self.assertEqual(guard_choice(prior), BASELINE)

    def test_split_does_not_know_future(self):
        rows = fixture(340)
        baseline = evaluate(rows, split_round=200)
        altered = fixture(340)
        altered[-1]["winning_number"] = (
            "0000" if altered[-1]["winning_number"] != "0000" else "0001")
        subsequent = evaluate(altered, split_round=200)
        self.assertEqual(baseline["development"], subsequent["development"])
        self.assertEqual(baseline["retrospective_holdout"]["first_round"], 201)
        self.assertEqual(baseline["retrospective_holdout"]["last_round"], 340)
        self.assertFalse(baseline["forecast_skill_confirmed"])
        self.assertEqual(baseline["genuine_prospective_verified_draws"], 0)
        for cohort in ("development", "retrospective_holdout"):
            models = baseline[cohort]["models"]
            self.assertIn(BASELINE, models)
            self.assertIn(GATED, models)
            for result in models.values():
                self.assertFalse(result["performance_advantage_confirmed"])
                self.assertGreaterEqual(
                    result["selected_only_hits_vs_fixed_uniform_reference"], 0)
                self.assertTrue(0 <= result["uniform_null_hit_tail_p_exploratory"] <= 1)
                self.assertTrue(0 <= result["paired_exact_discordance_p_exploratory"] <= 1)

    def test_malformed_chronology_and_split_fail(self):
        for split in (0, 1, 340, 341, True):
            with self.assertRaises(ValueError):
                evaluate(fixture(340), split_round=split)
        bad = fixture(30)
        bad[5]["round"] = 30
        with self.assertRaisesRegex(ValueError, "complete and sequential"):
            evaluate(bad, split_round=20)
        bad = fixture(30)
        bad[10]["winning_number"] = "999"
        with self.assertRaises(ValueError):
            evaluate(bad, split_round=20)

    def test_research_output_does_not_touch_published_predictions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data").mkdir()
            # Missing source provenance must fail closed.
            with self.assertRaises(ValueError):
                write_report(root, output=Path("research/challenger.json"),
                             split_round=20)
            self.assertFalse((root / "research/challenger.json").exists())
            self.assertFalse((root / "data/issued_forecasts.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
