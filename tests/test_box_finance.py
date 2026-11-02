"""BOX retrospective logic: no real purchases, 4-equal-digit candidates excluded."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path

from numbers4_agent.box_finance import (
    PAYOUT_CSV,PAYOUT_META,VERSION,STATUS,REPLAY_VERSION,_git_sha,
    box_valid,signature,parse_box_prize,load_box_payouts,simulate_box,
)


def small_case():
    history=[
        {"round":1,"draw_date":"1994-10-07","winning_number":"1149"},
        {"round":2,"draw_date":"1994-10-14","winning_number":"1234"},
        {"round":3,"draw_date":"1994-10-21","winning_number":"1111"},
        {"round":4,"draw_date":"1994-10-28","winning_number":"0097"},
    ]
    grades=[
        {"round":2,"draw_date":"1994-10-14","actual":"1234","data_cutoff_round":1,
         "selected_model":"uniform","selected_numbers":"4321 1234 1111 0000 0123",
         "selected_hit":1,"uniform_numbers":"1111 7777 5678 5679 1234","uniform_hit":1},
        {"round":3,"draw_date":"1994-10-21","actual":"1111","data_cutoff_round":2,
         "selected_model":"uniform","selected_numbers":"1111 1112 1113 1114 1123",
         "selected_hit":1,"uniform_numbers":"2222 3333 4444 5555 1112","uniform_hit":0},
        {"round":4,"draw_date":"1994-10-28","actual":"0097","data_cutoff_round":3,
         "selected_model":"positional_250_alpha5","selected_numbers":"9700 0079 5555 1234 1235",
         "selected_hit":0,"uniform_numbers":"0097 7900 2222 3333 4444","uniform_hit":1},
    ]
    return history,grades,[78000,32000,None,15000]


class BoxFinanceTests(unittest.TestCase):
    def test_validity_of_box_play(self):
        self.assertFalse(box_valid("0000"))
        self.assertFalse(box_valid("1111"))
        self.assertTrue(box_valid("0011"))
        self.assertEqual(signature("0097"),signature("9700"))
        self.assertIsNone(parse_box_prize("","7777"))
        with self.assertRaisesRegex(ValueError,"all-equal"):
            parse_box_prize("25000","7777")
        with self.assertRaisesRegex(ValueError,"lacks published"):
            parse_box_prize("","0011")
        with self.assertRaises(ValueError):
            box_valid("999")

    def test_winning_draws_vs_tickets_and_per_ticket_payout(self):
        rows,grades,payouts=small_case()
        f=simulate_box(grades,rows,payouts)
        self.assertEqual(f["version"],REPLAY_VERSION)
        self.assertEqual(f["historical_winning_draws"],2)
        self.assertEqual(f["historical_winning_tickets"],4)
        self.assertEqual(f["simulated_payout_yen"],2*32000+2*15000)
        self.assertEqual(f["simulated_purchased_tickets"],11)  # 3+4+4
        self.assertEqual(f["excluded_ineligible_tickets"],4)
        self.assertEqual(f["simulated_ticket_cost_yen"],2200)
        self.assertEqual(f["simulated_net_yen"],91800)
        self.assertEqual(f["winning_rounds"][0]["winning_ticket_count"],2)
        self.assertEqual(f["winning_rounds"][0]["matched_tickets"][0]["predicted_number"],"4321")
        self.assertEqual(f["winning_rounds"][1]["winning_number"],"0097")
        self.assertEqual(f["winning_rounds"][1]["box_payout_yen_per_ticket"],15000)
        self.assertIsNone(f["actual_profit_yen"])
        self.assertFalse(f["bank_primary_payouts_verified"])

    def test_original_straight_flags_cannot_be_edited_for_box(self):
        rows,grades,payouts=small_case()
        grades[0]["selected_hit"]=0
        with self.assertRaisesRegex(ValueError,"STRAIGHT replay flags"):
            simulate_box(grades,rows,payouts)

    def test_missing_grades_or_future_cutoff_rejected(self):
        rows,grades,payouts=small_case()
        with self.assertRaises(ValueError):simulate_box(grades[:-1],rows,payouts)
        grades[0]["data_cutoff_round"]=3
        with self.assertRaisesRegex(ValueError,"chronology"):
            simulate_box(grades,rows,payouts)

    def make_fixture(self,root):
        rows,_,payouts=small_case()
        (root/"data").mkdir()
        raw=("round,draw_date,winning_number,box_payout_yen\n"+
             "".join(f"{r['round']},{r['draw_date']},{r['winning_number']},{'' if p is None else p}\n"
                     for r,p in zip(rows,payouts))).encode()
        (root/PAYOUT_CSV).write_bytes(raw)
        meta={
            "version":VERSION,"status":STATUS,"git_blob_sha1":_git_sha(raw),
            "record_count":4,"first_round":1,"last_round":4,
            "first_draw_date":"1994-10-07","last_draw_date":"1994-10-28",
            "first_number":"1149","latest_number":"0097",
            "eligible_box_draws":3,"ineligible_box_draws":1,
            "ticket_price_yen":200,
            "bank_primary_payouts_verified":False,
            "secondary_payout_independence_proven":False,
            "forecast_grading_authorized":False,
            "actual_purchase_records_present":False,
            "source":{"url":"https://github.com/hazimekom/numbers4-api/blob/"+"a"*40+
                      "/data/numbers4_results_v2.csv","commit_sha":"a"*40,"blob_sha":"b"*40}
        }
        (root/PAYOUT_META).write_text(json.dumps(meta))
        return rows,payouts

    def test_immutable_source_and_blank_4_equal_round(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            rows,payouts=self.make_fixture(root)
            got,_=load_box_payouts(root,rows)
            self.assertEqual(got,payouts)
            self.assertIsNone(got[2])

    def test_reject_tamper_in_amount(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            rows,_=self.make_fixture(root)
            p=root/PAYOUT_CSV
            p.write_text(p.read_text().replace("1234,32000","1234,32001"))
            with self.assertRaisesRegex(ValueError,"unsafe or mismatched"):
                load_box_payouts(root,rows)

    def test_reject_unauthorized_official_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            rows,_=self.make_fixture(root)
            p=root/PAYOUT_META
            meta=json.loads(p.read_text());meta["bank_primary_payouts_verified"]=True
            p.write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError,"unsafe or mismatched"):
                load_box_payouts(root,rows)

    def test_reject_payout_in_4_equal_draw_even_if_rehashed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            rows,_=self.make_fixture(root)
            p=root/PAYOUT_CSV
            p.write_text(p.read_text().replace("1111,\n","1111,75000\n"))
            meta_path=root/PAYOUT_META
            meta=json.loads(meta_path.read_text())
            meta["git_blob_sha1"]=_git_sha(p.read_bytes())
            meta_path.write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError,"all-equal"):
                load_box_payouts(root,rows)


if __name__=="__main__":
    unittest.main()
