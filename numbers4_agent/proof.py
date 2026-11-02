"""Chronological, prequential Numbers4 diagnostic; no prospective skill claims."""
from __future__ import annotations
from collections import Counter
from hashlib import sha256
from math import log, prod
from pathlib import Path
import json
import random

from .models import ranked_candidates
from .rules import four_digits
from .sources import corroborated_draws, iso_date
from .store import canonical, file_hash

PROTOCOL = "numbers4-exploratory-prequential-v1"
SEED = 20261102


def _valid_rows(rows: list[dict]) -> list[dict]:
    seen: set[int] = set()
    ordered = sorted(rows, key=lambda x: x["round"])
    prev_date = None
    for row in ordered:
        rnd = row["round"]
        if type(rnd) is not int or rnd <= 0 or rnd in seen:
            raise ValueError("invalid or duplicate historical draw round")
        seen.add(rnd)
        date = iso_date(row["draw_date"])
        four_digits(row["winning_number"])
        if prev_date is not None and not date > prev_date:
            raise ValueError("historical result dates must increase with round")
        prev_date = date
    return ordered


def _positional_probabilities(previous: list[dict]) -> list[list[float]]:
    training = previous[-250:]
    n = len(training)
    # The same public research model uses 5 pseudocounts / digit / position.
    return [[(Counter(r["winning_number"][pos] for r in training)[str(d)] + 5) / (n + 50)
             for d in range(10)] for pos in range(4)]


def _bootstrap_ci(edges: list[float], repetitions: int = 900, block: int = 10) -> list[float]:
    rng = random.Random(SEED)
    n = len(edges)
    if n < 2:
        return [None, None]
    draws = []
    for _ in range(repetitions):
        resampled = []
        while len(resampled) < n:
            start = rng.randrange(n)
            resampled.extend(edges[(start+j) % n] for j in range(min(block, n)))
        draws.append(sum(resampled[:n]) / n)
    draws.sort()
    return [round(draws[int(.025*(repetitions-1))], 9), round(draws[int(.975*(repetitions-1))], 9)]


def prequential(rows: list[dict], *, min_history: int = 60, scope: str = "unverified_historical_exploratory") -> dict:
    if min_history < 30 or not isinstance(min_history, int):
        raise ValueError("warmup requires at least 30 past results")
    history = _valid_rows(rows)
    if len(history) <= min_history:
        return {"version": PROTOCOL, "status": "insufficient_history", "scope": scope,
                "observed_rounds": len(history), "evaluated_draws": 0,
                "prediction_skill_confirmed": False, "production_promotion_allowed": False}
    edges, brier_edges = [], []
    top5_wins, reference_wins = 0, 0
    for index in range(min_history, len(history)):
        target = history[index]
        previous = history[:index]
        assert previous[-1]["round"] < target["round"]
        q = _positional_probabilities(previous)
        digits = target["winning_number"]
        likelihood = prod(q[pos][int(d)] for pos,d in enumerate(digits))
        edges.append(log(likelihood / 0.0001))
        model_squared = prod(sum(p*p for p in line) for line in q)
        brier_edges.append((1-0.0001) - (model_squared-2*likelihood+1))
        guess = ranked_candidates(previous, target["round"], method="positional")
        ref = ranked_candidates(previous, target["round"], method="uniform")
        top5_wins += digits in guess["numbers"]
        reference_wins += digits in ref["numbers"]
    n = len(edges)
    avg = sum(edges)/n
    return {
        "version": PROTOCOL, "status": "historical_exploratory_only", "scope": scope,
        "observed_rounds": len(history), "evaluated_draws": n,
        "warmup_draws": min_history, "train_window_max_draws": 250,
        "first_evaluated_round": history[min_history]["round"],
        "last_evaluated_round": history[-1]["round"],
        "last_evaluated_date": history[-1]["draw_date"],
        "model_version": "positional-dirichlet-research-v1",
        "baseline": "exact_10k_uniform_straight_distribution",
        "top5_model_hits": top5_wins,
        "top5_reference_hits": reference_wins,
        "uniform_expected_top5_hit_draws": n*5/10_000,
        "mean_log_likelihood_edge_vs_uniform": round(avg, 9),
        "mean_brier_improvement_vs_uniform": round(sum(brier_edges)/n, 12),
        "descriptive_moving_block_bootstrap_95pct": _bootstrap_ci(edges),
        "bootstrap_block_draws": 10, "bootstrap_replicates": 900, "bootstrap_seed": SEED,
        "protocol_version_frozen_before_this_execution": False,
        "truly_prospective_verified_draws": 0,
        "prediction_skill_confirmed": False,
        "production_promotion_allowed": False,
        "actual_purchase_profit_yen": None,
        "interpretation": "Retrospective analysis only; historic feed provenance and model selection do not establish prospective predictive advantage",
    }


def run(root: Path) -> dict:
    file = root / "research" / "historical_unverified.json"
    if file.is_file():
        cache = json.loads(file.read_text(encoding="utf-8"))
        if cache.get("version") != "numbers4-research-source-v1" or cache.get("verified_official") is not False:
            raise ValueError("research-only historical cache provenance invalid")
        research = prequential(cache["rows"], scope="single_publisher_not_officially_verified")
        research["source_sha256"] = file_hash(file)
        research["source_publisher"] = cache["publisher"]
    else:
        research = prequential([], scope="no_historical_source")
    verified = corroborated_draws(root)
    prospective = prequential(verified, scope="historically_matched_two_publishers_not_preregistered")
    prospective["data_scope"] = "already_observed_only_no_prospective_claim"
    prospective["prediction_skill_confirmed"] = False
    return {"research_unverified_history": research,
            "verified_history_exploratory": prospective,
            "prospective_skill_confirmed": False,
            "production_changed": False,
            "existing_issued_predictions_changed": False}


def save_report(root: Path, output: Path) -> dict:
    payload = run(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return payload
