"""GitHub server published-at witness tests, without network or Git."""
from datetime import datetime, timezone, timedelta
import json
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
from numbers4_agent.draw_schedule import entry_hash

DAY="2026-11-02"


class PublicationWitnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        item={"round":7105,"draw_date":DAY,"human_reviewed":True,
              "source_url":"https://www.takarakuji-official.jp/kuji/numbers/numbers4/",
              "reviewed_at_jst":DAY+"T12:00:00+09:00"}
        schedule=self.root/"research/approved_draw_schedule.json"
        schedule.parent.mkdir(parents=True)
        schedule.write_text(json.dumps({"version":"numbers4-approved-draw-schedule-v1",
                                        "rounds":[item]}),encoding="utf-8")
        self.row=append(self.root/FORECAST_PATH, {
            "schedule_entry_sha256":entry_hash(item),
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

    def test_later_deadline_cannot_make_late_run_valid(self):
        path=self.root/FORECAST_PATH
        row=load(path)[0]
        path.unlink()
        payload={k:v for k,v in row.items() if k not in {"event_sha256","previous_sha256"}}
        payload["freeze_deadline_jst"]=DAY+"T23:00:00+09:00"
        append(path,payload)
        with self.assertRaisesRegex(ValueError,"timestamp or deadline"):
            verify_and_record(self.root,fetch=lambda sha:self._run("2026-11-02T10:05:00Z"))
        self.assertFalse((self.root/WITNESS_PATH).exists())

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
