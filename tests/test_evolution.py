"""Research evolution tests: online paper hints are NOT executable instructions."""
from collections import deque
from datetime import date, timedelta
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest

from numbers4_agent.evolution import (
    VERSION, JOURNAL, REPORT, ROUND_FIELDS, _EmaDigits, _MarkovDigits,
    _read_previous, _spec_id, _top_number, _validate_spec, choose_past_only,
    evaluate, next_queries, propose, cycle,
)
from numbers4_agent.online_learning import positional_probs
from numbers4_agent.store import append, canonical


def history(n=340):
    start = date(1994, 10, 7)
    return [
        {"round": i, "draw_date": (start + timedelta(days=i - 1)).isoformat(),
         "winning_number": f"{(7919 * i + 37) % 10000:04d}"}
        for i in range(1, n + 1)
    ]


def discovered(*titles):
    return {
        "candidates": [{
            "provider": "crossref", "id": f"10.1234/{i}",
            "source_url": f"https://doi.org/10.1234/{i}",
            "title": title, "research_categories": ["machine_learning"],
            "publication_year": 2024, "venue": "Some source",
            "external_claim_verified": False,
        } for i, title in enumerate(titles)]
    }


class SelfEvolutionTests(unittest.TestCase):
    def test_paper_keywords_propose_only_preimplemented_bounded_methods(self):
        specs, citations = propose(discovered(
            "Markov transition models for time series",
            "Exponential decay online forecast calibration",
            "Bayesian Dirichlet smoothing and drift",
            "eval('__import__(\"os\").system(\"touch /tmp/unsafe\")')"),
            generation=1)
        self.assertTrue(any(x["family"] == "markov" for x in specs))
        self.assertTrue(any(x["family"] == "ema" for x in specs))
        self.assertTrue(any(x["family"] == "rolling" for x in specs))
        self.assertLessEqual(len(specs), 8)
        self.assertTrue(all(_validate_spec(spec) == spec for spec in specs))
        self.assertTrue(all(x["claimed_predictive_ability_verified"] is False
                            for x in citations))
        self.assertTrue(all(x["full_paper_independently_reviewed"] is False
                            for x in citations))
        self.assertEqual(len({_spec_id(spec) for spec in specs}),len(specs))
        with self.assertRaises(ValueError):
            _validate_spec({"family": "arbitrary_external_script", "url": "https://x"})
        with self.assertRaises(ValueError):
            _validate_spec({"family": "rolling", "window": 999999, "alpha": 5})
        with self.assertRaises(ValueError):
            _validate_spec({"family": "ema", "decay": 0.1, "alpha": 5})

    def test_recursive_feedback_mutates_prior_development_winner(self):
        first, _ = propose(discovered(), generation=1)
        prior = {"model_specs": first, "development_winner": {
            "model": _spec_id(first[0])}}
        next_specs, _ = propose(discovered(), previous=prior, generation=2)
        self.assertGreaterEqual(len(next_specs), 4)
        self.assertIn({"family": "rolling", "window": 60, "alpha": 20}, next_specs)
        self.assertIn("Dirichlet", next_queries(prior)[1])
        prior["development_winner"]["model"] = "uniform"
        self.assertIn("data snooping", next_queries(prior)[1])
        fallback_specs, _ = propose(discovered(), previous=prior, generation=2)
        self.assertIn({"family": "rolling", "window": 60, "alpha": 20},
                      fallback_specs)
        self.assertGreaterEqual(len(fallback_specs), 4)

    def test_decay_training_matches_weighted_counts_and_markov_has_no_lookahead(self):
        ema = _EmaDigits(.99, 5)
        self.assertEqual(ema.probabilities()[0], [.1] * 10)
        for value in ("0000", "1234", "0000"):
            ema.append(value)
        for line in ema.probabilities():
            self.assertAlmostEqual(sum(line), 1.0)
        model = _MarkovDigits(30, 5)
        self.assertEqual(_top_number(model.probabilities()), "0000")
        for value in ("1234", "5678", "1234", "5678"):
            model.append(value)
        predicted = model.probabilities()
        self.assertEqual(_top_number(predicted), "1234")
        self.assertTrue(all(abs(sum(line)-1) < 1e-10 for line in predicted))

    def test_every_number_from_draw_two_is_selected_before_current_result(self):
        sample = history(340)
        specs,_ = propose(discovered("Markov transitions", "decay trend"),generation=1)
        before, records = evaluate(sample, specs, split_round=200)
        self.assertEqual(len(records), 339)
        self.assertEqual(records[0]["round"], 2)
        self.assertEqual(records[0]["data_cutoff_round"], 1)
        self.assertEqual(records[-1]["data_cutoff_round"], 339)
        self.assertTrue(all(len(row["selected_number"]) == 4 for row in records))
        self.assertTrue(all(row["selected_hit"] == int(
            row["selected_number"] == row["actual"]) for row in records))
        self.assertTrue(all(row["uniform_hit"] == int(
            row["uniform_number"] == row["actual"]) for row in records))
        altered = history(340)
        altered[-1]["winning_number"] = (
            "0000" if altered[-1]["winning_number"] != "0000" else "0001")
        after, records_changed = evaluate(altered, specs, split_round=200)
        self.assertEqual(before["development"], after["development"])
        self.assertEqual(records[-1]["selected_number"],
                         records_changed[-1]["selected_number"])
        self.assertEqual(records[-1]["research_selected_model"],
                         records_changed[-1]["research_selected_model"])
        self.assertEqual(records[:-1], records_changed[:-1])
        self.assertFalse(after["performance_advantage_confirmed"])
        self.assertEqual(after["genuine_prospective_independently_verified_draws"],0)
        self.assertFalse(after["production_model_changed"])
        self.assertTrue(after["model_family_devised_after_historical_outcomes"])

    def test_rolling_selector_protects_against_past_negative_scores(self):
        past = {
            "rolling_60_alpha10": deque([-0.2] * 250, maxlen=250),
            "ema_0p99_alpha10": deque([.2] * 250, maxlen=250),
        }
        self.assertEqual(choose_past_only(past), "ema_0p99_alpha10")
        past["ema_0p99_alpha10"] = deque([-.02] * 250,maxlen=250)
        self.assertEqual(choose_past_only(past), "uniform")
        past["rolling_60_alpha10"] = deque([.2] * 249,maxlen=250)
        self.assertEqual(choose_past_only(past), "uniform")

    def test_invalid_chronology_and_future_use_rejected(self):
        specs, _ = propose(discovered())
        for split in (0, 1, 340, True):
            with self.assertRaises(ValueError):
                evaluate(history(340), specs, split_round=split)
        invalid = history(20)
        invalid[4]["round"] = 7
        with self.assertRaisesRegex(ValueError,"sequential"):
            evaluate(invalid,specs,split_round=10)
        with self.assertRaises(ValueError):
            evaluate(history(10),[specs[0],specs[0]],split_round=5)

    def test_journal_sha_chain_detects_tampering_and_no_provenance_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                cycle(root, offline=True, split_round=10)
            self.assertFalse((root/REPORT).exists())
            self.assertFalse((root/JOURNAL).exists())
            report = {"version":VERSION,"generation":1,
                      "archive_latest_round":20,"model_specs":[],
                      "development_winner":{"model":"uniform"}}
            path=root/REPORT
            path.parent.mkdir(parents=True,exist_ok=True)
            raw=json.dumps(report)
            path.write_text(raw,encoding="utf-8")
            append(root/JOURNAL,{"report_sha256":sha256(raw.encode()).hexdigest(),
                                 "generation":1})
            state, old = _read_previous(root)
            self.assertEqual(len(state),1)
            self.assertEqual(old["generation"],1)
            path.write_text(raw+" ",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"hash diverges"):
                _read_previous(root)


if __name__ == "__main__":
    unittest.main()
