"""Research-only, prior-observation payout forecast comparison.

No number recommendations, promotion, purchase decisions, or official verification.
"""
from __future__ import annotations

from collections import Counter
from math import sqrt
from pathlib import Path

from .box_finance import load_box_payouts
from .finance import load_payouts
from .historical_archive import load_archive
from .rules import four_digits

VERSION = "numbers4-payout-forecast-audit-v1"
WARMUP = 100
SPLIT_ROUND = 5000
MODELS = ("expanding_mean", "rolling_30", "rolling_100")
GROUPS = ("straight", "box_1111", "box_211", "box_22", "box_31")


def box_group(number: str) -> str | None:
    counts = sorted(Counter(four_digits(number)).values(), reverse=True)
    if counts == [4]:
        return None
    return "box_" + "".join(str(n) for n in counts)


def prior_estimates(values: list[int]) -> dict[str, float] | None:
    """All three models use the same 100-observation warmup and past only."""
    if len(values) < WARMUP:
        return None
    return {
        "expanding_mean": sum(values) / len(values),
        "rolling_30": sum(values[-30:]) / 30,
        "rolling_100": sum(values[-100:]) / 100,
    }


def _metrics(events: list[tuple[int, int, dict[str, float]]]) -> dict:
    n = len(events)
    if not n:
        return {"evaluated_observations": 0, "models": {}}
    models = {}
    for name in MODELS:
        errors = [predictions[name] - actual for _, actual, predictions in events]
        models[name] = {
            "mae_yen": sum(abs(e) for e in errors) / n,
            "rmse_yen": sqrt(sum(e * e for e in errors) / n),
            "mean_error_yen": sum(errors) / n,
        }
    return {"evaluated_observations": n, "models": models}


def evaluate(history: list[dict], straight: list[int], box: list[int | None],
             *, split_round: int = SPLIT_ROUND) -> dict:
    if (not history or len(history) != len(straight) or len(history) != len(box)
            or type(split_round) is not int or split_round < 1):
        raise ValueError("invalid aligned payout history or split")
    observed: dict[str, list[int]] = {g: [] for g in GROUPS}
    events: dict[str, list[tuple[int, int, dict[str, float]]]] = {g: [] for g in GROUPS}
    previous_date = ""
    for index, row in enumerate(history):
        rnd = row["round"]
        date = row["draw_date"]
        if rnd != index + 1 or not isinstance(date, str) or date <= previous_date:
            raise ValueError("payout history is not chronological")
        previous_date = date
        group = box_group(row["winning_number"])
        s, b = straight[index], box[index]
        if type(s) is not int or s <= 0:
            raise ValueError("invalid straight payout")
        if group is None:
            if b is not None:
                raise ValueError("four-equal BOX has no payout")
        elif type(b) is not int or b <= 0:
            raise ValueError("invalid eligible BOX payout")

        # Form every conditional group estimate before consuming this draw.
        # The actual BOX group is used only to select which estimate to grade.
        predictions = {g: prior_estimates(observed[g]) for g in GROUPS}
        outcomes = [("straight", s)]
        if group is not None:
            outcomes.append((group, b))
        for g, actual in outcomes:
            estimate = predictions[g]
            if estimate is not None:
                events[g].append((rnd, actual, estimate))
            observed[g].append(actual)

    return {
        "groups": {
            g: {
                "total_observations": len(observed[g]),
                "all": _metrics(events[g]),
                "development": _metrics([e for e in events[g] if e[0] <= split_round]),
                "late_historical": _metrics([e for e in events[g] if e[0] > split_round]),
            } for g in GROUPS
        },
        "warmup_observations_per_group": WARMUP,
        "split_round": split_round,
        "late_cohort_is_independent_holdout": False,
        "model_selection_performed": False,
        "current_draw_payout_used_as_feature": False,
        "box_group_used_only_for_conditional_scoring": True,
        "number_level_payout_prediction": False,
    }


def audit(root: Path) -> dict:
    history, archive = load_archive(root)
    if not history:
        raise ValueError("historical archive missing")
    straight, straight_meta = load_payouts(root, history)
    box, box_meta = load_box_payouts(root, history)
    return {
        "version": VERSION,
        "status": "secondary_history_retrospective_research_only",
        "first_round": history[0]["round"],
        "last_round": history[-1]["round"],
        "first_draw_date": history[0]["draw_date"],
        "last_draw_date": history[-1]["draw_date"],
        "archive_git_blob_sha1": archive["git_blob_sha1"],
        "straight_payout_git_blob_sha1": straight_meta["git_blob_sha1"],
        "box_payout_git_blob_sha1": box_meta["git_blob_sha1"],
        **evaluate(history, straight, box),
        "bank_primary_payouts_verified": False,
        "prospective_skill_confirmed": False,
        "positive_expected_value_confirmed": False,
        "production_promotion_authorized": False,
        "actual_purchase": False,
        "purchase_decision": "SKIP",
        "interpretation": (
            "Conditional historical payout-error comparison, not a forecast of the winning "
            "number, future payout guarantee, purchase recommendation, or evidence of return improvement."
        ),
    }
