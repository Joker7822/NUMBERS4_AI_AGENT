"""Research-only BOX outcome distribution and probability calibration audit.

All 715 unordered outcomes, including 10 four-equal non-purchasable outcomes,
are scored. No ticket selection or promotion is performed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from itertools import combinations_with_replacement
import json
from math import fsum, log
from pathlib import Path

from .historical_archive import load_archive
from .rules import OUTCOMES, four_digits, permutation_count

VERSION = "numbers4-box-calibration-audit-v1"
WARMUP = 100
SPLIT_ROUND = 5000
PRIOR_STRENGTHS = (100, 1000, 10000)
SIGNATURES = tuple("".join(x) for x in combinations_with_replacement("0123456789", 4))
UNIFORM = tuple(permutation_count(s) / OUTCOMES for s in SIGNATURES)
INDEX = {s: i for i, s in enumerate(SIGNATURES)}
BASELINE_SQUARE_SUM = fsum(p * p for p in UNIFORM)


def signature(number: str) -> str:
    return "".join(sorted(four_digits(number)))


def posterior(counts: list[int], alpha: int) -> tuple[float, ...]:
    """A fixed Dirichlet shrinkage model centred on fair ordered outcomes."""
    if (type(alpha) is not int or alpha <= 0 or len(counts) != len(SIGNATURES)
            or any(type(c) is not int or c < 0 for c in counts)):
        raise ValueError("invalid counts or prior strength")
    denominator = sum(counts) + alpha
    return tuple((c + alpha * p) / denominator for c, p in zip(counts, UNIFORM))


def score(q: tuple[float, ...], actual: int) -> tuple[float, float]:
    """Positive edge means better than the theoretical uniform-ordered baseline."""
    if (len(q) != len(SIGNATURES) or type(actual) is not int
            or not 0 <= actual < len(SIGNATURES)
            or any(not 0 < p <= 1 for p in q)
            or abs(fsum(q) - 1) > 1e-10):
        raise ValueError("invalid outcome distribution")
    p = UNIFORM[actual]
    return (log(q[actual] / p),
            2 * (q[actual] - p) + BASELINE_SQUARE_SUM - fsum(x*x for x in q))


def pattern(number: str) -> str:
    return "".join(str(n) for n in sorted(Counter(number).values(), reverse=True))


PATTERNS = ("1111", "211", "22", "31", "4")
PATTERN_INDEX = tuple(PATTERNS.index(pattern(s)) for s in SIGNATURES)
BASE_PATTERN_PROBS = tuple(fsum(p for p, i in zip(UNIFORM, PATTERN_INDEX) if i == k)
                           for k in range(len(PATTERNS)))


def pattern_probs(q: tuple[float, ...]) -> tuple[float, ...]:
    masses = [0.0] * len(PATTERNS)
    for p, i in zip(q, PATTERN_INDEX):
        masses[i] += p
    return tuple(masses)


def _summary(events: list[tuple[int, float, float, tuple[float, ...], int]]) -> dict:
    n = len(events)
    if n == 0:
        return {"evaluated_draws": 0, "mean_log_edge": None,
                "mean_brier_edge": None, "pattern_calibration": {}}
    calibration = {}
    for i, name in enumerate(PATTERNS):
        predicted = fsum(e[3][i] for e in events) / n
        observed = sum(e[4] == i for e in events) / n
        calibration[name] = {
            "mean_predicted_probability": predicted,
            "observed_frequency": observed,
            "signed_calibration_gap": predicted - observed,
        }
    return {
        "evaluated_draws": n,
        "mean_log_edge": fsum(e[1] for e in events) / n,
        "mean_brier_edge": fsum(e[2] for e in events) / n,
        "pattern_calibration": calibration,
    }


def evaluate(history: list[dict], *, split_round: int = SPLIT_ROUND) -> dict:
    if not history or type(split_round) is not int or split_round < 1:
        raise ValueError("invalid history or split")
    counts = [0] * len(SIGNATURES)
    names = ("uniform_ordered", *(f"dirichlet_{a}" for a in PRIOR_STRENGTHS))
    events = {name: [] for name in names}
    previous_date = ""
    for i, row in enumerate(history):
        rnd, date = row["round"], row["draw_date"]
        if rnd != i + 1 or not isinstance(date, str) or date <= previous_date:
            raise ValueError("history is not consecutive and chronological")
        previous_date = date
        actual = INDEX[signature(row["winning_number"])]
        if i >= WARMUP:
            # Score all outcomes; no conditioning on purchasable outcomes.
            events[names[0]].append((rnd, 0.0, 0.0, BASE_PATTERN_PROBS,
                                      PATTERN_INDEX[actual]))
            for alpha, name in zip(PRIOR_STRENGTHS, names[1:]):
                q = posterior(counts, alpha)
                log_edge, brier_edge = score(q, actual)
                events[name].append((rnd, log_edge, brier_edge, pattern_probs(q),
                                     PATTERN_INDEX[actual]))
        # Only after scoring may the current observation enter the counts.
        counts[actual] += 1

    return {
        "unordered_outcome_classes": len(SIGNATURES),
        "valid_box_ticket_classes": len(SIGNATURES) - 10,
        "non_purchasable_outcome_classes_included_in_scoring": 10,
        "warmup_draws": WARMUP,
        "split_round": split_round,
        "uniform_baseline": "uniform_ordered_10000_induced_signature_distribution",
        "pattern_uniform_probabilities": dict(zip(PATTERNS, BASE_PATTERN_PROBS)),
        "models": {
            name: {
                "all": _summary(events[name]),
                "development": _summary([e for e in events[name] if e[0] <= split_round]),
                "late_historical": _summary([e for e in events[name] if e[0] > split_round]),
            } for name in names
        },
        "late_cohort_is_independent_holdout": False,
        "current_outcome_used_as_feature": False,
        "model_selection_performed": False,
        "pattern_calibration_is_descriptive_only": True,
    }


def audit(root: Path) -> dict:
    history, meta = load_archive(root)
    if not history:
        raise ValueError("historical archive missing")
    return {
        "version": VERSION,
        "status": "secondary_history_retrospective_research_only",
        "first_round": history[0]["round"],
        "last_round": history[-1]["round"],
        "first_draw_date": history[0]["draw_date"],
        "last_draw_date": history[-1]["draw_date"],
        "archive_git_blob_sha1": meta["git_blob_sha1"],
        **evaluate(history),
        "officially_verified": False,
        "prospective_skill_confirmed": False,
        "positive_expected_value_confirmed": False,
        "production_promotion_authorized": False,
        "actual_purchase": False,
        "purchase_decision": "SKIP",
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
