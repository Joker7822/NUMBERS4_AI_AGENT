"""Discover potential forecasting methods, independently validate metadata,
and run the local *existing* historical STRAIGHT challenger evaluation.

This is a research workflow, NOT an official lottery-results fetch. Neither
bibliographic hits nor search snippets grant authority to train/promote a model.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import http.client
import json
import os
from pathlib import Path
import re
from urllib.parse import urlencode

from .historical_archive import load_archive
from .open_web import (
    _PinnedHTTPSConnection, public_addresses, fetch_public_page,
    validate_public_url,
)
from .straight_challenger import evaluate

JST = timezone(timedelta(hours=9))
VERSION = "numbers4-predictive-research-discovery-v1"
CROSSREF_HOST = "api.crossref.org"
BRAVE_HOST = "api.search.brave.com"
MAX_QUERIES = 8
RESULTS_PER_QUERY = 5
MAX_METADATA_BYTES = 1_000_000
DEFAULT_TOPICS = (
    "lottery draw statistical randomness tests prediction",
    "lottery machine learning forecasting out of sample validation",
    "proper scoring rules probabilistic forecast evaluation",
    "sequential multiple testing overfitting forecast models",
)
RESEARCH_CATEGORIES = (
    ("randomness", ("randomness", "random number", "lottery", "lotto", "drawing")),
    ("validation", ("backtest", "out-of-sample", "cross-validation", "walk-forward",
                    "multiple testing", "data snooping", "forecast evaluation")),
    ("probability", ("proper scoring", "brier", "logarithmic score",
                     "probabilistic forecast", "calibration")),
    ("machine_learning", ("machine learning", "neural", "deep learning",
                          "markov", "bayesian", "predictive model")),
)


def _queries(queries: list[str]) -> list[str]:
    if not isinstance(queries, list) or not 1 <= len(queries) <= MAX_QUERIES:
        raise ValueError("provide between one and eight research queries")
    result = []
    for term in queries:
        if (not isinstance(term, str) or not term.strip() or len(term) > 250
                or any(ord(ch) < 32 for ch in term)):
            raise ValueError("invalid research search term")
        result.append(term.strip())
    return result


def _fixed_api_get(host: str, target: str, *, token: str | None = None,
                   connection_factory=None, resolver=None) -> bytes:
    """Resolve approved search-API host, pin public IP, verify HTTPS certificate.

    The optional token is sent ONLY to BRAVE_HOST and never written to output.
    No redirects, cross-site follow-ups, HTML execution, or retry storms.
    """
    if host not in {CROSSREF_HOST, BRAVE_HOST} or not target.startswith("/"):
        raise ValueError("unsupported search provider")
    if token is not None and host != BRAVE_HOST:
        raise ValueError("search token cannot be sent to this provider")
    addresses = public_addresses(host, resolver=resolver)
    factory = connection_factory or _PinnedHTTPSConnection
    connection = factory(host, addresses[0], 10)
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "identity",
        "User-Agent": "NUMBERS4_AI_AGENT/0.7 predictive-method-research",
        "Connection": "close",
    }
    if token:
        headers["X-Subscription-Token"] = token
    try:
        connection.request("GET", target, headers=headers)
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("search provider unavailable or rate-limited")
        encoding = (response.getheader("Content-Encoding") or "identity").lower()
        if encoding != "identity":
            raise ValueError("unexpected compressed search response")
        content_type = (response.getheader("Content-Type") or "").lower()
        if "json" not in content_type:
            raise ValueError("search service did not return JSON")
        length = response.getheader("Content-Length")
        if length is not None and (not length.isdecimal() or int(length) > MAX_METADATA_BYTES):
            raise ValueError("search response exceeds size limit")
        response_bytes = response.read(MAX_METADATA_BYTES + 1)
        if len(response_bytes) > MAX_METADATA_BYTES:
            raise ValueError("oversized search response")
        return response_bytes
    finally:
        connection.close()


def _crossref_request(query: str, *, fetch=None) -> dict:
    args = urlencode({"query": query, "rows": RESULTS_PER_QUERY,
                      "select": "DOI,title,published,type,container-title,score,relation"})
    url = f"https://{CROSSREF_HOST}/works?{args}"
    if fetch is None:
        raw = _fixed_api_get(CROSSREF_HOST, f"/works?{args}")
    else:
        raw = fetch(url)
    return json.loads(raw.decode("utf-8"))


def _brave_request(query: str, token: str, *, fetch=None) -> dict:
    args = urlencode({"q": query, "count": RESULTS_PER_QUERY, "safesearch": "strict"})
    if fetch is None:
        raw = _fixed_api_get(BRAVE_HOST, f"/res/v1/web/search?{args}", token=token)
    else:
        raw = fetch(f"https://{BRAVE_HOST}/res/v1/web/search?{args}", token)
    return json.loads(raw.decode("utf-8"))


def _first_text(value: object, max_chars: int) -> str:
    text = value[0] if isinstance(value, list) and value else value
    if not isinstance(text, str):
        return ""
    return re.sub(r"\s+", " ", text).strip()[:max_chars]


def _year_from_crossref(record: dict) -> int | None:
    date_parts = record.get("published", {}).get("date-parts", [])
    if not (isinstance(date_parts, list) and date_parts and
            isinstance(date_parts[0], list) and date_parts[0]):
        return None
    value = date_parts[0][0]
    return value if type(value) is int and 1900 <= value <= 2200 else None


def _categories(title: str, excerpt: str) -> list[str]:
    haystack = (title + " " + excerpt).lower()
    return [name for name, markers in RESEARCH_CATEGORIES
            if any(marker in haystack for marker in markers)]


def _crossref_entries(response: dict, query: str) -> list[dict]:
    items = response.get("message", {}).get("items", [])
    if not isinstance(items, list):
        raise ValueError("invalid Crossref search results")
    out = []
    for item in items[:RESULTS_PER_QUERY]:
        if not isinstance(item, dict):
            continue
        doi = _first_text(item.get("DOI"), 200)
        title = _first_text(item.get("title"), 400)
        if not title or not re.fullmatch(r"10\.\d{4,9}/\S+", doi, flags=re.I):
            continue
        url = f"https://doi.org/{doi}"
        try:
            validate_public_url(url)
        except ValueError:
            continue
        category = _categories(title, "")
        if not category:
            continue
        out.append({
            "provider": "crossref",
            "type": "bibliographic_metadata",
            "id": doi.lower(),
            "title": title,
            "source_url": url,
            "publication_year": _year_from_crossref(item),
            "venue": _first_text(item.get("container-title"), 150),
            "research_categories": category,
            "retraction_or_update_metadata_present": bool(item.get("relation")),
            "discovery_query": query,
            "external_claim_verified": False,
            "full_text_independently_reviewed": False,
            "reproducible_lottery_edge_verified": False,
            "review_status": "candidate_requires_manual_scientific_review",
        })
    return out


def _brave_entries(response: dict, query: str) -> list[dict]:
    results = response.get("web", {}).get("results", [])
    if not isinstance(results, list):
        raise ValueError("invalid web search results")
    out = []
    for item in results[:RESULTS_PER_QUERY]:
        if not isinstance(item, dict):
            continue
        title = _first_text(item.get("title"), 400)
        description = _first_text(item.get("description"), 500)
        url = item.get("url")
        if not title or not isinstance(url, str):
            continue
        try:
            _, _, display = validate_public_url(url)
        except ValueError:
            continue
        category = _categories(title, description)
        if not category:
            continue
        out.append({
            "provider": "brave_web_search",
            "type": "unverified_web_search_result",
            "id": sha256(display.encode()).hexdigest(),
            "title": title,
            "source_url": display,
            "description": description,
            "research_categories": category,
            "discovery_query": query,
            "external_claim_verified": False,
            "full_text_independently_reviewed": False,
            "reproducible_lottery_edge_verified": False,
            "review_status": "candidate_requires_manual_scientific_review",
        })
    return out


def discover(queries: list[str], *, crossref_fetch=None, brave_fetch=None,
             brave_api_key: str | None = None, now: datetime | None = None) -> dict:
    """Search academic metadata and optionally broad web search.

    A missing Brave key is a normal, explicitly reported academic-only mode.
    Model code, weights, purchased tickets and verified bank draws are untouched.
    """
    queries = _queries(queries)
    now = (now or datetime.now(JST)).astimezone(JST)
    observations = []
    errors = []
    provider = ["crossref"]
    if brave_api_key:
        provider.append("brave_web_search")
    seen: set[tuple[str, str]] = set()
    for query in queries:
        for name in provider:
            try:
                if name == "crossref":
                    candidates = _crossref_entries(
                        _crossref_request(query, fetch=crossref_fetch), query)
                else:
                    candidates = _brave_entries(
                        _brave_request(query, brave_api_key or "", fetch=brave_fetch), query)
                for item in candidates:
                    key = (name, item["id"])
                    if key not in seen:
                        seen.add(key)
                        observations.append(item)
            except (OSError, ConnectionError, TimeoutError, ValueError, KeyError,
                    TypeError, UnicodeError, json.JSONDecodeError) as exc:
                errors.append({"provider": name,
                               "query_sha256": sha256(query.encode()).hexdigest(),
                               "error_type": type(exc).__name__})
    return {
        "version": VERSION,
        "searched_at_jst": now.isoformat(timespec="seconds"),
        "queries": queries,
        "providers_attempted": provider,
        "web_search_enabled": bool(brave_api_key),
        "web_search_provider_requires_configured_key": True,
        "candidate_count": len(observations),
        "candidates": observations,
        "errors": errors,
        "review_policy": "literature_and_search_results_are_hypotheses_not_proven_model_improvements",
        "automatic_code_execution_from_sources": False,
        "automatic_model_training_from_sources": False,
        "official_results_verified": False,
        "automatic_production_model_promotion": False,
    }


def _model_assessment(report: dict) -> dict:
    models = report["retrospective_holdout"]["models"]
    uniform = models["uniform"]
    assessments = {}
    for name, result in models.items():
        gain = result["mean_log_score_edge_vs_uniform"]
        hit_diff = result["straight_hits"] - uniform["straight_hits"]
        descriptive_good = (
            name != "uniform" and gain > 0 and hit_diff > 0 and
            result["paired_exact_discordance_p_exploratory"] < 0.05
        )
        assessments[name] = {
            "holdout_rounds": result["evaluated_draws"],
            "straight_hits": result["straight_hits"],
            "difference_vs_uniform_hits": hit_diff,
            "mean_log_score_edge_vs_uniform": gain,
            "exploratory_screen_passed": descriptive_good,
            "prospective_independent_confirmation": False,
            "eligible_for_production": False,
            "decision": "research_only_no_prospective_validation",
        }
    return assessments


def _triage_scientific_hypotheses(discovery: dict, report: dict) -> list[dict]:
    """Link untrusted research leads to existing implemented, frozen tests.

    DOI existence and search snippets NEVER verify a forecasting advantage.
    This creates an actionable review queue without loading external code or
    changing any trainable architecture based on untrusted web text.
    """
    assessments = report["retrospective_holdout"]["models"]
    linked = []
    for item in discovery["candidates"]:
        categories = item.get("research_categories", [])
        if "machine_learning" in categories or "probability" in categories:
            applicable = [x for x in assessments if x.startswith("positional_")]
        elif "validation" in categories or "randomness" in categories:
            applicable = ["uniform"]
        else:
            applicable = []
        if not applicable:
            continue
        bibliographic = (
            item.get("provider") == "crossref" and
            item.get("publication_year") is not None and
            bool(item.get("venue")) and
            item.get("retraction_or_update_metadata_present") is False
        )
        linked.append({
            "source_id": item["id"],
            "source_url": item["source_url"],
            "metadata_screen_passed": bibliographic,
            "peer_review_and_claims_independently_verified": False,
            "suggested_existing_experiment_models": applicable,
            "model_results_historical_exploratory_only": {
                name: {
                    "straight_hits": assessments[name]["straight_hits"],
                    "mean_log_score_edge_vs_uniform":
                        assessments[name]["mean_log_score_edge_vs_uniform"],
                } for name in applicable
            },
            "automatic_model_code_adoption": False,
            "next_step": ("read_original_and_validate_methods_before_new_test"
                          if bibliographic else
                          "establish_reliable_publication_and_original_source"),
        })
    return linked


def run_research_cycle(root: Path, *, queries: list[str] | None = None,
                       brave_api_key: str | None = None,
                       crossref_fetch=None, brave_fetch=None,
                       now: datetime | None = None) -> dict:
    discovery = discover(queries or list(DEFAULT_TOPICS),
                         brave_api_key=brave_api_key,
                         crossref_fetch=crossref_fetch, brave_fetch=brave_fetch,
                         now=now)
    rows, provenance = load_archive(root)
    if not rows or provenance.get("officially_verified") is not False:
        raise ValueError("secondary research archive with explicit limits required")
    report = evaluate(rows, split_round=5000)
    return {
        "version": VERSION,
        "status": "research_cycle_complete_no_model_promotion",
        "discovery": discovery,
        "source_archive_git_blob_sha1": provenance["git_blob_sha1"],
        "source_archive_last_round": provenance["last_round"],
        "scientific_hypothesis_review_queue": _triage_scientific_hypotheses(discovery, report),
        "experiment": {
            "protocol": "historical_posthoc_challenger_benchmark",
            "development_first_round": report["development"]["first_round"],
            "development_last_round": report["development"]["last_round"],
            "historical_late_cohort_first_round":
                report["retrospective_holdout"]["first_round"],
            "historical_late_cohort_last_round":
                report["retrospective_holdout"]["last_round"],
            "model_assessments": _model_assessment(report),
            "research_publication_discoveries_did_not_change_model_specifications": True,
            "predictions_from_prior_draws_only": True,
        },
        "genuine_future_out_of_sample_verified_draws": 0,
        "forecast_skill_confirmed": False,
        "official_bank_results_verified_by_this_cycle": False,
        "model_auto_promotion_authorized": False,
        "external_code_executed": False,
        "production_forecast_ledger_modified": False,
        "interpretation": (
            "Internet research discovers candidates, not predictive truth. "
            "Already-implemented models are benchmarked on retrospective data; "
            "new methods require independent review, explicit implementation "
            "and preregistered prospective testing before any production change."
        ),
    }


def write_research_cycle(root: Path, output: Path, **kwargs) -> dict:
    location = output if output.is_absolute() else root / output
    # Research outputs cannot be written inside the source-of-truth ledgers.
    resolved = location.resolve()
    protected = [(root / dirname).resolve() for dirname in ("data", "numbers4_agent")]
    if any(resolved == path or path in resolved.parents for path in protected):
        raise ValueError("research output may not overwrite data or production code")
    report = run_research_cycle(root, **kwargs)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                   allow_nan=False) + "\n", encoding="utf-8")
    return report
