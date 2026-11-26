from datetime import date, timedelta
from itertools import product
from math import fsum, log, prod
from pathlib import Path
import tempfile
import unittest

from numbers4_agent.ensemble_audit import (
    UNIFORM, audit, components, evaluate, joint_dot, mixture_score,
)


def fixture(n=1002):
    start = date(2020, 1, 1)
    return [{"round": i+1, "draw_date": (start+timedelta(days=i)).isoformat(),
             "winning_number": f"{(17*i)%10000:04d}"} for i in range(n)]


class EnsembleAuditTests(unittest.TestCase):
    def test_uniform_score_is_zero(self):
        masses, dots = components([UNIFORM], "0000")
        for value in mixture_score(masses, dots, (1.0,)):
            self.assertAlmostEqual(value, 0)

    def test_exact_joint_mixture_matches_enumeration(self):
        biased = [[.19]+[.09]*9 for _ in range(4)]
        experts = [UNIFORM, biased]
        w = (.4, .6)
        masses, dots = components(experts, "0000")
        q = [fsum(w[j]*prod(experts[j][i][d] for i, d in enumerate(ds))
                  for j in range(2))
             for ds in product(range(10), repeat=4)]
        self.assertAlmostEqual(fsum(q), 1)
        edge, brier = mixture_score(masses, dots, w)
        self.assertAlmostEqual(edge, log(q[0]/.0001))
        self.assertAlmostEqual(brier, 2*q[0]-fsum(p*p for p in q)-.0001)
        self.assertAlmostEqual(joint_dot(UNIFORM, biased), .0001)

    def test_past_only_and_common_evaluation(self):
        rows = fixture()
        original = evaluate(rows, split_round=1001)
        rows[-1]["winning_number"] = "9999"
        changed = evaluate(rows, split_round=1001)
        for name in original["models"]:
            self.assertEqual(original["models"][name]["development"],
                             changed["models"][name]["development"])
            self.assertEqual(changed["models"][name]["all"]["evaluated_draws"], 2)

    def test_insufficient_warmup(self):
        result = evaluate(fixture(1000))
        for model in result["models"].values():
            self.assertEqual(model["all"]["evaluated_draws"], 0)
            self.assertIsNone(model["all"]["mean_log_edge_vs_uniform"])

    def test_invalid_probabilities_and_weights(self):
        with self.assertRaises(ValueError):
            components([[[0.0]*10]*4], "1234")
        with self.assertRaises(ValueError):
            components([UNIFORM], "123")
        masses, dots = components([UNIFORM], "0123")
        for weights in ((0.9,), (-1.0,), (float("nan"),)):
            with self.assertRaises(ValueError):
                mixture_score(masses, dots, weights)

    def test_invalid_history(self):
        rows = fixture(3)
        rows[-1]["round"] = 1
        with self.assertRaises(ValueError):
            evaluate(rows)

    def test_missing_archive_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                audit(Path(directory))


if __name__ == "__main__":
    unittest.main()
