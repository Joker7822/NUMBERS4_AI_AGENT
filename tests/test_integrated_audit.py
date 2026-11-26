import copy
import tempfile
import unittest
from unittest.mock import patch
from contextlib import ExitStack
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

    def test_shared_loaders_once_and_report_arguments(self):
        reports, future = fixture()
        root = Path(".")
        history = [{"round": 1}, {"round": 2}]
        archive, smeta, bmeta = {"a": 1}, {"b": 2}, {"c": 3}
        straight, box = [1, 2], [3, None]
        with ExitStack() as stack:
            fp = stack.enter_context(patch.object(m, "_fingerprint", return_value=("same",)))
            h = stack.enter_context(patch.object(m.historical_archive, "load_archive", return_value=(history, archive)))
            s = stack.enter_context(patch.object(m.finance, "load_payouts", return_value=(straight, smeta)))
            b = stack.enter_context(patch.object(m.box_finance, "load_box_payouts", return_value=(box, bmeta)))
            modules = {"returns": m.return_audit, "payouts": m.payout_research,
                       "box": m.box_calibration, "ensemble": m.ensemble_audit, "cashflow": m.cashflow_risk}
            builders = {name: stack.enter_context(patch.object(module, "_audit_loaded", return_value=reports[name]))
                        for name, module in modules.items()}
            p = stack.enter_context(patch.object(m, "assess_prospective", return_value=future))
            self.assertEqual(m.audit(root, simulations=10, seed=1)["historical_audit_count"], 5)
            h.assert_called_once_with(root)
            s.assert_called_once_with(root, history)
            b.assert_called_once_with(root, history)
            p.assert_called_once_with(root)
            self.assertEqual(fp.call_count, 2)
            builders["returns"].assert_called_once_with(history, archive, straight, smeta, box, bmeta, simulations=10, seed=1)
            for name in ("payouts", "cashflow"):
                builders[name].assert_called_once_with(history, archive, straight, smeta, box, bmeta)
            for name in ("box", "ensemble"):
                builders[name].assert_called_once_with(history, archive)
            fp.side_effect = [("before",), ("after",)]
            with self.assertRaisesRegex(ValueError, "inputs changed"):
                m.audit(root)

    def test_fingerprint_covers_all_six_inputs_and_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for path in m.INPUT_PATHS:
                (root/path).parent.mkdir(parents=True, exist_ok=True)
                (root/path).write_bytes(b"original")
            original = m._fingerprint(root)
            self.assertEqual(len(original), 6)
            for path in m.INPUT_PATHS:
                (root/path).write_bytes(b"changed")
                self.assertNotEqual(m._fingerprint(root), original)
                (root/path).write_bytes(b"original")
            (root/m.INPUT_PATHS[-1]).unlink()
            with self.assertRaises(OSError):
                m._fingerprint(root)


if __name__ == "__main__":
    unittest.main()
