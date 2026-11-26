from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest

from numbers4_agent.draw_schedule import reviewed_schedule, target_for_date
from numbers4_agent.sources import JST


class DrawScheduleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.path=self.root/"research/approved_draw_schedule.json"
        self.path.parent.mkdir()
        self.item={"round":7105,"draw_date":"2026-11-02","human_reviewed":True,
                   "source_url":"https://www.takarakuji-official.jp/kuji/numbers/numbers4/",
                   "reviewed_at_jst":"2026-11-02T12:00:00+09:00"}

    def write(self, rows):
        self.path.write_text(json.dumps({"version":"numbers4-approved-draw-schedule-v1",
                                         "rounds":rows}),encoding="utf-8")

    def test_missing_empty_and_exact_target(self):
        self.assertEqual(reviewed_schedule(self.root),[])
        self.write([])
        self.assertIsNone(target_for_date(self.root,"2026-11-02"))
        self.write([self.item])
        self.assertEqual(target_for_date(self.root,"2026-11-02"),self.item)
        self.assertIsNone(target_for_date(self.root,"2026-11-03"))

    def test_duplicate_round_or_date_and_unordered_rejected(self):
        for second in (dict(self.item),dict(self.item,round=7106),
                       dict(self.item,round=7104,draw_date="2026-11-03")):
            self.write([self.item,second])
            with self.assertRaises(ValueError):
                reviewed_schedule(self.root)

    def test_unreviewed_insecure_urls_weekend_and_late_review(self):
        for changes in ({"human_reviewed":False},{"source_url":"https://www.mizuhobank.co.jp:8443/page"},
                        {"source_url":"https://user@www.mizuhobank.co.jp/page"},
                        {"source_url":"https://example.com/page"},{"draw_date":"2026-11-01"},
                        {"reviewed_at_jst":"2026-11-02T18:00:00+09:00"}):
            self.write([dict(self.item,**changes)])
            with self.assertRaises(ValueError):
                reviewed_schedule(self.root)


if __name__=="__main__":
    unittest.main()
