"""Strictly past-only, research-only STRAIGHT challenger evaluation.

This is an exploratory historical experiment, NOT a prospective registration
or evidence that a fair lottery can be predicted. No published prediction,
verified draw ledger, payout, or production model is ever changed here.
"""
from __future__ import annotations

from collections import Counter, deque
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite, sqrt
from pathlib import Path

from .historical_archive import load_archive
from .online_learning import best_five, grade_prob, uniform_numbers
from .rules import four_digits
from .statistics import binomial_right_tail

JST = timezone(timedelta(hours=9))
VERSION = "numbers4-straight-retrospective-challenger-v1"
SPECS = (
    ("positional_60_alpha10", 60, 10),
    ("positional_250_alpha20", 250, 20),
    ("positional_1000_alpha20", 1000, 20),
)
GUARD_LOOKBACK = 250
GUARD_Z = 2.5
BASELINE = "uniform"
GATED = "past_only_gated"
PROBABILITY = 5 / 10000


class RollingDigits:
    """Windowed sufficient statistics: O(4) updates instead of recounting."""
    def __init__(self, length: int, alpha: int):
        if type(length) is not int or length <= 0 or type(alpha) is not int or alpha <= 0:
            raise ValueError("invalid rolling model specification")
        self.length = length
        self.alpha = alpha
        self.window: deque[str] = deque()
        self.counts = [[0] * 10 for _ in range(4)]

    def append(self, number: str) -> None:
        value = four_digits(number)
        if len(self.window) == self.length:
            old = self.window.popleft()
            for pos, digit in enumerate(old):
                self.counts[pos][int(digit)] -= 1
        self.window.append(value)
        for pos, digit in enumerate(value):
            self.counts[pos][int(digit)] += 1

    def probabilities(self) -> list[list[float]]:
        denominator = len(self.window) + 10 * self.alpha
        return [[(count + self.alpha) / denominator for count in pos]
                for pos in self.counts]


def guard_choice(previous_edges: dict[str, deque[float]]) -> str:
    """A deliberately conservative, *heuristic* past-only selection rule.

    Repeated rolling CI checks are NOT a sequential hypothesis test and do not
    establish statistical significance. They only control the research model.
    """
    eligible: list[tuple[float, str]] = []
    for name, scores in previous_edges.items():
        if len(scores) < GUARD_LOOKBACK:
            continue
        mean = sum(scores) / len(scores)
        variance = sum((v - mean) ** 2 for v in scores) / (len(scores) - 1)
        lower = mean - GUARD_Z * sqrt(variance / len(scores))
        if lower > 0:
            eligible.append((lower, name))
    return max(eligible)[1] if eligible else BASELINE


def _validate_rows(rows: list[dict], split_round: int) -> None:
    if len(rows) < 3 or type(split_round) is not int or not 2 <= split_round < len(rows):
        raise ValueError("chronological development/holdout split is invalid")
    previous_date = None
    for i, row in enumerate(rows, 1):
        if type(row.get("round")) is not int or row["round"] != i:
            raise ValueError("draws must be complete and sequential from round 1")
        if not isinstance(row.get("draw_date"), str):
            raise ValueError("draw date must be ISO formatted")
        draw_date = date.fromisoformat(row["draw_date"])
        if previous_date is not None and draw_date <= previous_date:
            raise ValueError("draw dates must increase strictly")
        four_digits(row["winning_number"])
        previous_date = draw_date


def _paired_exact_p(only_a: int, only_b: int) -> float:
    """Exploratory exact McNemar conditional two-sided probability."""
    discordant = only_a + only_b
    if discordant == 0:
        return 1.0
    return min(1.0, 2 * binomial_right_tail(discordant,
                                            discordant - min(only_a, only_b), .5))


def _summary(events: list[dict], baseline_events: list[dict]) -> dict:
    n = len(events)
    if n != len(baseline_events) or n == 0:
        raise ValueError("misaligned or empty retrospective evaluation subset")
    hits = sum(e["hit"] for e in events)
    ref_hits = sum(e["hit"] for e in baseline_events)
    only_selected = sum(e["hit"] and not ref["hit"]
                        for e, ref in zip(events, baseline_events))
    only_reference = sum(ref["hit"] and not e["hit"]
                         for e, ref in zip(events, baseline_events))
    return {
        "evaluated_draws": n,
        "top5_straight_hits": hits,
        "top5_straight_hit_rate": round(hits / n, 9),
        "uniform_theoretical_expected_hits": round(n * PROBABILITY, 6),
        "mean_log_score_edge_vs_uniform": round(sum(e["log_edge"] for e in events) / n, 9),
        "mean_brier_improvement_vs_uniform": round(sum(e["brier_edge"] for e in events) / n, 12),
        "selected_only_hits_vs_fixed_uniform_reference": only_selected,
        "uniform_reference_only_hits_vs_selected": only_reference,
        "paired_exact_discordance_p_exploratory":
            round(_paired_exact_p(only_selected, only_reference), 9),
        "uniform_null_hit_tail_p_exploratory":
            round(binomial_right_tail(n, hits, PROBABILITY), 9),
        "selected_model_counts": dict(sorted(Counter(e["selected_model"]
                                                     for e in events).items())),
        "performance_advantage_confirmed": False,
    }


def evaluate(rows: list[dict], *, split_round: int = 5000) -> dict:
    """Reconstruct each draw from earlier digits; report all challengers.

    Model family and retrospective split were designed after the historical
    series became available. Thus the holdout is *chronological* but not
    an untouched, preregistered independent test.
    """
    _validate_rows(rows, split_round)
    experts = {name: RollingDigits(window, alpha) for name, window, alpha in SPECS}
    edge_memory = {name: deque(maxlen=GUARD_LOOKBACK) for name in experts}
    events = {name: [] for name in (BASELINE, *(name for name, _, _ in SPECS), GATED)}
    for index, row in enumerate(rows):
        actual = row["winning_number"]
        if index:
            round_no = row["round"]
            ref_numbers = uniform_numbers(round_no)
            previous_choice = guard_choice(edge_memory)
            expert_forecasts: dict[str, tuple[list[str], float, float]] = {}
            # Compute model predictions only from past windows. The observed
            # result is used for scoring AFTER the choice has been fixed.
            for name, expert in experts.items():
                q = expert.probabilities()
                numbers = best_five(q)
                log_edge, brier_edge = grade_prob(q, actual)
                expert_forecasts[name] = (numbers, log_edge, brier_edge)
            events[BASELINE].append({
                "hit": int(actual in ref_numbers), "log_edge": 0.0,
                "brier_edge": 0.0, "selected_model": BASELINE,
            })
            for name, (numbers, log_edge, brier_edge) in expert_forecasts.items():
                events[name].append({
                    "hit": int(actual in numbers), "log_edge": log_edge,
                    "brier_edge": brier_edge, "selected_model": name,
                })
            if previous_choice == BASELINE:
                candidate_numbers, log_edge, brier_edge = ref_numbers, 0.0, 0.0
            else:
                candidate_numbers, log_edge, brier_edge = expert_forecasts[previous_choice]
            events[GATED].append({
                "hit": int(actual in candidate_numbers), "log_edge": log_edge,
                "brier_edge": brier_edge, "selected_model": previous_choice,
            })
            for name, (_, edge, _) in expert_forecasts.items():
                if not isfinite(edge):
                    raise ValueError("invalid probabilistic research score")
                edge_memory[name].append(edge)
        # This round is only available AFTER all predictions and choices.
        for expert in experts.values():
            expert.append(actual)

    def section(low: int, high: int) -> dict:
        start = low - 2   # event[0] corresponds to draw 2
        stop = high - 1
        reference = events[BASELINE][start:stop]
        return {
            "first_round": low, "last_round": high,
            "models": {name: _summary(samples[start:stop], reference)
                       for name, samples in events.items()},
        }

    next_round = rows[-1]["round"] + 1
    next_choice = guard_choice(edge_memory)
    next_numbers = (uniform_numbers(next_round) if next_choice == BASELINE
                    else best_five(experts[next_choice].probabilities()))
    return {
        "version": VERSION,
        "status": "retrospective_prequential_exploratory_only",
        "study_design": "posthoc_model_family_not_preregistered",
        "split_type": "chronological_not_untouched_prospective_holdout",
        "source_scope": "secondary_public_archives_not_bank_primary_verified",
        "first_training_round": 1,
        "first_evaluated_round": 2,
        "last_evaluated_round": rows[-1]["round"],
        "development_end_round": split_round,
        "retrospective_holdout_start_round": split_round + 1,
        "model_specs": [{"name": name, "window": window, "dirichlet_alpha": alpha}
                        for name, window, alpha in SPECS],
        "gating": {"lookback_rounds": GUARD_LOOKBACK, "z_heuristic": GUARD_Z,
                   "repeated_testing_is_valid_inferential_proof": False},
        "development": section(2, split_round),
        "retrospective_holdout": section(split_round + 1, rows[-1]["round"]),
        "next_research_candidate": {
            "target_round": next_round, "data_cutoff_round": rows[-1]["round"],
            "model": next_choice, "numbers": next_numbers,
            "status": "research_only_not_issued_not_purchased", "draw_date": None,
        },
        "genuine_prospective_verified_draws": 0,
        "forecast_skill_confirmed": False,
        "automatic_production_promotion": False,
        "actual_purchase_profit_yen": None,
        "interpretation": (
            "Observed historical metrics are exploratory. Chance, multiple testing,"
            " and post-hoc protocol selection prevent a prospective skill claim."
        ),
    }


def write_report(root: Path, *, output: Path = Path("research/straight_challenger_report.json"),
                 split_round: int = 5000) -> dict:
    rows, meta = load_archive(root)
    if not rows or meta.get("officially_verified") is not False:
        raise ValueError("secondary research-only source with explicit provenance required")
    result = evaluate(rows, split_round=split_round)
    result["archive_git_blob_sha1"] = meta["git_blob_sha1"]
    result["generated_at_jst"] = datetime.now(JST).isoformat(timespec="seconds")
    result["archive_last_round"] = meta["last_round"]
    result["experimental_code_revision"] = VERSION
    location = output if output.is_absolute() else root / output
    location.parent.mkdir(parents=True, exist_ok=True)
    location.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                        encoding="utf-8")
    return result
