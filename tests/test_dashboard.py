from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from numbers4_agent.dashboard import snapshot, write_dashboard, recent_week_projection
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

    def test_recent_week_separates_real_issuance_and_research_reconstruction(self):
        now=datetime(2026,11,4,7,0,tzinfo=JST)
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            issuance=[
                {'target_round':7103,'draw_date':'2026-10-29','numbers':['2491'],
                 'mode':'straight','issued_at_jst':'2026-10-29T17:00:00+09:00'},
                {'target_round':7102,'draw_date':'2026-10-28','numbers':['3986'],
                 'mode':'straight','issued_at_jst':'2026-10-28T17:00:00+09:00'}
            ]
            graded=[{'round':7103,'date':'2026-10-29','winning_number':'2491',
                     'verification':'bank_primary_rakuten_publication_match',
                     'tickets':[{'number':'2491','result':'straight'}]}]
            evolution={'status':'recursive_research_exploration_not_prospective_evidence',
                       'latest_verification':{
                           'all_rounds_checked_against_archive':True,
                           'source_status':'secondary_public_mirrors_agree_not_officially_verified',
                           'independently_verified_prepublished_forecasts':False,
                           'recent_rounds':[
                               {'round':7106,'draw_date':'2026-11-03',
                                'data_cutoff_round':7105,'selected_number':'2903',
                                'selected_model':'uniform','actual':'5870','selected_hit':False},
                               {'round':7103,'draw_date':'2026-10-29',
                                'data_cutoff_round':7102,'selected_number':'2491',
                                'selected_model':'uniform','actual':'2491','selected_hit':True},
                               {'round':7102,'draw_date':'2026-10-28',
                                'data_cutoff_round':7101,'selected_number':'3986',
                                'selected_model':'uniform','actual':'3986','selected_hit':True}
                           ]}}
            with patch('numbers4_agent.dashboard.load',return_value=[]),patch(
                    'numbers4_agent.dashboard._validated_witnesses',return_value={}):
                week=recent_week_projection(root,now=now,issued=issuance,
                    graded=graded,trusted=[],evolution=evolution)
            self.assertEqual((week['start_date'],week['end_date']),
                             ('2026-10-29','2026-11-04'))
            self.assertEqual(week['officially_graded_issued'],1)
            self.assertEqual(len(week['issued_forecasts']),1)
            self.assertEqual(week['issued_forecasts'][0]['ticket_results'],['straight'])
            self.assertEqual(len(week['research_replay']),2)
            self.assertEqual(week['research_reference_matches'],1)
            self.assertFalse(week['research_replay'][0]['issued_before_draw'])
            self.assertFalse(week['research_replay'][0]['actual_purchase'])

    def test_missing_official_and_publication_proof_never_grade_shadow(self):
        now=datetime(2026,11,4,7,0,tzinfo=JST)
        frozen=[{'round':7106,'draw_date':'2026-11-03',
                 'champion_number':'5870','champion_at_issue':'uniform',
                 'issued_at_jst':'2026-11-03T16:00:00+09:00'}]
        with tempfile.TemporaryDirectory() as t:
            with patch('numbers4_agent.dashboard.load',return_value=frozen),patch(
                    'numbers4_agent.dashboard._validated_witnesses',return_value={}):
                week=recent_week_projection(Path(t),now=now,issued=[],graded=[],
                    trusted=[{'round':7106,'draw_date':'2026-11-03',
                              'winning_number':'5870'}],evolution={})
            self.assertEqual(week['officially_matched_shadow'],0)
            self.assertEqual(week['shadow_forecasts'][0]['winning_number'],'5870')
            self.assertIsNone(week['shadow_forecasts'][0]['straight_match'])
            self.assertFalse(week['shadow_forecasts'][0]['publication_witnessed'])
