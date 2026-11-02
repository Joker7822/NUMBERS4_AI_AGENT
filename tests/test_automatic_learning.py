"""Bank-only, genuinely prepublished auto-learning and promotion gate tests."""
from datetime import datetime, timedelta, timezone
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from numbers4_agent.automatic_learning import (
    VERSION, PROTOCOL_HASH, SPECS, FORECAST_PATH, WITNESS_PATH,
    CHAMPION_PATH, STATUS_PATH, _candidate_models, _probability,
    _training_hash, _verified, assess, apply_policy, freeze_shadow,
    read_champion, recommend_champion,
)
from numbers4_agent.sources import JST
from numbers4_agent.store import append, load, file_hash

VALID_BANK = "https://www.mizuhobank.co.jp/takarakuji/check/numbers/numbers4/index.html"
VALID_RAKUTEN = "https://takarakuji.rakuten.co.jp/backnumber/numbers4/202611/"
DAY = "2026-11-02"


def official(root, number, rnd, day, hour=19):
    return append(root/"data"/"auto_verified_draws.jsonl", {
        "round": rnd, "draw_date": day, "winning_number": number,
        "verification": "bank_primary_rakuten_publication_match",
        "not_a_digital_signature": True,
        "bank_url": VALID_BANK, "corroborator_url": VALID_RAKUTEN,
        "bank_response_sha256": "a"*64,
        "corroborator_response_sha256": "b"*64,
        "verified_at_jst": f"{day}T{hour:02d}:15:00+09:00",
    })


def witness(root, shadow, hour=15):
    append(root/WITNESS_PATH, {
        "version": VERSION, "round": shadow["round"],
        "forecast_event_sha256": shadow["event_sha256"],
        "github_repo": "Joker7822/NUMBERS4_AI_AGENT",
        "github_event": "push", "github_workflow": "Numbers4 CI",
        "github_head_sha": "a"*40, "github_run_id": 123456,
        "github_run_created_at": f"{DAY}T{hour:02d}:10:00+09:00",
        "github_server_verified": True,
    })


class AutomaticLearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = datetime(2026, 11, 2, 15, tzinfo=JST)

    def prepare(self):
        official(self.root, "1234", 7104, "2026-10-30")

    def test_empty_bank_blocks_training_shadow_and_promotion(self):
        self.assertEqual(assess(self.root)["status"], "no_shadow_forecasts")
        self.assertEqual(read_champion(self.root)["champion"], "uniform")
        with self.assertRaisesRegex(ValueError,"bank-verified"):
            freeze_shadow(self.root, target_round=7105,
                          draw_date=DAY, now=self.now)
        state=apply_policy(self.root,now=self.now)
        self.assertEqual(state["production_champion"],"uniform")
        self.assertFalse(state["automatic_promotion_executed"])
        self.assertFalse((self.root/CHAMPION_PATH).exists())
        self.assertFalse((self.root/FORECAST_PATH).exists())
        self.assertTrue((self.root/STATUS_PATH).is_file())

    def test_pre_draw_shadow_one_ticket_only_and_no_purchase(self):
        self.prepare()
        frozen=freeze_shadow(self.root,target_round=7105,
                            draw_date=DAY,now=self.now)
        self.assertEqual(frozen["status"],
                         "shadow_frozen_requires_github_publication_witness")
        shadow=load(self.root/FORECAST_PATH)[0]
        self.assertEqual(shadow["baseline_number"],shadow["baseline_number"].zfill(4))
        self.assertEqual(shadow["training_verified_rounds"],1)
        self.assertEqual(shadow["training_last_round"],7104)
        self.assertEqual(shadow["protocol_sha256"],PROTOCOL_HASH)
        self.assertEqual(set(shadow["models"]),set(SPECS))
        self.assertTrue(all(len(m["number"])==4 for m in shadow["models"].values()))
        self.assertFalse(shadow["actual_purchase"])
        self.assertEqual(freeze_shadow(self.root,target_round=7105,
                                      draw_date=DAY,now=self.now)["status"],
                         "already_frozen")
        self.assertEqual(len(load(self.root/FORECAST_PATH)),1)
        self.assertFalse((self.root/"data/issued_forecasts.jsonl").exists())
        self.assertEqual(recommend_champion(self.root,7105)["selected_champion"],
                         "uniform")
        with self.assertRaises(ValueError):
            recommend_champion(self.root,7106)

    def test_unwitnessed_or_after_deadline_cannot_count_even_with_official_draw(self):
        self.prepare()
        freeze_shadow(self.root,target_round=7105,draw_date=DAY,now=self.now)
        official(self.root,"4321",7105,DAY)
        a=assess(self.root)
        self.assertEqual(a["integrity_blocker"],
                         "missing_independent_publication_witness")
        witness(self.root,load(self.root/FORECAST_PATH)[0],hour=19)
        with self.assertRaisesRegex(ValueError,"pre-draw GitHub"):
            assess(self.root)

    def test_verified_prepublished_data_scored_but_500_draw_gate_blocks(self):
        self.prepare()
        freeze_shadow(self.root,target_round=7105,draw_date=DAY,now=self.now)
        row=load(self.root/FORECAST_PATH)[0]
        witness(self.root,row,hour=15)
        official(self.root,row["baseline_number"],7105,DAY)
        result=assess(self.root)
        self.assertEqual(result["eligible_prospective_draws"],1)
        self.assertIsNone(result["integrity_blocker"])
        self.assertEqual(result["eligible_champion"],"uniform")
        self.assertEqual(result["model_assessments"]["positional_250_alpha5"]
                         ["uniform_reference_straight_hits"],1)
        self.assertEqual(apply_policy(self.root)["production_champion"],"uniform")

    def test_tampered_model_training_and_untrusted_manual_data_rejected(self):
        self.prepare()
        freeze_shadow(self.root,target_round=7105,draw_date=DAY,now=self.now)
        row=load(self.root/FORECAST_PATH)[0]
        witness(self.root,row)
        official(self.root,"5678",7105,DAY)
        baseline=assess(self.root)
        self.assertEqual(baseline["eligible_prospective_draws"],1)
        # Simulate an attacker recomputing the SHA chain after changing the
        # frozen model's output: subsequent official scoring must catch it.
        p=self.root/FORECAST_PATH
        p.unlink()
        tamper={k:v for k,v in row.items() if k not in
                {"event_sha256","previous_sha256"}}
        tamper["models"]["positional_60_alpha10"]["number"]="9999"
        append(p,tamper)
        with self.assertRaisesRegex(ValueError,"orphan"):
            assess(self.root)

    def test_published_model_does_not_override_secondary_learning(self):
        self.prepare()
        self.assertEqual(len(_verified(self.root)),1)
        expected=_candidate_models(_verified(self.root),7105)
        self.assertEqual(len(expected),3)
        for model in expected.values():
            p=_probability(model["q"],"1234")
            self.assertGreater(p,0)
            self.assertTrue(0<=p<=1)
        with self.assertRaisesRegex(ValueError,"look-ahead"):
            _candidate_models(_verified(self.root),7104)

    def test_retroactive_or_weekend_forecasts_refused(self):
        self.prepare()
        for now,draw in [
            (datetime(2026,11,2,18,0,tzinfo=JST),DAY),
            (datetime(2026,11,1,15,0,tzinfo=JST),"2026-11-01"),
            (self.now,"2026-10-30"),
        ]:
            with self.assertRaises(ValueError):
                freeze_shadow(self.root,target_round=7105,
                              draw_date=draw,now=now)

    def test_policy_changes_only_when_rigorous_assessment_agrees(self):
        result=assess(self.root)
        result["status"]="eligible_under_preregistered_uniform_null"
        result["eligible_champion"]="positional_60_alpha10"
        result["integrity_blocker"]=None
        with patch("numbers4_agent.automatic_learning.assess",
                   return_value=result):
            new=apply_policy(self.root,now=self.now)
        self.assertTrue(new["automatic_promotion_executed"])
        self.assertEqual(new["production_champion"],"positional_60_alpha10")
        self.assertEqual(read_champion(self.root)["champion"],
                         "positional_60_alpha10")
        state=assess(self.root)
        self.assertEqual(state["status"],"no_shadow_forecasts")
        self.assertEqual(state["current_champion"],"positional_60_alpha10")
        # Fail-closed on evidence outage: do not roll back during an outage.
        state["integrity_blocker"]="official_outage"
        with patch("numbers4_agent.automatic_learning.assess",return_value=state):
            held=apply_policy(self.root,now=self.now)
        self.assertEqual(held["production_champion"],"positional_60_alpha10")
        state["integrity_blocker"]=None
        state["status"]="no_confirmed_advantage"
        with patch("numbers4_agent.automatic_learning.assess",return_value=state):
            undone=apply_policy(self.root,now=self.now)
        self.assertEqual(undone["production_champion"],"uniform")
        self.assertEqual(undone["action"],"rollback_to_uniform")


if __name__ == "__main__":
    unittest.main()
