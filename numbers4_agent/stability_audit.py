"""Descriptive block-resampling stability audit of fixed historical score series.

Repeatedly used history is not prospective evidence. No predictions, model
selection, ticket rankings or purchase authorization are emitted.
"""
from __future__ import annotations

import argparse
import json
from math import ceil, floor, fsum, isfinite
from pathlib import Path
from random import Random

from .historical_archive import load_archive
from .online_learning import replay

VERSION = "numbers4-retrospective-stability-v1"
SERIES = ("selected_log_edge", "positional_60_log_edge",
          "positional_250_log_edge", "positional_1000_log_edge")
BLOCK_LENGTHS = (20, 100)
SPLIT_ROUND = 5000
REPLICATES = 10000
SEED = 20261126
NOMINAL_ALPHA = 0.05
COMPARISONS = len(SERIES) * len(BLOCK_LENGTHS) * 3


def _quantile(ordered, probability):
    # Linear interpolation between adjacent order statistics.
    position = probability * (len(ordered) - 1)
    lo, hi = floor(position), ceil(position)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def _circular_sums(values, length):
    extended = values + values[:length-1]
    prefix = [0.0]
    for value in extended:
        prefix.append(prefix[-1] + value)
    return [prefix[i+length] - prefix[i] for i in range(len(values))]


def resample(series: dict[str, list[float]], *, block_length: int,
             replicates: int, seed: int) -> dict:
    """Circular moving blocks; common random starts preserve paired sampling.

    Intervals describe the observed score series under this resampling scheme.
    They do not correct historical hypothesis selection or prove coverage.
    """
    if set(series) != set(SERIES):
        raise ValueError("unexpected score family")
    n = len(series[SERIES[0]])
    if (type(block_length) is not int or not 1 <= block_length <= n
            or type(replicates) is not int or not 100 <= replicates <= 20000
            or type(seed) is not int
            or any(len(v) != n or any(not isfinite(x) for x in v)
                   for v in series.values())):
        raise ValueError("invalid resampling inputs")
    blocks, remainder = divmod(n, block_length)
    sums = [_circular_sums(series[key], block_length) for key in SERIES]
    tails = ([_circular_sums(series[key], remainder) for key in SERIES]
             if remainder else None)
    samples = [[] for _ in SERIES]
    rng = Random(seed)
    for _ in range(replicates):
        starts = [rng.randrange(n) for _ in range(blocks)]
        tail_start = rng.randrange(n) if remainder else 0
        for i, vector in enumerate(sums):
            total = fsum(vector[start] for start in starts)
            if tails is not None:
                total += tails[i][tail_start]
            samples[i].append(total/n)
    output = {}
    for i, key in enumerate(SERIES):
        values = sorted(samples[i])
        low = _quantile(values, NOMINAL_ALPHA / 2)
        high = _quantile(values, 1 - NOMINAL_ALPHA / 2)
        adjusted = NOMINAL_ALPHA / (2 * COMPARISONS)
        wider_low = _quantile(values, adjusted)
        wider_high = _quantile(values, 1-adjusted)
        output[key] = {
            "observed_mean_log_edge": fsum(series[key])/n,
            "nominal_95_percent_resampling_range": [low, high],
            "nominal_bonferroni_percentile_range": [wider_low, wider_high],
            "adjusted_lower_above_zero_descriptive": wider_low > 0,
            "adjusted_upper_below_zero_descriptive": wider_high < 0,
        }
    return output


def evaluate(grades: list[dict], *, split_round: int = SPLIT_ROUND,
             replicates: int = REPLICATES, seed: int = SEED) -> dict:
    if (not grades or type(split_round) is not int or type(seed) is not int
            or type(replicates) is not int or not 100 <= replicates <= 20000):
        raise ValueError("invalid historical evaluation settings")
    previous_date = ""
    for index, row in enumerate(grades, 2):
        if (type(row.get("round")) is not int or row["round"] != index
                or row.get("data_cutoff_round") != index-1
                or not isinstance(row.get("draw_date"), str)
                or row["draw_date"] <= previous_date):
            raise ValueError("invalid historical chronology or cutoff")
        previous_date = row["draw_date"]
        for key in SERIES:
            value = row.get(key)
            if type(value) not in (int, float) or not isfinite(value):
                raise ValueError("missing or invalid historical score")
    cohorts = {
        "all": grades,
        "development": [r for r in grades if r["round"] <= split_round],
        "late_historical": [r for r in grades if r["round"] > split_round],
    }
    if any(len(rows) < max(BLOCK_LENGTHS) for rows in cohorts.values()):
        raise ValueError("insufficient history for both block lengths in every cohort")
    results = {}
    for name, rows in cohorts.items():
        scores = {key: [r[key] for r in rows] for key in SERIES}
        results[name] = {
            "first_round": rows[0]["round"],
            "last_round": rows[-1]["round"],
            "evaluated_draws": len(rows),
            "block_results": {str(length): resample(scores, block_length=length,
                             replicates=replicates, seed=seed)
                              for length in BLOCK_LENGTHS},
        }
    return {
        "split_round": split_round,
        "series": list(SERIES),
        "block_lengths": list(BLOCK_LENGTHS),
        "replicates_per_cohort_and_block_length": replicates,
        "seed": seed,
        "nominal_alpha": NOMINAL_ALPHA,
        "within_audit_comparison_count": COMPARISONS,
        "nominal_percentile_adjustment": "bonferroni_within_this_audit_only",
        "cohorts": results,
        "historical_hypothesis_selection_corrected": False,
        "historical_cohorts_independent": False,
        "confidence_coverage_guaranteed": False,
        "model_selection_performed": False,
    }


def audit(root: Path, *, replicates: int = REPLICATES, seed: int = SEED) -> dict:
    history, meta = load_archive(root)
    if not history or meta.get("officially_verified") is not False:
        raise ValueError("validated secondary archive required")
    _, grades = replay(history)
    return {
        "version": VERSION,
        "archive_git_blob_sha1": meta["git_blob_sha1"],
        "last_round": history[-1]["round"],
        "last_draw_date": history[-1]["draw_date"],
        **evaluate(grades, replicates=replicates, seed=seed),
        "prospective_skill_confirmed": False,
        "positive_expected_value_confirmed": False,
        "production_promotion_authorized": False,
        "actual_purchase": False,
        "purchase_decision": "SKIP",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--replicates", type=int, default=REPLICATES)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    try:
        report = audit(args.root, replicates=args.replicates, seed=args.seed)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
