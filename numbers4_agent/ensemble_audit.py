"""Research-only exact joint-distribution ensemble scoring; no ticket ranking."""
from __future__ import annotations

import argparse
import json
from math import fsum, isfinite, log, prod
from pathlib import Path

from .historical_archive import load_archive
from .online_learning import MODELS, RollingPositionCounts
from .rules import four_digits

VERSION = "numbers4-ensemble-score-audit-v1"
WARMUP = 1000
SPLIT_ROUND = 5000
UNIFORM = [[0.1] * 10 for _ in range(4)]
WEIGHTS = {
    "uniform": (1.0, 0.0, 0.0, 0.0),
    "equal_experts": (0.0, 1/3, 1/3, 1/3),
    "uniform50": (0.5, 1/6, 1/6, 1/6),
    "uniform90": (0.9, 1/30, 1/30, 1/30),
}


def joint_dot(a: list[list[float]], b: list[list[float]]) -> float:
    """Inner product over all 10,000 ordered outcomes, by factorization."""
    return prod(fsum(x*y for x, y in zip(u, v)) for u, v in zip(a, b))


def components(experts: list[list[list[float]]], actual: str) -> tuple[list, list]:
    digits = tuple(map(int, four_digits(actual)))
    if not experts or any(
        len(q) != 4 or any(len(v) != 10 or any(not isfinite(p) or p <= 0 for p in v)
                           or abs(fsum(v)-1) > 1e-10 for v in q)
        for q in experts
    ):
        raise ValueError("invalid expert probability distribution")
    masses = [prod(q[i][d] for i, d in enumerate(digits)) for q in experts]
    dots = [[joint_dot(a, b) for b in experts] for a in experts]
    return masses, dots


def mixture_score(masses: list, dots: list, weights: tuple[float, ...]) -> tuple[float, float]:
    """Score a mixture of JOINT distributions, not products of mixed marginals."""
    n = len(masses)
    if (n == 0 or len(weights) != n or len(dots) != n
            or any(len(row) != n for row in dots)
            or any(not isfinite(w) or w < 0 for w in weights)
            or abs(fsum(weights)-1) > 1e-10):
        raise ValueError("invalid mixture weights or components")
    p = fsum(w*x for w, x in zip(weights, masses))
    norm2 = fsum(weights[i]*weights[j]*dots[i][j]
                 for i in range(n) for j in range(n))
    if not isfinite(p) or not 0 < p <= 1 or not isfinite(norm2):
        raise ValueError("invalid joint mixture")
    return log(p/0.0001), 2*p-norm2-0.0001


def _summary(events: list[tuple[int, float, float]]) -> dict:
    n = len(events)
    return {
        "evaluated_draws": n,
        "mean_log_edge_vs_uniform": fsum(e[1] for e in events)/n if n else None,
        "mean_brier_edge_vs_uniform": fsum(e[2] for e in events)/n if n else None,
    }


def evaluate(history: list[dict], *, split_round: int = SPLIT_ROUND) -> dict:
    if not history or type(split_round) is not int or split_round < 1:
        raise ValueError("invalid history or split")
    windows = [RollingPositionCounts(length) for _, length, _ in MODELS]
    events = {name: [] for name in WEIGHTS}
    previous_date = ""
    for i, row in enumerate(history):
        rnd, date = row["round"], row["draw_date"]
        if type(rnd) is not int or rnd != i+1 or not isinstance(date, str) or date <= previous_date:
            raise ValueError("history must be consecutive and chronological")
        previous_date = date
        actual = four_digits(row["winning_number"])
        if i >= WARMUP:
            experts = [UNIFORM, *(window.probabilities(spec[2])
                                  for window, spec in zip(windows, MODELS))]
            masses, dots = components(experts, actual)
            for name, weights in WEIGHTS.items():
                edge, brier = mixture_score(masses, dots, weights)
                events[name].append((rnd, edge, brier))
        # The current outcome is added only after all models have been scored.
        for window in windows:
            window.append(actual)

    return {
        "warmup_draws": WARMUP,
        "split_round": split_round,
        "expert_names": ["uniform", *(s[0] for s in MODELS)],
        "fixed_weights": {name: list(w) for name, w in WEIGHTS.items()},
        "models": {
            name: {
                "all": _summary(rows),
                "development": _summary([e for e in rows if e[0] <= split_round]),
                "late_historical": _summary([e for e in rows if e[0] > split_round]),
            } for name, rows in events.items()
        },
        "mixture_of_joint_distributions": True,
        "current_outcome_used_as_feature": False,
        "late_cohort_is_independent_holdout": False,
        "weights_selected_from_results": False,
        "model_selection_performed": False,
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
