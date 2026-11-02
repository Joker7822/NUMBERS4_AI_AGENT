"""Research-method discovery is untrusted input; tests never call the internet."""
import json
import unittest
from datetime import datetime, timedelta, timezone

from numbers4_agent.research_discovery import (
    DEFAULT_TOPICS, discover, _crossref_entries, _brave_entries,
    _model_assessment, _queries, _research_method_signals,
)

NOW=datetime(2026,11,2,17,30,tzinfo=timezone(timedelta(hours=9)))


def academic(url):
    return json.dumps({"message":{"items":[
      {"DOI":"10.1000/182","title":["Lottery randomness and forecast evaluation"],
       "published":{"date-parts":[[2021,8,1]]},
       "container-title":["Research journal"],"relation":{}},
      {"DOI":"10.1000/182","title":["Lottery randomness and forecast evaluation"]},
      {"DOI":"not-a-doi","title":["Lottery prediction system"]},
      {"DOI":"10.1000/183","title":["Unrelated forest soil analysis"]},
    ]}}).encode()


def web(url,token):
    assert token=="test-secret"
    return json.dumps({"web":{"results":[
      {"url":"https://papers.example.org/forecast","title":"Machine learning lottery forecasting",
       "description":"Time series data snooping and out-of-sample testing"},
      {"url":"http://127.0.0.1/admin","title":"Lottery chance exploit","description":"private"},
    ]}}).encode()


class PredictiveResearchTests(unittest.TestCase):
    def test_distinct_academic_and_web_hypotheses_are_unverified(self):
        report=discover(["lottery prediction"],crossref_fetch=academic,
                        brave_fetch=web,brave_api_key="test-secret",now=NOW)
        self.assertEqual(report["candidate_count"],2)
        self.assertEqual(report["providers_attempted"],["crossref","brave_web_search"])
        self.assertEqual(report["errors"],[])
        self.assertFalse(report["official_results_verified"])
        self.assertFalse(report["automatic_production_model_promotion"])
        self.assertTrue(all(not x["external_claim_verified"] and
                            not x["reproducible_lottery_edge_verified"]
                            for x in report["candidates"]))
        self.assertNotIn("test-secret",json.dumps(report))
        self.assertEqual(report["candidates"][0]["publication_year"],2021)

    def test_academic_only_does_not_fake_full_web_search(self):
        report=discover(["forecast evaluation"],crossref_fetch=academic,now=NOW)
        self.assertFalse(report["web_search_enabled"])
        self.assertEqual(report["providers_attempted"],["crossref"])
        self.assertEqual(report["candidate_count"],1)

    def test_unavailable_provider_is_reported_without_promoting(self):
        def unreachable(url): raise OSError("offline")
        report=discover(["lottery"],crossref_fetch=unreachable,now=NOW)
        self.assertEqual(report["candidate_count"],0)
        self.assertEqual(report["errors"][0]["error_type"],"OSError")
        self.assertFalse(report["automatic_code_execution_from_sources"])

    def test_nonpublic_search_results_are_rejected(self):
        r=_brave_entries({"web":{"results":[
            {"title":"Lottery model","url":"https://127.0.0.1/predictions"},
            {"title":"Lottery analysis","url":"https://valid.org/?api_key=secret"},
        ]}},"lottery")
        self.assertEqual(r,[])

    def test_run_research_literature_cannot_modify_model_selection(self):
        report={"retrospective_holdout":{"models":{
            "uniform":{"mean_log_score_edge_vs_uniform":0,
                       "top5_straight_hits":0, "straight_hits":0,
                       "evaluated_draws":1000,"paired_exact_discordance_p_exploratory":1},
            "positional":{"mean_log_score_edge_vs_uniform":0.01,
                          "straight_hits":3, "evaluated_draws":1000,
                          "paired_exact_discordance_p_exploratory":0.02},
        }}}
        assessments=_model_assessment(report)
        self.assertTrue(assessments["positional"]["exploratory_screen_passed"])
        self.assertFalse(assessments["positional"]["eligible_for_production"])
        self.assertFalse(assessments["positional"]["prospective_independent_confirmation"])

    def test_abstract_method_signals_without_republishing_copyrighted_abstract(self):
        raw="<jats:p>One-step Markov transition probabilities and concept drift</jats:p>"
        data={"message":{"items":[{
            "DOI":"10.9999/lottery-model",
            "title":["Lottery sequential statistical forecasting"],
            "abstract":raw,
            "container-title":["Research journal"],
            "published":{"date-parts":[[2023,2,1]]},
        }]}}
        results=_crossref_entries(data,"lottery")
        self.assertEqual(len(results),1)
        self.assertTrue(results[0]["abstract_metadata_present"])
        self.assertIn("markov",results[0]["method_signals"])
        self.assertIn("temporal_decay",results[0]["method_signals"])
        self.assertNotIn("abstract",results[0])
        self.assertNotIn(raw,json.dumps(results))
        self.assertFalse(results[0]["external_claim_verified"])
        self.assertEqual(_research_method_signals("unrelated text"),[])

    def test_no_unbounded_query_count_or_credentials(self):
        for query in ([""], ["a\nb"], ["x"*251], []):
            with self.assertRaises(ValueError):
                _queries(query)
        with self.assertRaises(ValueError):
            _queries(["lottery"]*9)


if __name__=="__main__":
    unittest.main()
