from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from numbers4_agent.sources import JST, record_observation, reconcile, corroborated_draws
from numbers4_agent.store import load
from numbers4_agent.ledger import issue, read_issued
from numbers4_agent.evaluation import graded_predictions

URLS = {
    "mizuhobank": "https://www.mizuhobank.co.jp/takarakuji/check/numbers/numbers4/index.html",
    "takarakuji_official": "https://www.takarakuji-official.jp/kuji/numbers/numbers4/feature.html",
}


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.when = datetime(2026, 10, 30, 20, 0, tzinfo=JST)
        self.issue_time = datetime(2026, 10, 30, 12, 0, tzinfo=JST)

    def observe(self, source, number="0123", round_number=100, date="2026-10-30"):
        return record_observation(self.root, round_number=round_number, draw_date=date,
                                  number=number, source=source, url=URLS[source], at=self.when)

    def test_consistent_manual_sources_not_auto_official_verified(self):
        self.observe("mizuhobank")
        self.assertEqual(reconcile(self.root)[100]["status"], "single_source_only")
        self.assertEqual(corroborated_draws(self.root), [])
        self.observe("takarakuji_official")
        self.assertEqual(reconcile(self.root)[100]["status"], "two_source_entered_consistent")
        self.assertEqual(corroborated_draws(self.root)[0]["winning_number"], "0123")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.observe("mizuhobank")

    def test_conflicting_sources_never_grade(self):
        self.observe("mizuhobank", "0123")
        self.observe("takarakuji_official", "0124")
        self.assertEqual(reconcile(self.root)[100]["status"], "source_conflict")
        self.assertEqual(corroborated_draws(self.root), [])

    def test_malicious_source_url_refused(self):
        with self.assertRaises(ValueError):
            record_observation(self.root, round_number=100, draw_date="2026-10-30",
                               number="0123", source="mizuhobank",
                               url="https://www.mizuhobank.co.jp.attacker.example/", at=self.when)

    def test_evidence_chain_tamper_fails_closed(self):
        self.observe("mizuhobank")
        path = self.root / "data" / "source_observations.jsonl"
        path.write_text(path.read_text().replace("0123", "9876"))
        with self.assertRaisesRegex(ValueError, "checksum"):
            reconcile(self.root)

    def test_issuance_grade_exact_mode_with_manual_source_agreement(self):
        record = issue(self.root, target_round=100, draw_date="2026-10-30",
                       mode="set", numbers=["0123"],
                       deadline_jst="2026-10-30T18:30:00+09:00",
                       model_version="research-candidate-v1", now=self.issue_time)
        self.assertFalse(record["actual_purchase"])
        self.assertEqual(graded_predictions(self.root), [])
        self.observe("mizuhobank")
        self.observe("takarakuji_official")
        grades = graded_predictions(self.root)
        self.assertEqual(grades[0]["tickets"][0]["result"], "set_straight")
        self.assertEqual(grades[0]["winning_tickets"], 1)
        self.assertIsNone(grades[0]["actual_profit_yen"])
        self.assertEqual(grades[0]["reference_cost_yen"], 200)
        self.assertEqual(read_issued(self.root)[0]["numbers"][0], "0123")

    def test_no_after_draw_or_duplicated_or_redundant_publication(self):
        args = dict(target_round=100, draw_date="2026-10-30",mode="box",
                    numbers=["0123"],
                    deadline_jst="2026-10-30T18:30:00+09:00",
                    model_version="research-candidate-v1")
        with self.assertRaisesRegex(ValueError, "deadline has passed"):
            issue(self.root, **args, now=self.when)
        with self.assertRaises(ValueError):
            issue(self.root, **(args | {"numbers": ["1111"]}),
                  now=self.issue_time)
        issue(self.root, **args, now=self.issue_time)
        with self.assertRaisesRegex(ValueError, "already published"):
            issue(self.root, **args, now=self.issue_time)
        path = self.root / "data" / "issued_forecasts.jsonl"
        path.write_text(path.read_text().replace("0123", "9876"))
        with self.assertRaises(ValueError):
            read_issued(self.root)


    def test_new_issuance_is_one_ticket_but_legacy_five_is_read_only(self):
        from numbers4_agent.store import append
        with self.assertRaisesRegex(ValueError, "exactly one"):
            issue(self.root, target_round=101, draw_date="2026-10-30",
                  mode="straight", numbers=["0123","1234"],
                  deadline_jst="2026-10-30T18:30:00+09:00",
                  model_version="one-v1", now=self.issue_time)
        legacy = {
            "target_round":100,"draw_date":"2026-10-30",
            "mode":"straight","numbers":["0000","0001","0002","0003","0004"],
            "freeze_deadline_jst":"2026-10-30T18:30:00+09:00",
            "issued_at_jst":self.issue_time.isoformat(),
            "model_version":"five-ticket-legacy",
            "actual_purchase":False,"scope":"published_advice_not_purchase",
        }
        append(self.root/"data"/"issued_forecasts.jsonl", legacy)
        self.assertEqual(len(read_issued(self.root)[0]["numbers"]),5)
        with self.assertRaisesRegex(ValueError,"already published"):
            issue(self.root, target_round=100, draw_date="2026-10-30",
                  mode="straight", numbers=["0123"],
                  deadline_jst="2026-10-30T18:30:00+09:00",
                  model_version="one-v1", now=self.issue_time)

    def test_no_retroactive_issue_with_real_draw_evidence(self):
        self.observe("mizuhobank")
        self.observe("takarakuji_official")
        with self.assertRaisesRegex(ValueError, "after latest"):
            issue(self.root, target_round=100, draw_date="2026-10-30", mode="straight",
                  numbers=["0123"],
                  deadline_jst="2026-10-30T18:30:00+09:00", model_version="ref",now=self.issue_time)

    def test_observation_before_official_draw_window_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "before the draw-day"):
            record_observation(self.root, round_number=100, draw_date="2026-10-30",
                               number="0123", source="mizuhobank", url=URLS["mizuhobank"],
                               at=datetime(2026, 10, 30, 12, 0, tzinfo=JST))

    def test_pre_deadline_input_must_use_jst(self):
        with self.assertRaisesRegex(ValueError, "must be JST"):
            issue(self.root, target_round=100, draw_date="2026-10-30", mode="straight",
                  numbers=["0123"],
                  deadline_jst="2026-10-30T09:30:00+00:00",
                  model_version="ref",now=self.issue_time)
