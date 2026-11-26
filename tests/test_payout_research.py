from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest

from numbers4_agent.payout_research import audit, box_group, evaluate, prior_estimates


def fixture(n=102, number="0123"):
    start = date(2020, 1, 1)
    rows = [{"round": i + 1, "draw_date": (start + timedelta(days=i)).isoformat(),
             "winning_number": number} for i in range(n)]
    return rows, [900000] * n, [37500] * n


class PayoutResearchTests(unittest.TestCase):
    def test_box_groups_and_leading_zero(self):
        self.assertEqual(box_group("0123"), "box_1111")
        self.assertEqual(box_group("0012"), "box_211")
        self.assertEqual(box_group("0011"), "box_22")
        self.assertEqual(box_group("0001"), "box_31")
        self.assertIsNone(box_group("0000"))

    def test_same_warmup_for_every_model(self):
        self.assertIsNone(prior_estimates([1] * 99))
        self.assertEqual(prior_estimates([100] * 100),
                         {"expanding_mean": 100, "rolling_30": 100, "rolling_100": 100})

    def test_current_and_future_payouts_not_training_features(self):
        rows, straight, box = fixture()
        straight[100] = 1200000
        straight[101] = 1500000
        box[100] = 47500
        result = evaluate(rows, straight, box, split_round=101)
        early = result["groups"]["straight"]["development"]
        self.assertEqual(early["evaluated_observations"], 1)
        for metrics in early["models"].values():
            self.assertEqual(metrics["mae_yen"], 300000)
            self.assertEqual(metrics["mean_error_yen"], -300000)
        self.assertEqual(result["groups"]["box_1111"]["development"]["models"]
                         ["rolling_30"]["mae_yen"], 10000)
        truncated = evaluate(rows[:101], straight[:101], box[:101], split_round=101)
        self.assertEqual(early, truncated["groups"]["straight"]["development"])

    def test_box_group_histories_are_separate(self):
        rows, straight, box = fixture()
        rows[-1]["winning_number"] = "0001"
        box[-1] = 225000
        result = evaluate(rows, straight, box)
        self.assertEqual(result["groups"]["box_1111"]["all"]["evaluated_observations"], 1)
        self.assertEqual(result["groups"]["box_31"]["all"]["evaluated_observations"], 0)
        self.assertEqual(result["groups"]["straight"]["all"]["evaluated_observations"], 2)

    def test_four_equal_draw_only_scores_straight(self):
        rows, straight, box = fixture()
        rows[-1]["winning_number"] = "0000"
        box[-1] = None
        result = evaluate(rows, straight, box)
        self.assertEqual(result["groups"]["box_1111"]["all"]["evaluated_observations"], 1)
        self.assertEqual(result["groups"]["straight"]["all"]["evaluated_observations"], 2)

    def test_bad_alignment_and_payout_fail_closed(self):
        rows, straight, box = fixture()
        with self.assertRaises(ValueError):
            evaluate(rows, straight[:-1], box)
        rows[-1]["winning_number"] = "0000"
        with self.assertRaises(ValueError):
            evaluate(rows, straight, box)
        rows[-1]["round"] = 1
        with self.assertRaises(ValueError):
            evaluate(rows, straight, box)

    def test_no_archive_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                audit(Path(directory))


if __name__ == "__main__":
    unittest.main()
