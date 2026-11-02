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
            self.assertTrue(s["auto_learning"]["feature_implemented"])
            self.assertEqual(s["auto_learning"]["active_champion"],"uniform")
            self.assertEqual(s["auto_learning"]["officially_verified_training_rounds"],0)
            self.assertEqual(s["auto_learning"]["eligible_prospective_draws"],0)
            self.assertEqual(s["auto_learning"]["required_prospective_draws"],500)
            self.assertFalse(s["automatic_model_promotion"])
            self.assertGreater(len(s["warnings"]),0)
            output=root/"docs/data/status.json"
            write_dashboard(root,output)
            self.assertTrue(output.is_file())
            self.assertFalse((root/"data/issued_forecasts.jsonl").exists())


    def test_unverified_secondary_result_never_increases_trusted_draw_counter(self):
        import json
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            cache=root/'research/historical_unverified.json'
            cache.parent.mkdir(parents=True)
            cache.write_text(json.dumps({
                'version':'numbers4-research-source-v1',
                'verified_official':False,
                'publisher':'rakuten_lottery_publication_only',
                'rows_count':1,
                'rows':[{'round':7104,'draw_date':'2026-10-30','winning_number':'5805'}]
            }))
            report=snapshot(root,datetime(2026,11,2,12,tzinfo=JST))
            self.assertEqual(report['latest_unverified_draw']['winning_number'],'5805')
            self.assertEqual(report['latest_unverified_draw']['status'],'publisher_only_not_officially_verified')
            self.assertEqual(report['consistent_rounds'],0)
            self.assertIsNone(report['latest_consistent_draw'])
            self.assertFalse(report['prediction_skill_confirmed'])
