"""Read-only historical cash-flow risk audit. Not a purchase or staking policy."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .box_finance import box_valid, load_box_payouts, signature, simulate_box
from .finance import load_payouts, summarize_reconstruction
from .historical_archive import load_archive
from .online_learning import replay
from .rules import PRICE_PER_TICKET_YEN, four_digits

VERSION = "numbers4-cashflow-risk-audit-v1"


def cashflow_metrics(events: list[tuple[int, int, int]]) -> dict:
    """Events are (round, hypothetical cost, payout); zero-cost rounds are skips.

    Drawdown measures settled cumulative net from its prior peak (including zero).
    Pre-settlement shortfall separately accounts for paying the ticket before
    receiving the prize. Neither is a recommendation about bankroll size.
    """
    if not events:
        raise ValueError("cash-flow events required")
    previous = 0
    spend = payout = balance = peak = 0
    min_balance = max_drawdown = max_shortfall = 0
    misses = max_misses = bought = skips = hits = 0
    drawdown_round = None
    longest_miss_end_round = None
    for rnd, cost, award in events:
        if (type(rnd) is not int or rnd <= previous
                or type(cost) is not int or cost not in (0, PRICE_PER_TICKET_YEN)
                or type(award) is not int or award < 0
                or (cost == 0 and award != 0)):
            raise ValueError("invalid chronological one-ticket cash flow")
        previous = rnd
        spend += cost
        payout += award
        max_shortfall = max(max_shortfall, cost - balance)
        balance += award - cost
        min_balance = min(min_balance, balance)
        peak = max(peak, balance)
        if peak - balance > max_drawdown:
            max_drawdown = peak - balance
            drawdown_round = rnd
        if cost == 0:
            skips += 1
        else:
            bought += 1
            if award:
                hits += 1
                misses = 0
            else:
                misses += 1
                if misses > max_misses:
                    max_misses = misses
                    longest_miss_end_round = rnd
    return {
        "evaluated_draws": len(events),
        "hypothetical_purchased_tickets": bought,
        "skipped_draws": skips,
        "winning_tickets": hits,
        "hypothetical_spend_yen": spend,
        "hypothetical_payout_yen": payout,
        "hypothetical_net_yen": balance,
        "gross_recovery_percent": 100 * payout / spend if spend else None,
        "net_roi_percent": 100 * balance / spend if spend else None,
        "minimum_settled_cumulative_net_yen": min_balance,
        "maximum_settled_drawdown_yen": max_drawdown,
        "maximum_drawdown_end_round": drawdown_round,
        "maximum_pre_settlement_shortfall_yen": max_shortfall,
        "longest_consecutive_losing_purchased_tickets": max_misses,
        "longest_losing_streak_end_round": longest_miss_end_round,
        "ending_consecutive_losing_purchased_tickets": misses,
    }


def _events(grades: list[dict], history: list[dict], straight: list[int],
            box: list[int | None], mode: str, reference: bool) -> list[tuple[int, int, int]]:
    if mode not in ("straight", "box"):
        raise ValueError("unsupported risk scenario")
    key = "uniform_numbers" if reference else "selected_numbers"
    result = []
    for i, grade in enumerate(grades, 1):
        number = four_digits(grade[key])
        actual = history[i]["winning_number"]
        if mode == "straight":
            cost = PRICE_PER_TICKET_YEN
            award = straight[i] if number == actual else 0
        elif not box_valid(number):
            cost = award = 0
        else:
            cost = PRICE_PER_TICKET_YEN
            award = box[i] if signature(number) == signature(actual) else 0
            if award is None:
                raise ValueError("missing matched BOX payout")
        result.append((history[i]["round"], cost, award))
    return result


def evaluate(grades: list[dict], history: list[dict], straight: list[int],
             box: list[int | None]) -> dict:
    # Reuse existing strict replay and finance validators before computing risk.
    s = summarize_reconstruction(grades, history, straight)
    b = simulate_box(grades, history, box)
    scenarios = {}
    for mode, original in (("straight", s), ("box", b)):
        for reference in (False, True):
            events = _events(grades, history, straight, box, mode, reference)
            metrics = cashflow_metrics(events)
            if not reference:
                metrics["cashflow_exceptions"] = [[rnd, cost, award] for rnd, cost, award in events
                                                  if cost != PRICE_PER_TICKET_YEN or award != 0]
            prefix = "baseline_" if reference else ""
            expected_spend = (original["baseline_ticket_cost_yen"]
                              if reference and mode == "box"
                              else original["simulated_ticket_cost_yen"])
            expected_payout = original[prefix + "simulated_payout_yen"]
            expected_net = original[prefix + "simulated_net_yen"]
            if (metrics["hypothetical_spend_yen"] != expected_spend
                    or metrics["hypothetical_payout_yen"] != expected_payout
                    or metrics["hypothetical_net_yen"] != expected_net):
                raise ValueError("risk cash flow disagrees with validated historical finance")
            scenarios[mode + ("_uniform_reference" if reference else "_selected")] = metrics
    scenarios["no_purchase"] = cashflow_metrics(
        [(row["round"], 0, 0) for row in history[1:]])
    return scenarios


def audit(root: Path) -> dict:
    history, meta = load_archive(root)
    if len(history) < 2:
        raise ValueError("historical archive missing or insufficient")
    straight, smeta = load_payouts(root, history)
    box, bmeta = load_box_payouts(root, history)
    return _audit_loaded(history, meta, straight, smeta, box, bmeta)


def _audit_loaded(history, meta, straight, smeta, box, bmeta) -> dict:
    """Internal report builder; callers must use validated loader results."""
    if len(history) < 2:
        raise ValueError("historical archive missing or insufficient")
    _, grades = replay(history)
    return {
        "version": VERSION,
        "status": "secondary_history_retrospective_risk_only",
        "first_evaluated_round": history[1]["round"],
        "last_evaluated_round": history[-1]["round"],
        "first_evaluated_date": history[1]["draw_date"],
        "last_evaluated_date": history[-1]["draw_date"],
        "archive_git_blob_sha1": meta["git_blob_sha1"],
        "straight_payout_git_blob_sha1": smeta["git_blob_sha1"],
        "box_payout_git_blob_sha1": bmeta["git_blob_sha1"],
        "scenarios": evaluate(grades, history, straight, box),
        "actual_purchase": False,
        "actual_bankroll_known": False,
        "bank_primary_payouts_verified": False,
        "prospective_skill_confirmed": False,
        "production_promotion_authorized": False,
        "purchase_decision": "SKIP",
        "interpretation": "Historical hypothetical cash flows only; no future loss bound or bankroll recommendation.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    try:
        result = audit(args.root.resolve())
    except (ValueError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
