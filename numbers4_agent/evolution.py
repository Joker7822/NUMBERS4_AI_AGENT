"""Recursive ONLINE research evolution, restricted to reviewed Python algorithms.

Each generation: scientific/web-search metadata -> allowlisted method mapping ->
new parameterized hypotheses -> FULL round-2 prequential reconstruction ->
development feedback -> next search strategy. Untrusted external code and
secondary historical outcomes can NEVER enter the prospective champion gate.

IMPORTANT: even a strictly past-only *weight update* here is not a real
pre-issued forecast: hypothesis families have been designed on the historical
archive. Repeated tests of the late cohort are post-hoc, not genuine OOS proof.
"""
from __future__ import annotations

import csv
from collections import Counter, deque
from datetime import date, datetime
from hashlib import sha256
import json
from math import isfinite, sqrt
from pathlib import Path

from .historical_archive import load_archive
from .online_learning import (JST, grade_prob, uniform_numbers, write_replay)
from .research_discovery import DEFAULT_TOPICS
from .research_acquisition import collect as collect_progressively, persist as persist_progressive_sources
from .rules import four_digits
from .store import append as append_chain, canonical, load as read_chain
from .straight_challenger import RollingDigits

VERSION = "numbers4-recursive-research-evolution-v1"
REPORT = Path("research/evolution_report.json")
ROUND_CSV = Path("research/evolution_round_predictions.csv")
JOURNAL = Path("research/evolution_journal.jsonl")
SPLIT_ROUND = 5000
MAX_MODELS = 8
MAX_GENERATIONS = 1000
GUARD_LOOKBACK = 250
GUARD_Z = 2.5
ROUND_FIELDS = (
    "round", "draw_date", "actual", "data_cutoff_round",
    "research_selected_model", "selected_number", "selected_hit",
    "uniform_number", "uniform_hit", "selected_log_edge",
    "selected_brier_edge", "source_status",
)
FALLBACK_SPECS = (
    {"family": "rolling", "window": 60, "alpha": 10},
    {"family": "rolling", "window": 250, "alpha": 5},
    {"family": "ema", "decay": 0.99, "alpha": 10},
)
SAFE_FAMILIES = ("rolling", "ema", "markov")


def _validate_spec(spec: dict) -> dict:
    """Only predefined implementation families and bounded hyperparameters."""
    if not isinstance(spec, dict) or spec.get("family") not in SAFE_FAMILIES:
        raise ValueError("unsafe research method family")
    family = spec["family"]
    if family in ("rolling", "markov"):
        if (set(spec) != {"family", "window", "alpha"}
                or type(spec["window"]) is not int or spec["window"] not in
                (30, 60, 120, 250, 500, 1000)
                or type(spec["alpha"]) is not int or spec["alpha"] not in
                (2, 5, 10, 20, 50)):
            raise ValueError("unsupported hyperparameter proposal")
    else:
        if (set(spec) != {"family", "decay", "alpha"}
                or type(spec["decay"]) is not float
                or spec["decay"] not in (0.98, 0.99, 0.995, 0.999)
                or type(spec["alpha"]) is not int or spec["alpha"] not in
                (2, 5, 10, 20, 50)):
            raise ValueError("unsupported EMA proposal")
    return dict(spec)


def _spec_id(spec: dict) -> str:
    spec = _validate_spec(spec)
    label = spec["family"] + "_" + (
        str(spec["window"]) if spec["family"] != "ema" else
        str(spec["decay"]).replace(".", "p")
    ) + "_alpha" + str(spec["alpha"])
    return label


class _EmaDigits:
    """O(4*10) exponentially decayed digit-frequency learner."""
    def __init__(self, decay: float, alpha: int):
        self.decay, self.alpha = decay, alpha
        self.counts = [[0.0] * 10 for _ in range(4)]
        self.weight = 0.0

    def append(self, number: str) -> None:
        n = four_digits(number)
        self.weight = self.weight * self.decay + 1
        for position, digit in enumerate(n):
            for k in range(10):
                self.counts[position][k] *= self.decay
            self.counts[position][int(digit)] += 1.0

    def probabilities(self) -> list[list[float]]:
        denom = self.weight + 10 * self.alpha
        return [[(c + self.alpha) / denom for c in line]
                for line in self.counts]


class _MarkovDigits:
    """One-step positional transition model based ONLY on earlier outcomes."""
    def __init__(self, window: int, alpha: int):
        self.window, self.alpha = window, alpha
        self.counts = [[[0] * 10 for _ in range(10)] for _ in range(4)]
        self.trans: deque[tuple[str, str]] = deque()
        self.previous: str | None = None

    def append(self, number: str) -> None:
        value = four_digits(number)
        if self.previous is not None:
            if len(self.trans) == self.window:
                old, nxt = self.trans.popleft()
                for position in range(4):
                    self.counts[position][int(old[position])][int(nxt[position])] -= 1
            self.trans.append((self.previous, value))
            for position in range(4):
                self.counts[position][int(self.previous[position])][int(value[position])] += 1
        self.previous = value

    def probabilities(self) -> list[list[float]]:
        if self.previous is None:
            return [[0.1] * 10 for _ in range(4)]
        rows = []
        for position, previous_digit in enumerate(self.previous):
            counts = self.counts[position][int(previous_digit)]
            denom = sum(counts) + 10 * self.alpha
            rows.append([(c + self.alpha) / denom for c in counts])
        return rows


def _model(spec: dict):
    spec = _validate_spec(spec)
    if spec["family"] == "rolling":
        return RollingDigits(spec["window"], spec["alpha"])
    if spec["family"] == "ema":
        return _EmaDigits(spec["decay"], spec["alpha"])
    return _MarkovDigits(spec["window"], spec["alpha"])


def _top_number(q: list[list[float]]) -> str:
    # For an independent positional distribution the MAP four-digit number
    # is obtained by maximizing each digit marginal independently.
    if (len(q) != 4 or any(len(line) != 10 or
            any(not isfinite(x) or x <= 0 for x in line) or
            abs(sum(line) - 1) > 1e-8 for line in q)):
        raise ValueError("invalid learned categorical distribution")
    return "".join(str(max(range(10), key=lambda d: (line[d], -d)))
                   for line in q)


def _metadata_leads(discovery: dict) -> tuple[set[str], list[dict]]:
    """Map *metadata* to safe hypotheses; do not treat it as verified science."""
    hints: set[str] = set()
    links = []
    for record in discovery.get("candidates", []):
        if not isinstance(record, dict) or not isinstance(record.get("title"), str):
            continue
        text = " ".join([record["title"], record.get("description", "")]).lower()
        # Crossref abstracts are used only to produce bounded method-signal
        # flags; no full publisher abstracts or page instructions are retained.
        signals = record.get("method_signals", [])
        if not isinstance(signals, list):
            signals = []
        proposed = []
        if "markov" in signals or any(word in text for word in ("markov", "transition", "sequential dependence")):
            proposed.append("markov")
        if "temporal_decay" in signals or any(word in text for word in ("exponentially weight", "forgetting", "decay", "concept drift")):
            proposed.append("ema")
        if any(signal in signals for signal in ("bayesian_smoothing", "calibration")) or any(word in text for word in ("bayesian", "dirichlet", "rolling", "smoothing", "calibration")):
            proposed.append("rolling")
        if proposed:
            hints.update(proposed)
            links.append({
                "source_id": record.get("id", ""),
                "source_url": record.get("source_url", ""),
                "mapped_to_approved_implementations": proposed,
                "mapping_rule": "bounded_title_keyword_only_not_a_paper_reproduction",
                "full_paper_independently_reviewed": False,
                "claimed_predictive_ability_verified": False,
            })
    return hints, links


def _mutate(parent: dict, generation: int) -> dict:
    """Deterministic, bounded hyperparameter exploration of a past-cycle parent."""
    parent = _validate_spec(parent)
    alpha_options = (2, 5, 10, 20, 50)
    alpha_index = alpha_options.index(parent["alpha"])
    if parent["family"] == "ema":
        options = (0.98, 0.99, 0.995, 0.999)
        position = options.index(parent["decay"])
        return {"family": "ema",
                "decay": options[(position + 1) % len(options)],
                "alpha": parent["alpha"]}
    window_options = (30, 60, 120, 250, 500, 1000)
    position = window_options.index(parent["window"])
    if generation % 2:
        return {"family": parent["family"],
                "window": window_options[(position + 1) % len(window_options)],
                "alpha": parent["alpha"]}
    return {"family": parent["family"], "window": parent["window"],
            "alpha": alpha_options[(alpha_index + 1) % len(alpha_options)]}


def propose(discovery: dict, *, previous: dict | None = None,
            generation: int = 1) -> tuple[list[dict], list[dict]]:
    if type(generation) is not int or not 1 <= generation <= MAX_GENERATIONS:
        raise ValueError("invalid bounded evolution generation")
    hints, links = _metadata_leads(discovery)
    seed = [dict(x) for x in FALLBACK_SPECS]
    if "markov" in hints:
        seed.append({"family": "markov", "window": 250, "alpha": 20})
    if "rolling" in hints:
        seed.append({"family": "rolling", "window": 120, "alpha": 10})
    if "ema" in hints:
        seed.append({"family": "ema", "decay": 0.995, "alpha": 5})
    if previous:
        parent_name = previous.get("development_winner", {}).get("model")
        parent_spec = next(
            (spec for spec in previous.get("model_specs", [])
             if isinstance(spec, dict) and _spec_id(spec) == parent_name), None)
        if parent_spec is not None:
            seed.append(_mutate(parent_spec, generation))
        else:
            # No development model beat the uniform reference. Continue
            # controlled, bounded exploration rather than quietly reusing
            # the same losing parameter set in every generation.
            base = FALLBACK_SPECS[(generation - 2) % len(FALLBACK_SPECS)]
            seed.append(_mutate(base, generation))
        # Explore a different approved family after observing prior development
        # performance, but never transfer exploratory history to formal proof.
        if generation % 3 == 0:
            seed.append({"family": "markov", "window": 120, "alpha": 20})
    else:
        seed.append({"family": "rolling", "window": 1000, "alpha": 20})
    selected: dict[str, dict] = {}
    for item in seed:
        checked = _validate_spec(item)
        selected.setdefault(_spec_id(checked), checked)
    return list(selected.values())[:MAX_MODELS], links


def choose_past_only(recent_edges: dict[str, deque[float]]) -> str:
    """Non-inferential guard: select a candidate ONLY using earlier log scores."""
    eligible = []
    for name, window in recent_edges.items():
        if len(window) < GUARD_LOOKBACK:
            continue
        mean = sum(window) / len(window)
        var = sum((x - mean) ** 2 for x in window) / (len(window) - 1)
        lower = mean - GUARD_Z * sqrt(var / len(window))
        if lower > 0:
            eligible.append((lower, name))
    return max(eligible)[1] if eligible else "uniform"


def _stats(events: list[tuple[int, float, float]]) -> dict:
    if not events:
        raise ValueError("empty retrospective cohort")
    n = len(events)
    return {
        "draws": n, "straight_hits": sum(x[0] for x in events),
        "mean_log_score_edge_vs_uniform": round(sum(x[1] for x in events) / n, 9),
        "mean_brier_edge_vs_uniform": round(sum(x[2] for x in events) / n, 12),
        "expected_uniform_hits_per_one_ticket": round(n / 10000, 6),
        "confirmed_prospective_skill": False,
    }


def evaluate(rows: list[dict], specs: list[dict], *,
             split_round: int = SPLIT_ROUND) -> tuple[dict, list[dict]]:
    """Rerun EVERY target round starting with 2; forecast before updating.

    Hypothesis proposals may have been devised with hindsight. This strictly
    protects weight chronology but does NOT recreate historical issuance.
    """
    if (len(rows) < 4 or type(split_round) is not int
            or not 2 <= split_round < len(rows)):
        raise ValueError("need original round 1 and development/late cohorts")
    previous_date = None
    for index, row in enumerate(rows, 1):
        if type(row.get("round")) is not int or row["round"] != index:
            raise ValueError("draws must be sequential from original draw 1")
        day = date.fromisoformat(row["draw_date"])
        if previous_date is not None and day <= previous_date:
            raise ValueError("draw dates must increase strictly")
        four_digits(row["winning_number"])
        previous_date = day
    checked = [_validate_spec(x) for x in specs]
    ids = [_spec_id(x) for x in checked]
    if not ids or len(ids) > MAX_MODELS or len(set(ids)) != len(ids):
        raise ValueError("invalid or duplicate research candidate list")
    learners = {name: _model(spec) for name, spec in zip(ids, checked)}
    edges = {name: deque(maxlen=GUARD_LOOKBACK) for name in ids}
    events = {name: [] for name in ("uniform", *ids, "adaptive")}
    round_records = []
    for index, row in enumerate(rows):
        actual = row["winning_number"]
        if index:
            rnd = row["round"]
            selected = choose_past_only(edges)
            ref = uniform_numbers(rnd)[0]
            current = {}
            for name, model in learners.items():
                q = model.probabilities()
                candidate = _top_number(q)
                # This score is computed AFTER the selected model/number
                # is determined and is not used to choose this same round.
                score, brier = grade_prob(q, actual)
                current[name] = (candidate, score, brier)
            events["uniform"].append((int(ref == actual), 0.0, 0.0))
            for name, (candidate, score, brier) in current.items():
                events[name].append((int(candidate == actual), score, brier))
            current_selected = (ref, 0.0, 0.0) if selected == "uniform" else current[selected]
            number, score, brier = current_selected
            events["adaptive"].append((int(number == actual), score, brier))
            round_records.append({
                "round": rnd, "draw_date": row["draw_date"], "actual": actual,
                "data_cutoff_round": rnd - 1, "research_selected_model": selected,
                "selected_number": number, "selected_hit": int(number == actual),
                "uniform_number": ref, "uniform_hit": int(ref == actual),
                "selected_log_edge": round(score, 9),
                "selected_brier_edge": round(brier, 12),
                "source_status": "secondary_public_mirrors_agree_not_officially_verified",
            })
            for name, (_, prior_score, _) in current.items():
                edges[name].append(prior_score)
        for model in learners.values():
            model.append(actual)
    def section(first: int, last: int) -> dict:
        return {
            "first_round": first, "last_round": last,
            "model_metrics": {
                name: _stats(values[first - 2:last - 1])
                for name, values in events.items()
            },
        }
    dev = section(2, split_round)
    late = section(split_round + 1, rows[-1]["round"])
    # Development is reused each generation and is no longer an independent
    # test; this selection is heuristic and must not be labelled confidence.
    dev_candidates = [
        (entry["mean_log_score_edge_vs_uniform"], name)
        for name, entry in dev["model_metrics"].items()
        if name not in ("adaptive", "uniform")
    ]
    dev_best_score, dev_best_name = max(dev_candidates)
    winner = dev_best_name if dev_best_score > 0 else "uniform"
    next_round = rows[-1]["round"] + 1
    selected = choose_past_only(edges)
    if selected == "uniform":
        next_number = uniform_numbers(next_round)[0]
    else:
        next_number = _top_number(learners[selected].probabilities())
    return {
        "status": "recursive_research_exploration_not_prospective_evidence",
        "tickets_per_draw": 1,
        "first_training_round": 1,
        "first_evaluated_round": 2,
        "last_evaluated_round": rows[-1]["round"],
        "evaluated_draws": len(rows) - 1,
        "model_specs": checked,
        "model_ids": ids,
        "development": dev,
        "late_historical_reanalysis": late,
        "development_winner": {
            "model": winner, "mean_log_score_edge_vs_uniform":
                max(0.0, dev_best_score),
            "is_independent_holdout": False,
        },
        "next_research_candidate": {
            "target_round": next_round, "data_cutoff_round": rows[-1]["round"],
            "model": selected, "numbers": [next_number], "draw_date": None,
            "status": "research_only_not_issued_not_purchased",
        },
        "selection_guard": {"lookback": GUARD_LOOKBACK, "z_heuristic": GUARD_Z,
                            "not_a_valid_statistical_significance_test": True},
        "weights_fitted_only_from_prior_rounds": True,
        "model_family_devised_after_historical_outcomes": True,
        "repeated_development_and_late_cohort_reuse": True,
        "research_model_policy_auto_updated": True,
        "genuine_prospective_independently_verified_draws": 0,
        "performance_advantage_confirmed": False,
        "production_model_changed": False,
        "automatic_purchase": False,
        "interpretation": "Each generation restarts at round 2 for comparative research only. Repeated history reuse and posthoc hypothesis choice cannot prove predictive superiority.",
    }, round_records


def next_queries(previous: dict | None) -> list[str]:
    """Feed previous development learning back into the next search targets."""
    queries = list(DEFAULT_TOPICS)
    if previous:
        winner = previous.get("development_winner", {}).get("model", "")
        if winner.startswith("ema"):
            queries[1] = "exponential forgetting online probability calibration temporal drift"
        elif winner.startswith("markov"):
            queries[1] = "Markov transition digit sequence prediction statistical validity"
        elif winner.startswith("rolling"):
            queries[1] = "Dirichlet smoothing rolling window forecast cross validation"
        else:
            queries[1] = "lottery forecast model comparison data snooping prevention"
    return queries


def _read_previous(root: Path) -> tuple[list[dict], dict | None]:
    chain = read_chain(root / JOURNAL)
    if len(chain) >= MAX_GENERATIONS:
        raise ValueError("bounded research generation limit reached")
    file = root / REPORT
    if chain and not file.is_file():
        raise ValueError("missing evolution report for existing journal")
    previous = None
    if file.exists():
        previous = json.loads(file.read_text(encoding="utf-8"))
        if (not isinstance(previous, dict) or previous.get("version") != VERSION
                or previous.get("generation") != len(chain)):
            raise ValueError("research evolution snapshot inconsistent with journal")
        if chain and chain[-1]["report_sha256"] != sha256(file.read_bytes()).hexdigest():
            raise ValueError("evolution report hash diverges from append-only journal")
    if not chain and previous is not None:
        raise ValueError("journal missing for existing evolution report")
    return chain, previous



def public_status(root: Path, archive: dict) -> dict:
    """Read and verify research evolution artifacts for the public dashboard."""
    chain, previous = _read_previous(root)
    if not chain:
        return {
            "version": VERSION, "status": "not_yet_run", "generation": 0,
            "evaluated_draws": 0, "candidate_models": 0,
            "research_sources_found": 0, "web_search_enabled": False,
            "lifetime_unique_sources": None, "new_unique_sources": 0,
            "requests_attempted": 0,
            "next_model": None, "next_number": None, "generated_at_jst": None,
            "performance_advantage_confirmed": False,
            "model_auto_promotion_authorized": False,
            "actual_purchase": False,
        }
    if previous is None:
        raise ValueError("missing last evolution report")
    csv_file = root / ROUND_CSV
    if (not csv_file.is_file() or
            sha256(csv_file.read_bytes()).hexdigest() !=
            previous["research_round_csv_sha256"] or
            chain[-1]["round_csv_sha256"] != previous["research_round_csv_sha256"]):
        raise ValueError("evolution round-by-round replay checksum mismatch")
    latest = previous["next_research_candidate"]
    archive_fresh = (
        previous["archive_git_blob_sha1"] == archive.get("git_blob_sha1")
        and previous["archive_latest_round"] == archive.get("last_round")
    )
    return {
        "version": VERSION,
        "status": ("recursive_research_exploration_not_prospective_evidence"
                   if archive_fresh else "stale_history_reanalysis"),
        "generation": previous["generation"],
        "evaluated_draws": previous["evaluated_draws"] if archive_fresh else 0,
        "candidate_models": len(previous["model_specs"]),
        "research_sources_found": previous["research_discovery"]["candidate_count"],
        "lifetime_unique_sources": previous["research_discovery"].get("lifetime_unique_sources_after_commit"),
        "new_unique_sources": previous["research_discovery"].get("new_unique_sources", 0),
        "requests_attempted": previous["research_discovery"].get("requests_attempted_this_run", 0),
        "web_search_enabled": previous["research_discovery"].get(
            "web_search_enabled", False),
        "research_search_errors": len(previous["research_discovery"]["errors"]),
        "new_draws_since_previous_generation":
            previous["current_archive_new_rounds_since_previous_generation"],
        "metadata_based_method_leads": len(previous["retrieved_method_metadata_leads"]),
        "next_model": latest["model"] if archive_fresh else None,
        "next_number": latest["numbers"][0] if archive_fresh else None,
        "generated_at_jst": previous["generated_at_jst"],
        "performance_advantage_confirmed": False,
        "model_auto_promotion_authorized": False,
        "actual_purchase": False,
        "repeated_historical_cohorts_not_independent": True,
        "description": "All draws from round 2 are retrospectively reconstructed each generation; no actual pre-issued prediction or independent confirmation.",
    }


def cycle(root: Path, *, queries: list[str] | None = None,
          offline: bool = False, crossref_fetch=None, brave_fetch=None,
          brave_api_key: str | None = None, split_round: int = SPLIT_ROUND,
          now: datetime | None = None) -> dict:
    """Run one *entire* research generation, including original full replay.

    A failed external search is reported as unavailable, not made up. Current
    results do not imply future lottery profitability or model promotion.
    """
    now = (now or datetime.now(JST)).astimezone(JST)
    chain, previous = _read_previous(root)
    generation = len(chain) + 1
    rows, provenance = load_archive(root)
    if previous is not None and provenance.get("last_round", 0) < previous["archive_latest_round"]:
        raise ValueError("historical archive cannot be rewound across research generations")
    if not rows or provenance.get("officially_verified") is not False:
        raise ValueError("strict full secondary archive and provenance required")
    active_queries = queries or next_queries(previous)
    staged_sources = None
    if offline:
        discovered = {
            "queries": active_queries, "candidates": [], "candidate_count": 0,
            "providers_attempted": [], "web_search_enabled": False,
            "errors": [], "status": "explicitly_offline_no_sources_retrieved",
            "new_unique_sources": 0, "lifetime_unique_sources_after_commit": None,
            "requests_attempted_this_run": 0,
        }
    else:
        discovered, staged_sources = collect_progressively(
            root, active_queries, crossref_fetch=crossref_fetch,
            brave_fetch=brave_fetch, brave_api_key=brave_api_key, now=now)
        discovered["status"] = "online_discovery_attempted"
    specs, mapped = propose(discovered, previous=previous, generation=generation)
    assessed, grades = evaluate(rows, specs, split_round=split_round)
    if len(grades) != len(rows) - 1:
        raise ValueError("full historical reconstruction is incomplete")
    # The canonical one-ticket replay is ALSO recreated, never re-labelled as
    # model skill. Its payout and BOX accounting remain a distinct scenario.
    regular = write_replay(root)
    if (regular["evaluated_draws"] != assessed["evaluated_draws"] or
            regular["archive_git_blob_sha1"] != provenance["git_blob_sha1"]):
        raise ValueError("canonical replay and proposed research history disagree")
    target = root / ROUND_CSV
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROUND_FIELDS)
        writer.writeheader()
        writer.writerows(grades)
    report = {
        "version": VERSION, "generation": generation,
        "generated_at_jst": now.isoformat(timespec="seconds"),
        "archive_git_blob_sha1": provenance["git_blob_sha1"],
        "archive_latest_round": provenance["last_round"],
        "current_archive_new_rounds_since_previous_generation": (
            None if previous is None else
            provenance["last_round"] - previous["archive_latest_round"]),
        "research_discovery": discovered,
        "retrieved_method_metadata_leads": mapped,
        "research_sources_directly_changed_training_weights": False,
        "external_paper_code_executed": False,
        "research_proposed_specs_derived_from_safe_registry": True,
        "previous_generation_feedback_used_for_hypothesis_mutation": previous is not None,
        "previous_generation_search_queries_adapted": previous is not None,
        "past_only_research_replay_recomputed": True,
        "parallel_original_one_ticket_replay_recomputed": True,
        "original_replay_version": regular["version"],
        "original_replay_straight_hits": regular["selected_straight_hits"],
        "original_replay_uniform_hits": regular["uniform_reference_straight_hits"],
        "original_replay_sha256": sha256((root / "research/online_replay.json").read_bytes()).hexdigest(),
        "research_round_csv_sha256": sha256(target.read_bytes()).hexdigest(),
        "next_generation_queries": next_queries(assessed),
        **assessed,
        "research_generation_is_prospective_preregistration": False,
        "official_results_verified_by_this_cycle": False,
        "model_auto_promotion_authorized": False,
        "actual_purchase_profit_yen": None,
    }
    path = root / REPORT
    raw = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    path.write_text(raw, encoding="utf-8")
    if staged_sources is not None:
        persist_progressive_sources(root, staged_sources, discovered)
    append_chain(root / JOURNAL, {
        "version": VERSION, "generation": generation,
        "at_jst": report["generated_at_jst"],
        "archive_git_blob_sha1": provenance["git_blob_sha1"],
        "model_spec_sha256": sha256(canonical(specs)).hexdigest(),
        "report_sha256": sha256(raw.encode("utf-8")).hexdigest(),
        "round_csv_sha256": report["research_round_csv_sha256"],
        "development_winner": assessed["development_winner"]["model"],
        "source_candidates": discovered["candidate_count"],
        "new_unique_sources": discovered["new_unique_sources"],
        "lifetime_unique_sources_after_commit": discovered["lifetime_unique_sources_after_commit"],
        "searched_online": not offline,
        "not_prospective_evidence": True,
        "production_model_untouched": True,
    })
    return report
