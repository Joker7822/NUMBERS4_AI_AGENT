import tempfile
import unittest
from pathlib import Path

from numbers4_agent.cashflow_risk import audit, cashflow_metrics, evaluate


class CashflowRiskTests(unittest.TestCase):
    def test_drawdown_differs_from_final_loss(self):
        r = cashflow_metrics([(2, 200, 0), (3, 200, 1000),
                              (4, 200, 0), (5, 200, 0)])
        self.assertEqual(r["hypothetical_net_yen"], 200)
        self.assertEqual(r["maximum_settled_drawdown_yen"], 400)
        self.assertEqual(r["maximum_drawdown_end_round"], 5)
        self.assertEqual(r["minimum_settled_cumulative_net_yen"], -200)
        self.assertEqual(r["maximum_pre_settlement_shortfall_yen"], 400)
        self.assertEqual(r["longest_consecutive_losing_purchased_tickets"], 2)

    def test_skips_do_not_reset_or_extend_ticket_losing_streak(self):
        r = cashflow_metrics([(2, 200, 0), (3, 0, 0), (4, 200, 0)])
        self.assertEqual(r["skipped_draws"], 1)
        self.assertEqual(r["ending_consecutive_losing_purchased_tickets"], 2)
        self.assertEqual(r["longest_losing_streak_end_round"], 4)

    def test_no_purchase_has_no_recovery_ratio(self):
        r = cashflow_metrics([(2, 0, 0), (3, 0, 0)])
        self.assertIsNone(r["gross_recovery_percent"])
        self.assertIsNone(r["net_roi_percent"])
        self.assertEqual(r["maximum_settled_drawdown_yen"], 0)

    def test_prize_after_cost(self):
        r = cashflow_metrics([(2, 200, 900000)])
        self.assertEqual(r["maximum_pre_settlement_shortfall_yen"], 200)
        self.assertEqual(r["maximum_settled_drawdown_yen"], 0)

    def test_invalid_events_fail(self):
        for events in ([], [(1, 0, 10)], [(1, 400, 0)], [(1, 200, -1)],
                       [(2, 200, 0), (2, 200, 0)]):
            with self.assertRaises(ValueError):
                cashflow_metrics(events)

    def test_replay_finance_reconciliation_and_box_skip(self):
        history = [
            {"round": 1, "draw_date": "2020-01-01", "winning_number": "1234"},
            {"round": 2, "draw_date": "2020-01-02", "winning_number": "0123"},
            {"round": 3, "draw_date": "2020-01-03", "winning_number": "0000"},
        ]
        grades = [
            {"round": 2, "draw_date": "2020-01-02", "actual": "0123",
             "data_cutoff_round": 1, "selected_model": "uniform",
             "selected_numbers": "3210", "selected_hit": 0,
             "uniform_numbers": "0123", "uniform_hit": 1},
            {"round": 3, "draw_date": "2020-01-03", "actual": "0000",
             "data_cutoff_round": 2, "selected_model": "uniform",
             "selected_numbers": "0000", "selected_hit": 1,
             "uniform_numbers": "9999", "uniform_hit": 0},
        ]
        r = evaluate(grades, history, [900000]*3, [37500, 37500, None])
        self.assertEqual(r["straight_selected"]["hypothetical_payout_yen"], 900000)
        self.assertEqual(r["box_selected"]["hypothetical_payout_yen"], 37500)
        self.assertEqual(r["box_selected"]["skipped_draws"], 1)
        self.assertEqual(r["box_uniform_reference"]["hypothetical_spend_yen"], 200)
        self.assertIsNone(r["no_purchase"]["gross_recovery_percent"])
        grades[0]["selected_hit"] = 1
        with self.assertRaises(ValueError):
            evaluate(grades, history, [900000]*3, [37500, 37500, None])

    def test_missing_archive_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                audit(Path(directory))


if __name__ == "__main__":
    unittest.main()
