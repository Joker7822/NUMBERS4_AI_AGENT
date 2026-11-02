"""Incremental provider-compliant collection without a lifetime source quota.

A research cycle has a finite budget to protect API quotas and GitHub Actions;
there is NO application-wide maximum number of queries, domains or sources.
Progress is versioned and reproducible, and newly seen research sources are
append-only SHA-chained. Provider-specific pagination restrictions STILL apply.

All retrieved records are UNTRUSTED RESEARCH METADATA, not training labels,
confirmed claims, executable instructions or official draw records.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

from .research_discovery import (
    JST, RESULTS_PER_QUERY, BRAVE_HOST, CROSSREF_HOST,
    _brave_entries, _brave_request, _crossref_entries, _crossref_request,
    _queries,
)
from .store import append, load

VERSION = "numbers4-continuous-discovery-v1"
PROGRESS_PATH = Path("research/discovery_progress.json")
SOURCE_LEDGER = Path("research/discovery_sources.jsonl")
REQUESTS_PER_RUN = 8
CROSSREF_OFFSET_MAX = 10000
BRAVE_MAX_PAGES = 10
REFRESH_DAYS = 1


def _key(provider: str, query: str) -> str:
    return sha256(f"{provider}\n{query}".encode("utf-8")).hexdigest()


def _progress(root: Path) -> dict:
    path = root / PROGRESS_PATH
    if not path.is_file():
        return {"version": VERSION, "request_counter": 0, "positions": {}}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(raw, dict) or raw.get("version") != VERSION
            or type(raw.get("request_counter")) is not int
            or raw["request_counter"] < 0 or
            not isinstance(raw.get("positions"), dict)):
        raise ValueError("invalid or obsolete research pagination checkpoint")
    for key, value in raw["positions"].items():
        if (not isinstance(key, str) or len(key) != 64
                or any(c not in "0123456789abcdef" for c in key)
                or not isinstance(value, dict)
                or value.get("provider") not in ("crossref", "brave_web_search")
                or type(value.get("next_offset")) is not int
                or value["next_offset"] < 0
                or type(value.get("exhausted")) is not bool
                or not isinstance(value.get("last_checked_date"), str)):
            raise ValueError("invalid research pagination position")
        datetime.fromisoformat(value["last_checked_date"])
    return raw


def _seen(root: Path) -> tuple[set[tuple[str, str]], int]:
    history = load(root / SOURCE_LEDGER)
    visited = set()
    for event in history:
        if (event.get("version") != VERSION
                or not isinstance(event.get("sources"), list)):
            raise ValueError("unrecognized cumulative research-source ledger")
        for source in event["sources"]:
            if not isinstance(source, dict):
                raise ValueError("malformed research-source record")
            provider, identifier = source.get("provider"), source.get("id")
            if not isinstance(provider, str) or not isinstance(identifier, str):
                raise ValueError("missing cumulative source identity")
            identity = (provider, identifier)
            if identity in visited:
                raise ValueError("cumulative research source identity duplicated")
            visited.add(identity)
    return visited, len(history)


def collect(root: Path, queries: list[str], *, brave_api_key: str | None = None,
            crossref_fetch=None, brave_fetch=None,
            request_budget: int = REQUESTS_PER_RUN,
            now: datetime | None = None) -> tuple[dict, dict]:
    """Fetch pages in a rotating, resumable queue; return staged state.

    Max requests per run is a RESOURCE budget, not a cumulative acquisition
    cap. Crossref offset 10K and Brave 10 pages are PROVIDER API ceilings.
    Freshly exhausted searches may be polled the following day.
    """
    questions = _queries(queries)
    if type(request_budget) is not int or not 1 <= request_budget <= 100:
        raise ValueError("per-run request budget must be between 1 and 100")
    now = (now or datetime.now(JST)).astimezone(JST)
    state = _progress(root)
    seen, old_batches = _seen(root)
    known_before = len(seen)
    providers = ["crossref"] + (["brave_web_search"] if brave_api_key else [])
    tasks = [(provider, query, _key(provider, query))
             for query in questions for provider in providers]
    positions = dict(state["positions"])
    observations = []
    errors = []
    new_sources = []
    requested = 0
    pages_received = 0
    failed_in_run = set()
    exhausted_today = 0
    # Each run rotates the starting provider/query. Stopped queries are
    # automatically revisited after the next JST date to find new deposits.
    pointer = state["request_counter"] % len(tasks)
    no_more = 0
    while requested < request_budget and no_more < len(tasks):
        provider, query, key = tasks[pointer]
        pointer = (pointer + 1) % len(tasks)
        value = dict(positions.get(key, {
            "provider": provider, "next_offset": 0, "exhausted": False,
            "last_checked_date": "1970-01-01",
        }))
        if value.get("provider") != provider:
            raise ValueError("research provider identity changed in checkpoint")
        if value["exhausted"] and value["last_checked_date"] < now.date().isoformat():
            value["next_offset"] = 0
            value["exhausted"] = False
        if key in failed_in_run or value["exhausted"]:
            no_more += 1
            if value["exhausted"]:
                exhausted_today += 1
            continue
        no_more = 0
        offset = value["next_offset"]
        if (provider == "crossref" and offset > CROSSREF_OFFSET_MAX) or (
                provider == "brave_web_search" and offset >= BRAVE_MAX_PAGES):
            value["exhausted"] = True
            value["last_checked_date"] = now.date().isoformat()
            positions[key] = value
            continue
        requested += 1
        try:
            if provider == "crossref":
                response = _crossref_request(
                    query, offset=offset, fetch=crossref_fetch)
                message = response.get("message")
                if not isinstance(message, dict) or not isinstance(message.get("items"), list):
                    raise ValueError("Crossref response missing items")
                entries = _crossref_entries(response, query)
                fetched = len(message["items"])
                value["next_offset"] = offset + RESULTS_PER_QUERY
                value["exhausted"] = (
                    fetched < RESULTS_PER_QUERY or
                    value["next_offset"] > CROSSREF_OFFSET_MAX)
            else:
                response = _brave_request(
                    query, brave_api_key or "", offset=offset,
                    fetch=brave_fetch)
                web = response.get("web")
                if not isinstance(web, dict) or not isinstance(web.get("results"), list):
                    raise ValueError("Brave response missing web results")
                entries = _brave_entries(response, query)
                more = response.get("query", {}).get("more_results_available")
                value["next_offset"] = offset + 1
                value["exhausted"] = (
                    more is False or value["next_offset"] >= BRAVE_MAX_PAGES
                    or not web["results"])
            value["last_checked_date"] = now.date().isoformat()
            positions[key] = value
            pages_received += 1
            for record in entries:
                identity = (record["provider"], record["id"])
                if identity not in seen:
                    seen.add(identity)
                    new_sources.append(record)
                observations.append(record)
        except (OSError, ConnectionError, TimeoutError, ValueError,
                KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            failed_in_run.add(key)
            errors.append({
                "provider": provider, "query_sha256": sha256(query.encode()).hexdigest(),
                "offset": offset, "error_type": type(exc).__name__,
                "retry_in_future_run": True,
            })
    staged = {
        "version": VERSION, "request_counter": state["request_counter"] + requested,
        "positions": positions,
    }
    discovery = {
        "version": VERSION, "searched_at_jst": now.isoformat(timespec="seconds"),
        "queries": questions, "providers_attempted": providers,
        "web_search_enabled": bool(brave_api_key),
        "web_search_provider_requires_configured_key": True,
        "candidate_count": len(observations), "candidates": observations,
        "new_unique_sources": len(new_sources),
        "lifetime_unique_sources_after_commit": len(seen),
        "lifetime_unique_sources_before_run": known_before,
        "cumulative_batches_before_run": old_batches,
        "request_budget_this_run": request_budget,
        "requests_attempted_this_run": requested,
        "pages_received_this_run": pages_received,
        "checked_queries": len(questions),
        "provider_page_limits_obeyed": True,
        "application_lifetime_source_quota": None,
        "per_http_response_size_and_timeout_limits_enabled": True,
        "errors": errors, "review_policy": "search_metadata_is_untrusted_not_model_proof",
        "automatic_code_execution_from_sources": False,
        "automatic_model_training_from_sources": False,
        "official_results_verified": False,
        "automatic_production_model_promotion": False,
    }
    return discovery, {"progress": staged, "new_sources": new_sources}


def persist(root: Path, staged: dict, discovery: dict) -> None:
    """Commit source ledger and checkpoint only AFTER the full replay succeeds."""
    expected = _progress(root)
    if (not isinstance(staged, dict) or
            staged.get("progress", {}).get("request_counter", -1) <
            expected["request_counter"] or
            discovery.get("version") != VERSION or
            len(staged.get("new_sources", [])) != discovery["new_unique_sources"]):
        raise ValueError("research acquisition staging is inconsistent")
    new = staged["new_sources"]
    if new:
        append(root / SOURCE_LEDGER, {
            "version": VERSION, "observed_at_jst": discovery["searched_at_jst"],
            "sources": new,
            "scope": "untrusted_bibliographic_and_web_search_metadata_only",
            "can_train_production": False, "purchase_authorized": False,
        })
    destination = root / PROGRESS_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(staged["progress"], ensure_ascii=False, sort_keys=True,
                   indent=2, allow_nan=False) + "\n", encoding="utf-8")
