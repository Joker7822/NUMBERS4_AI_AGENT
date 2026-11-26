"""Unlimited cumulative source collection, provider page bounds, resumability."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import json
import tempfile
import unittest
from unittest.mock import patch

from numbers4_agent.research_acquisition import (
    VERSION, SOURCE_LEDGER, PROGRESS_PATH, collect, persist, _seen,
)
from numbers4_agent.research_discovery import (
    RESULTS_PER_QUERY, _crossref_request, _brave_request, _queries,
)
from numbers4_agent.store import load

NOW = datetime(2026, 11, 2, 19, tzinfo=timezone(timedelta(hours=9)))
TOMORROW = NOW + timedelta(days=1)


def crossref_page(url):
    query = parse_qs(urlsplit(url).query)
    offset = int(query["offset"][0])
    count = 20 if offset == 0 else 2 if offset == 20 else 0
    return json.dumps({"message":{"items":[
        {"DOI":f"10.1234/method-{i}","title":["Lottery Bayesian Markov forecast"],
         "container-title":["Journal"],"published":{"date-parts":[[2020,1,1]]}}
        for i in range(offset,offset+count)
    ]}}).encode()


def brave_page(url, key):
    assert key == "dummy-token"
    query=parse_qs(urlsplit(url).query)
    off=int(query["offset"][0])
    return json.dumps({
        "web":{"results":[{
            "url":f"https://papers.example.net/method/{i}",
            "title":"Markov transition lottery prediction",
            "description":"Probabilistic forecast calibration"} for i in range(off*20,(off+1)*20)]},
        "query":{"more_results_available":off < 1},
    }).encode()


class ContinuousResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def test_query_count_not_artificially_capped_and_search_pages(self):
        self.assertEqual(len(_queries(["lottery markov"]*80)),80)
        self.assertEqual(RESULTS_PER_QUERY,20)
        data=_crossref_request("lottery",offset=20,fetch=crossref_page)
        self.assertEqual(len(data["message"]["items"]),2)
        data=_brave_request("lottery","dummy-token",offset=1,fetch=brave_page)
        self.assertEqual(len(data["web"]["results"]),20)
        for bad in (-1,10001,True):
            with self.assertRaises(ValueError):
                _crossref_request("lottery",offset=bad,fetch=crossref_page)
        for bad in (-1,10,True):
            with self.assertRaises(ValueError):
                _brave_request("lottery","dummy-token",offset=bad,fetch=brave_page)

    def test_next_run_resumes_cumulative_sources_without_duplicate(self):
        report, stage=collect(self.root,["lottery markov"],crossref_fetch=crossref_page,
                              request_budget=1,now=NOW)
        self.assertEqual(report["candidate_count"],20)
        self.assertEqual(report["new_unique_sources"],20)
        self.assertEqual(report["lifetime_unique_sources_after_commit"],20)
        self.assertIsNone(report["application_lifetime_source_quota"])
        persist(self.root,stage,report)
        self.assertEqual(_seen(self.root)[0].__len__(),20)
        second,stage2=collect(self.root,["lottery markov"],crossref_fetch=crossref_page,
                              request_budget=1,now=NOW)
        self.assertEqual(second["candidate_count"],2)
        self.assertEqual(second["new_unique_sources"],2)
        self.assertEqual(second["lifetime_unique_sources_after_commit"],22)
        persist(self.root,stage2,second)
        self.assertEqual(len(load(self.root/SOURCE_LEDGER)),2)
        self.assertEqual(len(_seen(self.root)[0]),22)
        third,third_stage=collect(self.root,["lottery markov"],crossref_fetch=crossref_page,
                                  request_budget=2,now=NOW)
        self.assertEqual(third["requests_attempted_this_run"],0)
        self.assertEqual(third["new_unique_sources"],0)
        self.assertEqual(third["candidate_count"],0)
        # The next JST date permits refresh; known identifiers aren't repeated.
        refreshed, staged=collect(self.root,["lottery markov"],crossref_fetch=crossref_page,
                                   request_budget=1,now=TOMORROW)
        self.assertEqual(refreshed["candidate_count"],20)
        self.assertEqual(refreshed["new_unique_sources"],0)
        self.assertEqual(refreshed["lifetime_unique_sources_after_commit"],22)

    def test_round_robin_brave_pagination_does_not_spill_token(self):
        one,staged=collect(self.root,["lottery methods"],brave_api_key="dummy-token",
                           crossref_fetch=crossref_page,brave_fetch=brave_page,
                           request_budget=1,now=NOW)
        self.assertEqual(one["providers_attempted"],["crossref","brave_web_search"])
        persist(self.root,staged,one)
        two,staged=collect(self.root,["lottery methods"],brave_api_key="dummy-token",
                           crossref_fetch=crossref_page,brave_fetch=brave_page,
                           request_budget=1,now=NOW)
        self.assertEqual(two["new_unique_sources"],20)
        self.assertEqual(two["pages_received_this_run"],1)
        self.assertNotIn("dummy-token",json.dumps(two))
        self.assertTrue(all(e["external_claim_verified"] is False
                            for e in two["candidates"]))
        persist(self.root,staged,two)
        self.assertEqual(len(_seen(self.root)[0]),40)

    def test_api_error_retries_later_and_does_not_forge_results(self):
        def offline(url):
            raise ConnectionError("unavailable")
        report,staged=collect(self.root,["lottery"],crossref_fetch=offline,
                              request_budget=9,now=NOW)
        self.assertEqual(report["new_unique_sources"],0)
        self.assertEqual(report["requests_attempted_this_run"],1)
        self.assertEqual(report["errors"][0]["error_type"],"ConnectionError")
        self.assertEqual(report["candidate_count"],0)
        self.assertFalse((self.root/SOURCE_LEDGER).exists())
        persist(self.root,staged,report)
        self.assertFalse((self.root/SOURCE_LEDGER).exists())
        recovered,_=collect(self.root,["lottery"],crossref_fetch=crossref_page,
                             request_budget=1,now=NOW)
        self.assertEqual(recovered["candidate_count"],20)

    def test_tampered_source_archive_fails_closed(self):
        report,staged=collect(self.root,["lottery"],crossref_fetch=crossref_page,
                              request_budget=1,now=NOW)
        persist(self.root,staged,report)
        file=self.root/SOURCE_LEDGER
        raw=file.read_text(encoding="utf-8").replace("Journal","OtherJournal")
        file.write_text(raw,encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"ledger checksum"):
            collect(self.root,["lottery"],crossref_fetch=crossref_page,
                    request_budget=1,now=NOW)

    def test_stale_collection_cannot_append_duplicate_batch(self):
        a, stage_a = collect(self.root, ["lottery"], crossref_fetch=crossref_page,
                             request_budget=1, now=NOW)
        b, stage_b = collect(self.root, ["lottery"], crossref_fetch=crossref_page,
                             request_budget=1, now=NOW)
        persist(self.root, stage_a, a)
        before = (self.root/SOURCE_LEDGER).read_bytes()
        with self.assertRaisesRegex(ValueError, "stale"):
            persist(self.root, stage_b, b)
        self.assertEqual((self.root/SOURCE_LEDGER).read_bytes(), before)
        self.assertEqual(len(_seen(self.root)[0]), 20)

    def test_duplicate_staged_identity_rejected_before_write(self):
        report, staged = collect(self.root, ["lottery"], crossref_fetch=crossref_page,
                                 request_budget=1, now=NOW)
        staged["new_sources"][1] = dict(staged["new_sources"][0])
        with self.assertRaisesRegex(ValueError, "duplicate staged"):
            persist(self.root, staged, report)
        self.assertFalse((self.root/SOURCE_LEDGER).exists())
        self.assertFalse((self.root/PROGRESS_PATH).exists())

    def test_exhausted_unchanged_checkpoint_is_not_rewritten(self):
        report, staged = collect(self.root, ["lottery"], crossref_fetch=crossref_page,
                                 request_budget=2, now=NOW)
        persist(self.root, staged, report)
        report, staged = collect(self.root, ["lottery"], crossref_fetch=crossref_page,
                                 request_budget=2, now=NOW)
        self.assertEqual(report["requests_attempted_this_run"], 0)
        self.assertEqual(report["new_unique_sources"], 0)
        with patch.object(Path, "write_bytes", side_effect=AssertionError("unexpected rewrite")):
            persist(self.root, staged, report)

    def test_checkpoint_edit_invalidates_staged_collection(self):
        report, staged = collect(self.root, ["lottery"], crossref_fetch=crossref_page,
                                 request_budget=1, now=NOW)
        path = self.root/PROGRESS_PATH
        path.parent.mkdir()
        path.write_text(json.dumps({"version":VERSION,"request_counter":0,"positions":{}}),
                        encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "stale"):
            persist(self.root, staged, report)
        self.assertFalse((self.root/SOURCE_LEDGER).exists())

    def test_cumulative_budget_is_never_an_infinite_http_loop(self):
        for budget in (0,-1,101,True):
            with self.assertRaises(ValueError):
                collect(self.root,["lottery"],crossref_fetch=crossref_page,
                        request_budget=budget,now=NOW)


if __name__=="__main__":
    unittest.main()
