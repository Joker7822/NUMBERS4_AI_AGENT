"""GitHub server published-at witness tests, without network or Git."""
from datetime import datetime, timezone, timedelta
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from numbers4_agent.automatic_learning import (
    FORECAST_PATH, WITNESS_PATH, VERSION, PROTOCOL_HASH,
    _validated_witnesses,
)
from numbers4_agent.publication_witness import verify_and_record
from numbers4_agent.store import append, load

DAY="2026-11-02"


class PublicationWitnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.row=append(self.root/FORECAST_PATH, {
            "version":VERSION,"protocol_sha256":PROTOCOL_HASH,
            "round":7105,"draw_date":DAY,
            "issued_at_jst":DAY+"T15:00:00+09:00",
            "freeze_deadline_jst":DAY+"T18:00:00+09:00",
        })

    def _run(self, created, commit="a"*40, event="push"):
        return {"workflow_runs":[{
            "id":41400012345,
            "event":event, "head_sha":commit,
            "head_branch":"main","name":"Numbers4 CI",
            "created_at":created,
        }]}

    def test_pre_deadline_server_run_adds_witness_once(self):
        with patch("numbers4_agent.publication_witness._find_introduction_commit",
                   return_value="a"*40):
            r=verify_and_record(self.root,fetch=lambda sha:
                                self._run("2026-11-02T06:10:00Z"))
            self.assertEqual(r["new_verified_witnesses"],1)
            self.assertEqual(r["unwitnessed_rounds"],[])
            r=verify_and_record(self.root,fetch=lambda sha:
                                self._run("2026-11-02T06:10:00Z"))
            self.assertEqual(r["new_verified_witnesses"],0)
        observed=_validated_witnesses(self.root,load(self.root/FORECAST_PATH))
        self.assertEqual(observed[7105]["github_event"],"push")
        self.assertIn(7105,observed)
        self.assertEqual(observed[7105]["github_run_id"],41400012345)

    def test_github_token_workflow_dispatch_proves_bot_published_forecast(self):
        with patch("numbers4_agent.publication_witness._find_introduction_commit",
                   return_value="a"*40):
            result=verify_and_record(self.root,fetch=lambda sha:
                self._run("2026-11-02T06:05:00Z",event="workflow_dispatch"))
        self.assertEqual(result["new_verified_witnesses"],1)
        accepted=_validated_witnesses(self.root,load(self.root/FORECAST_PATH))
        self.assertEqual(accepted[7105]["github_event"],"workflow_dispatch")

    def test_late_run_does_not_backdate_forecast(self):
        with patch("numbers4_agent.publication_witness._find_introduction_commit",
                   return_value="a"*40):
            report=verify_and_record(self.root,fetch=lambda sha:
                                     self._run("2026-11-02T10:05:00Z"))
        self.assertEqual(report["new_verified_witnesses"],0)
        self.assertEqual(report["unwitnessed_rounds"],[7105])
        self.assertFalse((self.root/WITNESS_PATH).is_file())

    def test_wrong_event_or_head_rejected(self):
        for response in (self._run("2026-11-02T06:10:00Z",event="pull_request"),
                         self._run("2026-11-02T06:10:00Z",commit="b"*40)):
            with patch("numbers4_agent.publication_witness._find_introduction_commit",
                       return_value="a"*40):
                report=verify_and_record(self.root,fetch=lambda sha,response=response:response)
            self.assertEqual(report["new_verified_witnesses"],0)
        self.assertFalse((self.root/WITNESS_PATH).exists())


if __name__=="__main__":
    unittest.main()
