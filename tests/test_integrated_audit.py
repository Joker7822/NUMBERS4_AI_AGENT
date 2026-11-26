import copy
import unittest
from unittest.mock import patch
from pathlib import Path

from numbers4_agent import integrated_audit as m


def fixture():
    reports = {}
    for name, (version, round_key, date_key) in m.AUDITS.items():
        reports[name] = {
            "version": version, round_key: 7122, date_key: "2026-11-25",
            "archive_git_blob_sha1": "a"*40,
            "actual_purchase": False, "prospective_skill_confirmed": False,
            "production_promotion_authorized": False, "purchase_decision": "SKIP",
        }
        if name in m.PAYOUT_AUDITS:
            reports[name].update(straight_payout_git_blob_sha1="b"*40,
                                 box_payout_git_blob_sha1="c"*40)
    prospective = {"secondary_historical_training_authorized": False,
                   "purchases_automated": False, "eligible_prospective_draws": 0,
                   "required_prospective_draws": 500, "integrity_blocker": None}
    return reports, prospective


class IntegratedAuditTests(unittest.TestCase):
    def test_consistent_reports_and_blockers(self):
        reports, future = fixture()
        result = m.integrate(reports, future)
        self.assertEqual(result["historical_audit_count"], 5)
        self.assertEqual(result["last_round"], 7122)
        self.assertEqual(result["purchase_decision"], "SKIP")
        self.assertFalse(result["production_promotion_authorized"])
        self.assertIn("insufficient_verified_prospective_draws", result["blockers"])

    def test_reject_missing_and_wrong_version(self):
        reports, future = fixture()
        del reports["box"]
        with self.assertRaises(ValueError):
            m.integrate(reports, future)
        reports, future = fixture()
        reports["box"]["version"] = "unknown"
        with self.assertRaises(ValueError):
            m.integrate(reports, future)

    def test_reject_inconsistent_round_date_or_archive_hash(self):
        reports, future = fixture()
        for key, value in (("last_round", 7121), ("last_draw_date", "2026-11-24"),
                           ("archive_git_blob_sha1", "z"*40)):
            changed = copy.deepcopy(reports)
            changed["box"][key] = value
            with self.assertRaisesRegex(ValueError, "inconsistent"):
                m.integrate(changed, future)

    def test_reject_inconsistent_payout_provenance(self):
        reports, future = fixture()
        reports["payouts"]["box_payout_git_blob_sha1"] = "d"*40
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            m.integrate(reports, future)

    def test_reject_unsafe_historical_claim(self):
        reports, future = fixture()
        reports["ensemble"]["production_promotion_authorized"] = True
        with self.assertRaisesRegex(ValueError, "unsafe"):
            m.integrate(reports, future)

    def test_no_authorization_even_if_prospective_count_met(self):
        reports, future = fixture()
        future["eligible_prospective_draws"] = 500
        result = m.integrate(reports, future)
        self.assertEqual(result["purchase_decision"], "SKIP")
        self.assertFalse(result["positive_expected_value_confirmed"])
        future["purchases_automated"] = True
        with self.assertRaises(ValueError):
            m.integrate(reports, future)

    def test_orchestration_invokes_each_read_only_audit(self):
        reports, future = fixture()
        root = Path(".")
        with patch.object(m.return_audit, "audit", return_value=reports["returns"]) as a, \
             patch.object(m.payout_research, "audit", return_value=reports["payouts"]), \
             patch.object(m.box_calibration, "audit", return_value=reports["box"]), \
             patch.object(m.ensemble_audit, "audit", return_value=reports["ensemble"]), \
             patch.object(m.cashflow_risk, "audit", return_value=reports["cashflow"]), \
             patch.object(m, "assess_prospective", return_value=future) as p:
            self.assertEqual(m.audit(root, simulations=10, seed=1)["historical_audit_count"], 5)
            a.assert_called_once_with(root, simulations=10, seed=1)
            p.assert_called_once_with(root)


if __name__ == "__main__":
    unittest.main()
