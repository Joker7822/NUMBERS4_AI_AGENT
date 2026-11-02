"""Historical finance is a simulation, never a real lottery purchase."""
import json
import tempfile
import unittest
from pathlib import Path

from numbers4_agent.finance import (
    PAYOUT_CSV, PAYOUT_META, STATUS, git_blob_sha1, load_payouts,
    summarize_reconstruction,
)


def sample():
    rows=[
        {"round":1,"draw_date":"1994-10-07","winning_number":"1149"},
        {"round":2,"draw_date":"1994-10-14","winning_number":"0097"},
        {"round":3,"draw_date":"1994-10-21","winning_number":"1234"}
    ]
    grades=[
        {"round":2,"draw_date":"1994-10-14","actual":"0097",
         "data_cutoff_round":1,"selected_model":"uniform",
         "selected_numbers":"0001 0002 0097 0004 0005","selected_hit":1,
         "uniform_numbers":"1000 1001 1002 1003 1004","uniform_hit":0},
        {"round":3,"draw_date":"1994-10-21","actual":"1234",
         "data_cutoff_round":2,"selected_model":"positional_250_alpha5",
         "selected_numbers":"2222 3333 4444 5555 6666","selected_hit":0,
         "uniform_numbers":"1234 8888 1111 9999 0000","uniform_hit":1},
    ]
    payouts=[1000000,900000,1100000]
    return rows,grades,payouts


class FinanceTests(unittest.TestCase):
    def test_only_nonmiss_results_and_net_costs(self):
        rows,grades,payouts=sample()
        r=summarize_reconstruction(grades,rows,payouts)
        self.assertEqual(r["evaluated_rounds"],2)
        self.assertEqual(r["simulated_ticket_cost_yen"],2000)
        self.assertEqual(r["simulated_payout_yen"],900000)
        self.assertEqual(r["simulated_net_yen"],898000)
        self.assertEqual(r["historical_winning_draws"],1)
        self.assertEqual(r["baseline_simulated_net_yen"],1098000)
        self.assertEqual(r["winning_rounds"][0]["matched_prediction"],"0097")
        self.assertEqual(r["winning_rounds"][0]["ticket_position"],3)
        self.assertIsNone(r["actual_profit_yen"])
        self.assertFalse(r["bank_primary_payouts_verified"])

    def test_forged_replay_wins_fail(self):
        rows,grades,payouts=sample()
        grades[0]["selected_hit"]=0
        with self.assertRaisesRegex(ValueError,"reported win count"):
            summarize_reconstruction(grades,rows,payouts)

    def test_duplicate_numbers_fail(self):
        rows,grades,payouts=sample()
        grades[0]["selected_numbers"]="0097 0097 0003 0004 0005"
        with self.assertRaisesRegex(ValueError,"invalid number"):
            summarize_reconstruction(grades,rows,payouts)

    def write_fixture(self,root):
        rows,grades,payouts=sample()
        folder=root/"data"
        folder.mkdir()
        raw=("round,draw_date,winning_number,straight_payout_yen\n"+
             "".join(f"{r['round']},{r['draw_date']},{r['winning_number']},{p}\n"
                     for r,p in zip(rows,payouts))).encode()
        (root/PAYOUT_CSV).write_bytes(raw)
        (root/PAYOUT_META).write_text(json.dumps({
            "version":"numbers4-secondary-straight-payouts-v1",
            "status":STATUS,"git_blob_sha1":git_blob_sha1(raw),
            "record_count":3,"first_round":1,"last_round":3,
            "first_draw_date":"1994-10-07","last_draw_date":"1994-10-21",
            "first_number":"1149","latest_number":"1234",
            "ticket_price_yen":200,"bank_primary_payouts_verified":False,
            "secondary_payout_independence_proven":False,
            "forecast_grading_authorized":False,"actual_purchase_records_present":False,
            "source":{"url":"https://github.com/hazimekom/numbers4-api/blob/"+"a"*40+
                      "/data/numbers4_results_v2.csv",
                      "commit_sha":"a"*40,"blob_sha":"b"*40}
        }))
        return rows,payouts

    def test_payout_archive_matches_and_leading_zero_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            rows,payouts=self.write_fixture(root)
            got,meta=load_payouts(root,rows)
            self.assertEqual(got,payouts)
            self.assertEqual(meta["status"],STATUS)

    def test_payout_tamper_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            rows,_=self.write_fixture(root)
            p=root/PAYOUT_CSV
            p.write_text(p.read_text().replace("0097,900000","0097,900001"))
            with self.assertRaisesRegex(ValueError,"safe provenance"):
                load_payouts(root,rows)

    def test_payout_wrong_draw_fails_even_with_rehash(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            rows,_=self.write_fixture(root)
            p=root/PAYOUT_CSV
            p.write_text(p.read_text().replace("0097,900000","0098,900000"))
            m=root/PAYOUT_META
            meta=json.loads(m.read_text())
            meta["git_blob_sha1"]=git_blob_sha1(p.read_bytes())
            m.write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError,"do not match historical"):
                load_payouts(root,rows)

    def test_payout_claimed_official_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            rows,_=self.write_fixture(root)
            m=root/PAYOUT_META
            meta=json.loads(m.read_text())
            meta["bank_primary_payouts_verified"]=True
            m.write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError,"safe provenance"):
                load_payouts(root,rows)


if __name__=="__main__":
    unittest.main()
