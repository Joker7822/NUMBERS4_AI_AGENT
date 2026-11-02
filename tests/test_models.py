import unittest
from numbers4_agent.models import ranked_candidates, MODEL_REFERENCE, MODEL_RESEARCH
from numbers4_agent.rules import grade_number


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.history = [{"round": n, "winning_number": f"{(n*37+3)%10000:04d}"}
                        for n in range(1, 52)]

    def test_zero_data_is_not_fake_ai_confidence(self):
        report = ranked_candidates([], 100, count=5)
        self.assertEqual(report["model_version"], MODEL_REFERENCE)
        self.assertEqual(report["confidence"], "not_established")
        self.assertFalse(report["purchase_authorized"])
        self.assertEqual(len(set(report["numbers"])), 5)

    def test_positional_research_is_auditable_and_target_excluded(self):
        result = ranked_candidates(self.history, 52, mode="straight")
        self.assertEqual(result["model_version"], MODEL_RESEARCH)
        self.assertEqual(result["data_cutoff_round"], 51)
        self.assertEqual(result["numbers"], ranked_candidates(self.history,52)["numbers"])
        self.assertEqual(len(result["numbers"]),1)
        with self.assertRaisesRegex(ValueError,"look-ahead"):
            ranked_candidates(self.history, 51)

    def test_box_covers_different_digit_multisets(self):
        result = ranked_candidates(self.history, 52, mode="box")
        self.assertTrue(all(len(set(n))>1 for n in result["numbers"]))
        self.assertEqual(len({tuple(sorted(n)) for n in result["numbers"]}), 1)
        self.assertEqual(grade_number("0012","2010","box"),"box")
