"""Deployment regression: history may advance between research and Pages jobs."""
from copy import deepcopy
from pathlib import Path
import unittest

from numbers4_agent.publication import audit_research_pages_snapshot


def fixture():
    report = {
        "generation": 8, "first_evaluated_round": 2,
        "last_evaluated_round": 7105, "evaluated_draws": 7104,
        "archive_latest_round": 7105, "archive_git_blob_sha1": "a" * 40,
        "production_model_changed": False,
        "model_auto_promotion_authorized": False,
        "development": {"model_metrics": {"adaptive": {"straight_hits": 1}}},
        "late_historical_reanalysis": {
            "model_metrics": {"adaptive": {"straight_hits": 0}}},
    }
    evolution = {
        "generation": 8,
        "status": "recursive_research_exploration_not_prospective_evidence",
        "evaluated_draws": 7104, "next_number": "2903", "next_model": "uniform",
        "performance_advantage_confirmed": False,
        "model_auto_promotion_authorized": False,
        "latest_verification": {
            "generation": 8, "evaluated_draws": 7104, "tickets_per_draw": 1,
            "selected_straight_hits": 1,
            "last_round": 7105,
            "archive_git_blob_sha1": "a" * 40,
            "bank_primary_all_rounds_verified": False,
            "prediction_skill_confirmed": False,
        },
    }
    state = {
        "research_evolution": evolution,
        "historical_archive": {
            "status": "secondary_public_mirrors_agree_not_officially_verified",
            "last_round": 7105, "git_blob_sha1": "a" * 40,
        },
        "latest_research_forecast": {
            "source": "validated_research_evolution",
            "target_round": 7106, "data_cutoff_round": 7105,
            "number": "2903", "model": "uniform",
            "research_generation": 8,
            "actual_purchase": False, "prediction_skill_confirmed": False,
            "archive_git_blob_sha1": "a" * 40,
        },
        "prediction_skill_confirmed": False,
        "actual_purchase_profit_yen": None,
    }
    return report, evolution, state


def set_stale_after_new_draw(report, evolution, state):
    evolution.update({
        "status": "stale_history_reanalysis",
        "latest_verification": None, "next_number": None, "next_model": None,
        "evaluated_draws": 0,
    })
    state["historical_archive"].update({
        "last_round": 7106, "git_blob_sha1": "b" * 40,
    })
    state["latest_research_forecast"] = {
        "source": "validated_single_ticket_replay",
        "target_round": 7107, "data_cutoff_round": 7106,
        "number": "0123", "model": "uniform",
        "research_generation": None,
        "actual_purchase": False, "prediction_skill_confirmed": False,
        "archive_git_blob_sha1": "b" * 40,
    }


class SafePagesDeploymentTests(unittest.TestCase):
    def test_current_report_and_archive_still_need_full_verification(self):
        report, evolution, state = fixture()
        self.assertEqual(
            audit_research_pages_snapshot(report, evolution, state), "fresh")
        state["latest_research_forecast"]["number"] = "9999"
        with self.assertRaisesRegex(ValueError, "fresh research snapshot"):
            audit_research_pages_snapshot(report, evolution, state)

    def test_new_history_during_deploy_is_stale_not_error_or_forged_success(self):
        report, evolution, state = fixture()
        set_stale_after_new_draw(report, evolution, state)
        self.assertEqual(
            audit_research_pages_snapshot(report, evolution, state),
            "stale_waiting_for_next_research")
        state["latest_research_forecast"] = None
        self.assertEqual(
            audit_research_pages_snapshot(report, evolution, state),
            "stale_waiting_for_next_research")

    def test_stale_research_number_cannot_leak_into_published_snapshot(self):
        report, evolution, state = fixture()
        set_stale_after_new_draw(report, evolution, state)
        state["latest_research_forecast"]["source"] = (
            "validated_research_evolution")
        with self.assertRaisesRegex(ValueError, "stale research candidate"):
            audit_research_pages_snapshot(report, evolution, state)

    def test_stale_claim_without_new_source_rejected(self):
        report, evolution, state = fixture()
        evolution.update({
            "status": "stale_history_reanalysis",
            "latest_verification": None,
            "next_number": None, "next_model": None, "evaluated_draws": 0,
        })
        with self.assertRaisesRegex(ValueError, "stale evolution result"):
            audit_research_pages_snapshot(report, evolution, state)

    def test_history_rollback_and_unauthorized_proof_rejected(self):
        report, evolution, state = fixture()
        set_stale_after_new_draw(report, evolution, state)
        state["historical_archive"]["last_round"] = 7104
        with self.assertRaisesRegex(ValueError, "stale evolution result"):
            audit_research_pages_snapshot(report, evolution, state)
        state["historical_archive"]["last_round"] = 7106
        state["prediction_skill_confirmed"] = True
        with self.assertRaisesRegex(ValueError, "unsafe or inconsistent"):
            audit_research_pages_snapshot(report, evolution, state)

    def test_wrong_generation_and_inconsistent_state_rejected(self):
        report, evolution, state = fixture()
        report["generation"] += 1
        with self.assertRaisesRegex(ValueError, "unsafe or inconsistent"):
            audit_research_pages_snapshot(report, evolution, state)
        report["generation"] -= 1
        state["research_evolution"] = deepcopy(evolution)
        state["research_evolution"]["next_number"] = "7777"
        with self.assertRaisesRegex(ValueError, "unsafe or inconsistent"):
            audit_research_pages_snapshot(report, evolution, state)

    def test_workflow_uses_both_states_and_current_main(self):
        yml = (Path(__file__).resolve().parents[1] /
               ".github/workflows/predictive-research.yml").read_text()
        self.assertIn("audit_research_pages_snapshot(report,evolution,state)", yml)
        self.assertIn("stale_waiting_for_next_research", yml)
        self.assertIn("git reset --hard origin/main", yml)
        self.assertNotIn("assert verification is not None", yml)


if __name__ == "__main__":
    unittest.main()
