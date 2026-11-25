"""Read-only historical return benchmark; never a forecast or purchase signal."""
from __future__ import annotations

from math import floor, fsum, log1p, sqrt
from pathlib import Path
from random import Random

from .box_finance import load_box_payouts
from .finance import load_payouts
from .historical_archive import load_archive
from .rules import OUTCOMES, PRICE_PER_TICKET_YEN, permutation_count, four_digits

VERSION = "numbers4-historical-return-audit-v1"
VALID_BOX_ORDERED_OUTCOMES = OUTCOMES - 10
MAX_SIMULATIONS = 100_000


def recovery_percent(payout_yen: float, spend_yen: int) -> float | None:
    """Gross recovery, not net ROI; zero spend has no defined recovery."""
    if spend_yen < 0 or payout_yen < 0:
        raise ValueError("negative payout or spend")
    return 100 * payout_yen / spend_yen if spend_yen else None


def uniform_events(history: list[dict], straight: list[int],
                   box: list[int | None], mode: str) -> list[tuple[float, int]]:
    """Rounds 2 onward; condition on observed draws and recorded payouts.

    BOX samples uniformly among the 9,990 valid ordered strings, NOT among
    the 705 distinct unordered BOX signatures. Four-equal actuals cannot win.
    """
    if len(history) < 2 or len(history) != len(straight) or len(history) != len(box):
        raise ValueError("incomplete historical data")
    if mode not in ("straight", "box"):
        raise ValueError("unsupported historical benchmark mode")
    events = []
    for i, row in enumerate(history):
        number = four_digits(row["winning_number"])
        if row["round"] != i + 1:
            raise ValueError("historical rounds must be consecutive")
        if type(straight[i]) is not int or straight[i] <= 0:
            raise ValueError("invalid straight payout")
        if len(set(number)) == 1:
            if box[i] is not None:
                raise ValueError("four-equal BOX cannot have a payout")
        elif type(box[i]) is not int or box[i] <= 0:
            raise ValueError("missing eligible BOX payout")
        if i == 0:
            continue
        if mode == "straight":
            events.append((1 / OUTCOMES, straight[i]))
        elif box[i] is None:
            events.append((0.0, 0))
        else:
            events.append((permutation_count(number) / VALID_BOX_ORDERED_OUTCOMES, box[i]))
    return events


def benchmark(events: list[tuple[float, int]], *, simulations: int = 10_000,
              seed: int = 20261126) -> dict:
    """Exact conditional moments plus reproducible independent-ticket simulation.

    Geometric thinning avoids iterating every draw in every simulation.
    Quantiles describe hypothetical outcomes, not confidence in future returns.
    """
    if type(simulations) is not int or not 1 <= simulations <= MAX_SIMULATIONS:
        raise ValueError("simulations must be an integer from 1 to 100000")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if not events or any(not 0 <= p < 1 or type(y) is not int or y < 0 for p, y in events):
        raise ValueError("invalid benchmark events")
    spend = len(events) * PRICE_PER_TICKET_YEN
    mean = fsum(p * y for p, y in events)
    variance = fsum(p * (1 - p) * y * y for p, y in events)
    max_p = max(p for p, _ in events)
    rng = Random(seed)
    totals = []
    log_survival = log1p(-max_p) if max_p else None
    for _ in range(simulations):
        total = 0
        if log_survival is not None:
            index = -1
            while True:
                index += 1 + floor(log1p(-rng.random()) / log_survival)
                if index >= len(events):
                    break
                p, y = events[index]
                if rng.random() < p / max_p:
                    total += y
        totals.append(total)
    totals.sort()

    def quantile(q: float) -> float:
        return recovery_percent(totals[floor(q * (simulations - 1))], spend)

    return {
        "evaluated_rounds": len(events),
        "hypothetical_spend_yen": spend,
        "expected_hits": fsum(p for p, _ in events),
        "expected_payout_yen": mean,
        "expected_gross_recovery_percent": recovery_percent(mean, spend),
        "expected_net_roi_percent": recovery_percent(mean, spend) - 100,
        "conditional_recovery_sd_percentage_points": 100 * sqrt(variance) / spend,
        "simulations": simulations,
        "seed": seed,
        "simulated_mean_gross_recovery_percent": recovery_percent(fsum(totals) / simulations, spend),
        "simulated_gross_recovery_quantiles_percent": {
            "p025": quantile(.025), "p50": quantile(.5), "p975": quantile(.975),
        },
        "simulated_loss_fraction": sum(y < spend for y in totals) / simulations,
        "simulated_zero_payout_fraction": sum(y == 0 for y in totals) / simulations,
    }


def audit(root: Path, *, simulations: int = 10_000, seed: int = 20261126) -> dict:
    history, archive_meta = load_archive(root)
    if len(history) < 2:
        raise ValueError("at least two historical draws are required")
    straight, straight_meta = load_payouts(root, history)
    box, box_meta = load_box_payouts(root, history)
    return {
        "version": VERSION,
        "status": "secondary_history_conditional_benchmark_only",
        "first_evaluated_round": history[1]["round"],
        "last_evaluated_round": history[-1]["round"],
        "first_evaluated_date": history[1]["draw_date"],
        "last_evaluated_date": history[-1]["draw_date"],
        "ticket_unit_cost_yen": PRICE_PER_TICKET_YEN,
        "straight": benchmark(uniform_events(history, straight, box, "straight"),
                              simulations=simulations, seed=seed),
        "box_valid_ordered_uniform": benchmark(uniform_events(history, straight, box, "box"),
                                               simulations=simulations, seed=seed + 1),
        "archive_git_blob_sha1": archive_meta["git_blob_sha1"],
        "straight_payout_git_blob_sha1": straight_meta["git_blob_sha1"],
        "box_payout_git_blob_sha1": box_meta["git_blob_sha1"],
        "bank_primary_payouts_verified": False,
        "prospective_skill_confirmed": False,
        "actual_purchase": False,
        "production_promotion_authorized": False,
        "purchase_decision": "SKIP",
        "interpretation": (
            "Historical conditional random-ticket distribution, assuming fixed recorded payouts "
            "and one independent valid ticket per draw. BOX denominator differs from regrading "
            "a straight ticket that may be invalid. Not a future forecast or confidence interval; "
            "no verified positive expected value, no purchase recommendation."
        ),
    }
