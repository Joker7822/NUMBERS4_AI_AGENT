"""Automatic verified-only learning and strictly gated prospective champion choice.

No scraped research text enters weights. No ticket is issued or purchased.
A shadow forecast can become scoreable ONLY with an independently checked
GitHub push-run publication witness dated before the draw. Unwitnessed
forecasts and all secondary-source history carry ZERO promotion authority.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
import json
from math import exp, isfinite, log, prod
from pathlib import Path

from .online_learning import best_five, positional_probs, uniform_numbers
from .rules import four_digits
from .sources import JST, automatic_verified_rows, reconcile
from .store import append, canonical, file_hash, load

VERSION = "numbers4-prospective-auto-learning-v1"
FORECAST_PATH = Path("data/shadow_forecasts.jsonl")
WITNESS_PATH = Path("data/shadow_publication_witnesses.jsonl")
CHAMPION_PATH = Path("data/production_champion.json")
STATUS_PATH = Path("research/prospective_auto_learning_status.json")
SPECS = {
    "positional_60_alpha10": (60, 10),
    "positional_250_alpha5": (250, 5),
    "positional_1000_alpha20": (1000, 20),
}
MODELS = ("uniform", *SPECS)
ALPHA_FAMILY = 0.01
MIN_PROSPECTIVE_DRAWS = 500
DEADLINE_CLOCK = time(18, 0)  # stricter than the Numbers4 18:30 purchase deadline
PROTOCOL_HASH = sha256(canonical({
    "version": VERSION, "models": SPECS,
    "family_alpha": ALPHA_FAMILY, "minimum_draws": MIN_PROSPECTIVE_DRAWS,
    "promotion_rule": "anytime_valid_uniform_eprocess_bonferroni_and_straight_hits",
})).hexdigest()


def _time(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return result.astimezone(JST)


def _verified(root: Path) -> list[dict]:
    rows = sorted(automatic_verified_rows(root), key=lambda r: r["round"])
    if len({r["round"] for r in rows}) != len(rows):
        raise ValueError("duplicate primary verified round")
    reconciled = reconcile(root)
    for row in rows:
        trusted = reconciled.get(row["round"])
        if (not trusted or trusted["status"] != "auto_verified_two_publishers"
                or trusted["winning_number"] != row["winning_number"]
                or trusted["draw_date"] != row["draw_date"]):
            raise ValueError("primary draw conflicts with other evidence")
    return rows


def _training_hash(rows: list[dict]) -> str:
    return sha256(canonical({
        "verified_training": [
            {"round": r["round"], "draw_date": r["draw_date"],
             "winning_number": r["winning_number"],
             "event_sha256": r["event_sha256"]}
            for r in rows
        ],
    })).hexdigest()


def _probability(q: list[list[float]], four: str) -> float:
    value = four_digits(four)
    if (len(q) != 4 or any(len(line) != 10 for line in q) or
            any(any(type(v) not in (float, int) or not isfinite(v) or v <= 0
                    for v in line) or abs(sum(line)-1) > 1e-10 for line in q)):
        raise ValueError("invalid preregistered categorical distribution")
    return prod(q[i][int(d)] for i, d in enumerate(value))


def _candidate_models(rows: list[dict], round_number: int) -> dict:
    if any(r["round"] >= round_number for r in rows):
        raise ValueError("look-ahead: training includes forecasted round")
    recent = [r["winning_number"] for r in rows]
    forecasts = {}
    for name, (window, alpha) in SPECS.items():
        q = positional_probs(recent[-window:], alpha)
        forecasts[name] = {
            "model": name, "window": window, "alpha": alpha,
            "training_rounds": min(len(recent), window),
            "q": q, "number": best_five(q)[0],
        }
    return forecasts


def read_champion(root: Path) -> dict:
    path = root / CHAMPION_PATH
    if not path.is_file():
        return {
            "version": VERSION, "champion": "uniform", "promotion_round": None,
            "status": "default_uniform_no_prospective_evidence",
            "protocol_sha256": PROTOCOL_HASH,
        }
    state = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(state, dict) or state.get("version") != VERSION or
            state.get("protocol_sha256") != PROTOCOL_HASH or
            state.get("champion") not in MODELS or
            not isinstance(state.get("assessment_sha256"), str) or
        len(state["assessment_sha256"]) != 64 or
        any(c not in "0123456789abcdef" for c in state["assessment_sha256"])):
        raise ValueError("invalid or mismatched champion model state")
    return state


def freeze_shadow(root: Path, *, target_round: int, draw_date: str,
                  now: datetime | None = None) -> dict:
    """Train from earlier BANK-verified rows and preregister all three models.

    Only one target/day; a historical restart is NOT permitted. Writing this
    ledger is not sufficient publication proof: GitHub must externally witness
    that the committed row existed before the deadline.
    """
    stamp = (now or datetime.now(JST)).astimezone(JST)
    if type(target_round) is not int or target_round < 2:
        raise ValueError("invalid future target round")
    announced = date.fromisoformat(draw_date)
    if (announced.isoformat() != draw_date or announced != stamp.date()
            or announced.weekday() >= 5 or stamp.time() >= DEADLINE_CLOCK):
        raise ValueError("forecasts require draw-day weekday before 18:00 JST")
    verified = _verified(root)
    if not verified or verified[-1]["round"] != target_round - 1:
        raise ValueError("one immediately preceding bank-verified draw required")
    if date.fromisoformat(verified[-1]["draw_date"]) >= announced:
        raise ValueError("target draw date must be after last verified draw")
    forecasts = load(root / FORECAST_PATH)
    if forecasts:
        last = forecasts[-1]
        if target_round == last["round"]:
            if last["draw_date"] != draw_date:
                raise ValueError("duplicate forecast round has a conflicting date")
            return {"status": "already_frozen", "round": target_round,
                    "forecast_sha256": last["event_sha256"]}
        if target_round != last["round"] + 1:
            raise ValueError("shadow forecast sequence has a missing round")
    champion = read_champion(root)["champion"]
    if champion != "uniform":
        review = assess(root)
        if review["integrity_blocker"] or review["eligible_champion"] != champion:
            raise ValueError("promoted champion lacks current verified prospective evidence")
    spec_models = _candidate_models(verified, target_round)
    reference = uniform_numbers(target_round)[0]
    record = append(root / FORECAST_PATH, {
        "version": VERSION, "protocol_sha256": PROTOCOL_HASH,
        "round": target_round, "draw_date": draw_date,
        "issued_at_jst": stamp.isoformat(timespec="seconds"),
        "freeze_deadline_jst": datetime.combine(announced, DEADLINE_CLOCK,
                                                 JST).isoformat(timespec="seconds"),
        "training_verified_rounds": len(verified),
        "training_last_round": verified[-1]["round"],
        "training_sha256": _training_hash(verified),
        "source_status": "bank_primary_rakuten_publication_match",
        "models": spec_models, "baseline_number": reference,
        "champion_at_issue": champion,
        "champion_number": reference if champion == "uniform"
                           else spec_models[champion]["number"],
        "publication_proof": "pending_independent_github_push_run_witness",
        "actual_purchase": False, "issued_forecasts_ledger_unchanged": True,
        "forecast_skill_confirmed": False,
    })
    return {
        "status": "shadow_frozen_requires_github_publication_witness",
        "round": target_round, "draw_date": draw_date,
        "forecast_sha256": record["event_sha256"],
        "bank_training_rounds": len(verified),
        "production_champion": champion,
        "issued_forecasts_ledger_unchanged": True,
    }



def recommend_champion(root: Path, target_round: int) -> dict:
    """Use the automatically selected, reproducible champion for advice only.

    Fail closed when the preceding primary draw is missing. All suggested
    numbers remain research advice; never issue or purchase automatically.
    """
    if type(target_round) is not int or target_round < 2:
        raise ValueError("invalid target round")
    verified = _verified(root)
    if not verified or verified[-1]["round"] != target_round - 1:
        raise ValueError("latest immediately preceding bank-verified round required")
    champion = read_champion(root)["champion"]
    if champion != "uniform":
        review = assess(root)
        if review["integrity_blocker"] or review["eligible_champion"] != champion:
            raise ValueError("active research champion lacks current verified evidence")
    forecasts = _candidate_models(verified, target_round)
    number = (uniform_numbers(target_round)[0] if champion == "uniform"
              else forecasts[champion]["number"])
    return {
        "target_round": target_round, "numbers": [number],
        "mode": "straight", "model_version": VERSION,
        "selected_champion": champion,
        "training_verified_rounds": len(verified),
        "data_cutoff_round": verified[-1]["round"],
        "source_status": "bank_primary_rakuten_publication_match",
        "confidence": "not_established",
        "scope": "research_candidate_only_not_issued",
        "purchase_authorized": False,
        "actual_purchase": False,
    }

def _validated_witnesses(root: Path, forecasts: list[dict]) -> dict[int, dict]:
    witnesses = load(root / WITNESS_PATH)
    forecast_by_round = {r["round"]: r for r in forecasts}
    if len(forecast_by_round) != len(forecasts):
        raise ValueError("duplicate shadow forecasts")
    records = {}
    for row in witnesses:
        rnd = row.get("round")
        if type(rnd) is not int or rnd in records or rnd not in forecast_by_round:
            raise ValueError("orphan, duplicated or invalid publication witness")
        issued = forecast_by_round[rnd]
        when = _time(row["github_run_created_at"])
        if (row.get("version") != VERSION or
                row.get("forecast_event_sha256") != issued["event_sha256"] or
                row.get("github_event") not in {"push", "workflow_dispatch"} or
                row.get("github_repo") != "Joker7822/NUMBERS4_AI_AGENT" or
                row.get("github_workflow") != "Numbers4 CI" or
                not isinstance(row.get("github_run_id"), int) or
                row["github_run_id"] <= 0 or
                not isinstance(row.get("github_head_sha"), str) or
                len(row["github_head_sha"]) != 40 or
                any(c not in "0123456789abcdef" for c in row["github_head_sha"]) or
                row.get("github_server_verified") is not True or
                not _time(issued["issued_at_jst"]) <= when <
                _time(issued["freeze_deadline_jst"])):
            raise ValueError("publication lacks pre-draw GitHub server witness")
        records[rnd] = row
    return records


def assess(root: Path) -> dict:
    """Read fresh verified outcomes and frozen, externally witnessed candidates.

    Missing receipts, incomplete rounds and any mismatch block ALL promotion.
    The threshold controls repeated looks only under an independent uniform
    null and correctly predictable, unaltered forecast distributions.
    """
    rows = _verified(root)
    shadow = load(root / FORECAST_PATH)
    witnesses = _validated_witnesses(root, shadow)
    scored = []
    gap = None
    if shadow:
        expected_round = shadow[0]["round"]
        for forecast in shadow:
            if forecast.get("round") != expected_round:
                gap = "shadow_round_gap"
                break
            expected_round += 1
            if (forecast.get("version") != VERSION or
                    forecast.get("protocol_sha256") != PROTOCOL_HASH or
                    forecast.get("source_status") != "bank_primary_rakuten_publication_match" or
                    forecast.get("actual_purchase") is not False):
                gap = "shadow_protocol_mismatch"
                break
            draw = next((r for r in rows if r["round"] == forecast["round"]), None)
            if draw is None:
                if any(r["round"] > forecast["round"] for r in rows):
                    gap = "verified_outcome_gap"
                break
            if forecast["round"] not in witnesses:
                gap = "missing_independent_publication_witness"
                break
            if (draw["draw_date"] != forecast["draw_date"] or
                    _time(draw["verified_at_jst"]) <=
                    _time(forecast["issued_at_jst"])):
                gap = "draw_date_or_verification_conflict"
                break
            prior = [r for r in rows if r["round"] < forecast["round"]]
            if (not prior or prior[-1]["round"] != forecast["training_last_round"]
                    or _training_hash(prior) != forecast["training_sha256"]):
                gap = "historical_training_prefix_changed"
                break
            expected_models = _candidate_models(prior, forecast["round"])
            if forecast["models"] != expected_models:
                gap = "trained_forecast_changed_after_publication"
                break
            if forecast.get("baseline_number") != uniform_numbers(forecast["round"])[0]:
                gap = "baseline_changed_after_publication"
                break
            number = four_digits(draw["winning_number"])
            scored.append({
                "round": forecast["round"],
                "baseline_hit": int(number == forecast["baseline_number"]),
                "model_hits": {name: int(number == model["number"])
                               for name, model in expected_models.items()},
                "log_e": {name: log(_probability(model["q"], number) * 10000)
                          for name, model in expected_models.items()},
            })
        if rows and rows[-1]["round"] > shadow[-1]["round"]:
            gap = gap or "missing_future_shadow_forecast"
    evidence = {}
    for name in SPECS:
        log_e = sum(row["log_e"][name] for row in scored)
        selected_hits = sum(row["model_hits"][name] for row in scored)
        base_hits = sum(row["baseline_hit"] for row in scored)
        required = log(len(SPECS) / ALPHA_FAMILY)
        qualifies = (gap is None and len(scored) >= MIN_PROSPECTIVE_DRAWS
                     and log_e >= required and selected_hits > base_hits)
        evidence[name] = {
            "verified_prospective_draws": len(scored),
            "candidate_straight_hits": selected_hits,
            "uniform_reference_straight_hits": base_hits,
            "log_e_against_independent_uniform": round(log_e, 9),
            "log_threshold": round(required, 9),
            "anytime_valid_uniform_null_alpha_family": ALPHA_FAMILY,
            "screen_passed": qualifies,
            "production_eligible": qualifies,
        }
    approved = [name for name, result in evidence.items()
                if result["production_eligible"]]
    selection = max(approved, key=lambda name: (evidence[name]["log_e_against_independent_uniform"], name)) if approved else "uniform"
    status = (
        "no_shadow_forecasts" if not shadow else
        "evidence_integrity_blocked" if gap else
        "insufficient_true_prospective_draws" if len(scored) < MIN_PROSPECTIVE_DRAWS else
        "eligible_under_preregistered_uniform_null" if approved else
        "no_confirmed_advantage"
    )
    return {
        "version": VERSION, "protocol_sha256": PROTOCOL_HASH,
        "status": status, "integrity_blocker": gap,
        "verified_official_draws_available": len(rows),
        "shadow_forecasts_recorded": len(shadow),
        "independently_witnessed_forecasts": len(witnesses),
        "eligible_prospective_draws": len(scored),
        "required_prospective_draws": MIN_PROSPECTIVE_DRAWS,
        "model_assessments": evidence,
        "eligible_champion": selection,
        "current_champion": read_champion(root)["champion"],
        "selection_criterion": "bonferroni_anytime_e_process_and_higher_straight_hits",
        "test_null": "independent_fair_uniform_10000_outcomes_conditional_on_past",
        "source": "bank_primary_plus_rakuten_matching_provenance_only",
        "secondary_historical_training_authorized": False,
        "unreviewed_external_source_code_executed": False,
        "forecasts_retroactively_modified": False,
        "purchases_automated": False,
        "evidence_is_absolute_prediction_proof": False,
    }


def apply_policy(root: Path, *, now: datetime | None = None) -> dict:
    """Auto-promote/rollback champion only with complete witnessed evidence.

    No edits to lottery forecasts, archived predictions, verified outcomes, or
    forecast model source code. Writes only the pointer and a research status.
    """
    result = assess(root)
    old = read_champion(root)["champion"]
    new = result["eligible_champion"]
    # During evidence outage, HOLD any existing champion, never replace it.
    if result["integrity_blocker"]:
        new = old
    if result["status"] == "no_shadow_forecasts":
        new = old
    changed = new != old
    stamp = (now or datetime.now(JST)).astimezone(JST).isoformat(timespec="seconds")
    result["previous_champion"] = old
    result["production_champion"] = new
    result["champion_changed"] = changed
    result["action"] = ("promote" if changed and new != "uniform" else
                        "rollback_to_uniform" if changed else "keep")
    result["evaluated_at_jst"] = stamp
    result["automatic_promotion_feature_implemented"] = True
    result["automatic_promotion_executed"] = changed and new != "uniform"
    result["actual_purchase"] = False
    result["forecast_skill_confirmed"] = False  # not an absolute claim
    result_bytes = canonical(result)
    result["assessment_sha256"] = sha256(result_bytes).hexdigest()
    location = root / STATUS_PATH
    location.parent.mkdir(parents=True, exist_ok=True)
    location.write_text(json.dumps(result, ensure_ascii=False, indent=2,
                                    allow_nan=False) + "\n", encoding="utf-8")
    if changed:
        state = {
            "version": VERSION, "protocol_sha256": PROTOCOL_HASH,
            "champion": new, "promotion_round": (
                max((r["round"] for r in load(root / FORECAST_PATH)), default=None)),
            "status": "automatic_evidence_gated_champion",
            "previous_champion": old, "updated_at_jst": stamp,
            "assessment_sha256": result["assessment_sha256"],
            "purchases_automated": False,
        }
        location = root / CHAMPION_PATH
        location.parent.mkdir(parents=True, exist_ok=True)
        location.write_text(json.dumps(state, ensure_ascii=False, indent=2,
                                       allow_nan=False) + "\n", encoding="utf-8")
    return result
