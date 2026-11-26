from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest

from numbers4_agent.operational_health import compact_ingestion, ingestion_health, snapshot, INGESTION_PATH
from numbers4_agent.sources import JST
from numbers4_agent.store import file_hash


class OperationalHealthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = datetime(2026, 11, 26, 12, tzinfo=JST)
        self.report = {"version": "numbers4-official-fetch-v1", "checked_at_jst": self.now.isoformat(),
                       "status": "blocked_no_bank_verified_results", "bank_rows": 0, "rakuten_rows": 255,
                       "publisher_matched_rows": 0, "new_verified_rows": 0,
                       "publisher_access_denials": {"mizuhobank": "HTTP 403"},
                       "requests_skipped_after_access_denial": 11,
                       "ledger_sha256": file_hash(self.root/"data/auto_verified_draws.jsonl"),
                       "automatic_model_promotion": False, "verified_claim_only_on_matching_records": True}
        self.prospective = {"verified_official_draws_available": 0, "shadow_forecasts_recorded": 0,
                            "independently_witnessed_forecasts": 0, "eligible_prospective_draws": 0,
                            "required_prospective_draws": 500, "integrity_blocker": None}

    def write(self):
        path = self.root/INGESTION_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(compact_ingestion(self.report)), encoding="utf-8")

    def test_missing_data_is_not_success(self):
        r = snapshot(self.root, self.now, self.prospective)
        self.assertEqual(r["official_ingestion"]["state"], "not_checked")
        self.assertEqual(r["schedule"]["state"], "no_reviewed_target")
        self.assertEqual(r["training"]["state"], "no_verified_draws")
        self.assertEqual(r["publication"]["state"], "no_forecasts")
        self.assertEqual(r["prospective"]["state"], "insufficient_draws")
        self.assertFalse(r["promotion_authorized_by_monitor"])

    def test_access_denial_and_skips_are_public_without_raw_errors(self):
        self.write()
        r = ingestion_health(self.root, self.now)
        self.assertEqual(r["state"], "access_denied")
        self.assertEqual(r["denied_publishers"], ["mizuhobank"])
        self.assertEqual(r["skipped_requests"], 11)
        self.assertNotIn("HTTP 403", json.dumps(r))

    def test_old_future_and_mismatched_evidence(self):
        self.write()
        self.assertEqual(ingestion_health(self.root, self.now+timedelta(hours=97))["state"], "stale")
        self.assertEqual(ingestion_health(self.root, self.now-timedelta(hours=1))["state"], "invalid_evidence")
        p = self.root/"data/auto_verified_draws.jsonl"
        p.parent.mkdir()
        p.write_text("changed", encoding="utf-8")
        self.assertEqual(ingestion_health(self.root, self.now)["state"], "invalid_evidence")

    def test_positive_matches_are_not_prediction_proof(self):
        self.report.update(status="verified", bank_rows=2, publisher_matched_rows=2,
                           new_verified_rows=2, publisher_access_denials={})
        self.write()
        self.assertEqual(ingestion_health(self.root, self.now)["state"], "matched")
        self.prospective.update(verified_official_draws_available=600, shadow_forecasts_recorded=501,
                                independently_witnessed_forecasts=500, eligible_prospective_draws=500)
        r = snapshot(self.root, self.now, self.prospective)
        self.assertEqual(r["publication"]["state"], "witnesses_pending")
        self.assertEqual(r["prospective"]["state"], "minimum_count_met_not_proof")
        self.assertFalse(r["actual_purchase"])

    def test_unsafe_counts_and_invalid_schedule(self):
        self.report["publisher_matched_rows"] = 3
        with self.assertRaises(ValueError):
            compact_ingestion(self.report)
        self.prospective["eligible_prospective_draws"] = 1
        with self.assertRaises(ValueError):
            snapshot(self.root, self.now, self.prospective)
        self.prospective["eligible_prospective_draws"] = 0
        p = self.root/"research/approved_draw_schedule.json"
        p.parent.mkdir()
        p.write_text("[]", encoding="utf-8")
        self.assertEqual(snapshot(self.root, self.now, self.prospective)["schedule"]["state"], "invalid_schedule")


if __name__ == "__main__":
    unittest.main()
