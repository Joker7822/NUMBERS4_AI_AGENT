"""Compact public projection of the integrated historical audit."""
from __future__ import annotations
import json
import sys
from .integrated_audit import VERSION, integrate


def project(report: dict) -> dict:
    if report.get("version") != VERSION:
        raise ValueError("unexpected integrated audit version")
    # Recheck all cross-report provenance and authority invariants.
    r = integrate(report["historical_reports"], report["prospective_evidence"])
    if any(report.get(k) != r[k] for k in (
        "last_round", "last_draw_date", "archive_git_blob_sha1",
        "straight_payout_git_blob_sha1", "box_payout_git_blob_sha1",
        "actual_purchase", "production_promotion_authorized", "purchase_decision",
        "positive_expected_value_confirmed",
    )):
        raise ValueError("integrated report does not match validated evidence")
    h = r["historical_reports"]
    def returns(mode):
        x = h["returns"][mode]
        return {k: x[k] for k in ("evaluated_rounds", "expected_gross_recovery_percent",
                                 "simulated_loss_fraction", "simulations")}
    def risk(mode):
        x = h["cashflow"]["scenarios"][mode]
        return {k: x[k] for k in ("gross_recovery_percent", "hypothetical_net_yen",
                                 "maximum_settled_drawdown_yen",
                                 "longest_consecutive_losing_purchased_tickets")}
    def models(kind, key):
        return {name: {"evaluated_draws": v["all"]["evaluated_draws"],
                       "mean_log_edge": v["all"][key]}
                for name, v in h[kind]["models"].items()}
    payout = h["payouts"]["groups"]["straight"]["late_historical"]
    return {
        "version": "numbers4-public-integrated-research-v1",
        "scope": "secondary_history_only",
        **{k:r[k] for k in ("last_round", "last_draw_date", "archive_git_blob_sha1",
                           "straight_payout_git_blob_sha1", "box_payout_git_blob_sha1",
                           "actual_purchase", "production_promotion_authorized",
                           "positive_expected_value_confirmed", "purchase_decision")},
        "straight_reference": returns("straight"),
        "box_reference": returns("box_valid_ordered_uniform"),
        "straight_risk": risk("straight_selected"),
        "box_risk": risk("box_selected"),
        "cashflow_chart": {"version": "numbers4-cashflow-exceptions-v1",
                           "first_round": h["cashflow"]["first_evaluated_round"],
                           "last_round": r["last_round"], "default_cost_yen": 200,
                           "straight": h["cashflow"]["scenarios"]["straight_selected"]["cashflow_exceptions"],
                           "box": h["cashflow"]["scenarios"]["box_selected"]["cashflow_exceptions"]},
        "payout_late_count": payout["evaluated_observations"],
        "payout_mae_yen": {name: v["mae_yen"] for name, v in payout["models"].items()},
        "box_models": models("box", "mean_log_edge"),
        "ensemble_models": models("ensemble", "mean_log_edge_vs_uniform"),
    }


if __name__ == "__main__":
    print(json.dumps(project(json.load(sys.stdin)), ensure_ascii=False, indent=2, allow_nan=False))
