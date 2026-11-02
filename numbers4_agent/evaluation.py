"""Grade only pre-issued tickets against consistent two-source observations."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path

from .rules import grade_number, theoretical_odds, PRICE_PER_TICKET_YEN
from .ledger import read_issued
from .models import ranked_candidates
from .sources import JST, corroborated_draws, reconcile


def graded_predictions(root: Path) -> list[dict]:
    trusted = {r["round"]: r for r in corroborated_draws(root)}
    result = []
    for issue in read_issued(root):
        draw = trusted.get(issue["target_round"])
        if draw is None:
            continue
        if draw["draw_date"] != issue["draw_date"]:
            raise ValueError("official draw date disagrees with issued forecast")
        if datetime.fromisoformat(issue["issued_at_jst"]).astimezone(JST) >= datetime.fromisoformat(issue["freeze_deadline_jst"]).astimezone(JST):
            raise ValueError("pre-draw integrity failure")
        verdicts = [grade_number(n, draw["winning_number"], issue["mode"]) for n in issue["numbers"]]
        result.append({
            "round": draw["round"], "date": draw["draw_date"],
            "winning_number": draw["winning_number"],
            "mode": issue["mode"], "numbers": issue["numbers"],
            "tickets": [{"number": n, "result": g} for n, g in zip(issue["numbers"], verdicts)],
            "winning_tickets": sum(g != "miss" for g in verdicts),
            "issued_at_jst": issue["issued_at_jst"],
            "verification": ("bank_primary_rakuten_publication_match" if draw["status"] == "auto_verified_two_publishers" else "two_source_manual_attestations_consistent"),
            "actual_purchase": False, "actual_profit_yen": None,
            "reference_cost_yen": len(issue["numbers"]) * PRICE_PER_TICKET_YEN,
        })
    return sorted(result, key=lambda row: row["round"])


def walk_forward(root: Path, *, min_history: int = 30) -> dict:
    draws = sorted(corroborated_draws(root), key=lambda r: r["round"])
    if len(draws) < min_history + 1:
        return {"status": "insufficient_history", "trusted_draws": len(draws),
                "evaluated_draws": 0, "forecast_skill_confirmed": False}
    outcomes = []
    for i in range(min_history, len(draws)):
        target = draws[i]
        guess = ranked_candidates(draws[:i], target["round"], method="positional", count=1)
        hits = sum(grade_number(n, target["winning_number"], "straight") == "straight"
                   for n in guess["numbers"])
        outcomes.append(hits)
    return {
        "status": "historical_exploratory_only", "trusted_draws": len(draws),
        "evaluated_draws": len(outcomes), "straight_hit_draws": sum(outcomes),
        "straight_hit_rate": sum(outcomes) / len(outcomes),
        "uniform_hit_probability": 1 / 10_000,
        "forecast_skill_confirmed": False,
        "selection_bias_note": "No prospective registered test; retrospective fit does not establish predictive skill",
        "realized_purchase_profit": None,
    }
