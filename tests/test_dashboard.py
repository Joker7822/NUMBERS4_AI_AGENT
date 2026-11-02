from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from numbers4_agent.dashboard import snapshot, write_dashboard
from numbers4_agent.sources import JST


class DashboardTests(unittest.TestCase):
    def test_empty_state_never_invents_draws_or_profit(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            s=snapshot(root,datetime(2026,11,2,12,tzinfo=JST))
            self.assertIsNone(s["latest_consistent_draw"])
            self.assertIsNone(s["latest_graded_issued_forecast"])
            self.assertIsNone(s["actual_purchase_profit_yen"])
            self.assertFalse(s["prediction_skill_confirmed"])
            self.assertGreater(len(s["warnings"]),0)
            output=root/"docs/data/status.json"
            write_dashboard(root,output)
            self.assertTrue(output.is_file())
            self.assertFalse((root/"data/issued_forecasts.jsonl").exists())
