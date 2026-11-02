"""Latest research candidate must follow newest valid data without changing issuance."""
from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from numbers4_agent.dashboard import (
    VERSION, LATEST_FORECAST_VERSION, latest_research_forecast,
    _add_change_metadata,
)
from numbers4_agent.sources import JST


def archive(round_n=7105):
    return {"status":"secondary_public_mirrors_agree_not_officially_verified",
            "git_blob_sha1":"a"*40, "last_round":round_n}


def verified_evolution(number="2903", generation=12, round_n=7105):
    return {
        "status":"recursive_research_exploration_not_prospective_evidence",
        "next_number":number, "next_model":"rolling_250_alpha10",
        "generated_at_jst":"2026-11-03T07:30:00+09:00",
        "generation":generation,
        "latest_verification":{
            "last_round":round_n, "archive_git_blob_sha1":"a"*40,
            "generation":generation, "prediction_skill_confirmed":False,
            "bank_primary_all_rounds_verified":False,
        },
    }


def replay(number="1234", round_n=7105):
    return {
        "status":"historical_walk_forward_reconstruction_only",
        "tickets_per_draw":1,
        "last_evaluated_round":round_n,
        "archive_git_blob_sha1":"a"*40,
        "generated_at_jst":"2026-11-03T07:20:00+09:00",
        "next_research_candidate":{
            "target_round":round_n+1,"data_cutoff_round":round_n,
            "status":"research_only_not_issued_not_purchased",
            "numbers":[number],"model":"uniform","accuracy_claim":False,
        },
    }


class LatestForecastTests(unittest.TestCase):
    def test_verified_evolution_takes_priority_over_old_replay(self):
        current=latest_research_forecast(archive(),verified_evolution(),replay())
        self.assertEqual(current["version"],LATEST_FORECAST_VERSION)
        self.assertEqual(current["number"],"2903")
        self.assertEqual(current["model"],"rolling_250_alpha10")
        self.assertEqual(current["target_round"],7106)
        self.assertEqual(current["data_cutoff_round"],7105)
        self.assertEqual(current["source"],"validated_research_evolution")
        self.assertEqual(current["research_generation"],12)
        self.assertFalse(current["officially_verified"])
        self.assertFalse(current["actual_purchase"])

    def test_stale_evolution_uses_current_replay_not_old_numbers(self):
        state=verified_evolution("9999",round_n=7104)
        state["status"]="stale_history_reanalysis"
        current=latest_research_forecast(archive(),state,replay("2903"))
        self.assertEqual(current["number"],"2903")
        self.assertEqual(current["source"],"validated_single_ticket_replay")
        self.assertIsNone(current["research_generation"])
        self.assertEqual(current["target_round"],7106)

    def test_evolution_and_replay_stale_hides_candidate(self):
        state=verified_evolution("8888",round_n=7104)
        state["status"]="stale_history_reanalysis"
        self.assertIsNone(latest_research_forecast(archive(),state,replay("2903",round_n=7104)))
        self.assertIsNone(latest_research_forecast(
            {"status":"not_loaded"},verified_evolution(),replay()))

    def test_same_candidate_preserves_changed_timestamp_through_replay(self):
        now=datetime(2026,11,3,8,tzinfo=JST)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            status=root/"docs/data/status.json"
            status.parent.mkdir(parents=True)
            current=latest_research_forecast(archive(),verified_evolution(),replay())
            first=_add_change_metadata(root,current,now)
            self.assertTrue(first["changed_since_previous_snapshot"])
            self.assertEqual(first["last_changed_at_jst"],now.isoformat(timespec="seconds"))
            status.write_text(json.dumps({
                "version":VERSION,
                "latest_research_forecast":first,
            }))
            repeated=_add_change_metadata(root,current,now+timedelta(hours=2))
            self.assertFalse(repeated["changed_since_previous_snapshot"])
            self.assertEqual(repeated["last_changed_at_jst"],first["last_changed_at_jst"])
            new_number=latest_research_forecast(
                archive(),verified_evolution("0456",generation=13),replay())
            changed=_add_change_metadata(root,new_number,now+timedelta(hours=3))
            self.assertTrue(changed["changed_since_previous_snapshot"])
            self.assertEqual(changed["number"],"0456")
            self.assertEqual(changed["last_changed_at_jst"],
                             (now+timedelta(hours=3)).isoformat(timespec="seconds"))
            # Switch from replay to evolved model also counts as a real change.
            online=latest_research_forecast(archive(),{"status":"not_yet_run"},replay())
            status.write_text(json.dumps({
                "version":VERSION, "latest_research_forecast":online,
            }))
            switched=_add_change_metadata(root,current,now+timedelta(hours=4))
            self.assertTrue(switched["changed_since_previous_snapshot"])
            self.assertEqual(switched["source"],"validated_research_evolution")
            self.assertFalse(switched["officially_verified"])

    def test_forecast_does_not_use_previous_snapshot_as_training_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            state=root/"docs/data/status.json"
            state.parent.mkdir(parents=True)
            state.write_text("invalid JSON",encoding="utf-8")
            current=latest_research_forecast(archive(),verified_evolution(),replay())
            result=_add_change_metadata(root,current,datetime(2026,11,3,8,tzinfo=JST))
            self.assertEqual(result["number"],"2903")
            self.assertTrue(result["changed_since_previous_snapshot"])


if __name__=="__main__":
    unittest.main()
