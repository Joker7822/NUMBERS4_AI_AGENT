"""Two-provider observation reconciliation; observations require human review."""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from .rules import four_digits
from .store import load, append

JST = timezone(timedelta(hours=9))
OBSERVATION_FILE = "source_observations.jsonl"
PROVIDERS = {
    "mizuhobank": "www.mizuhobank.co.jp",
    "takarakuji_official": "www.takarakuji-official.jp",
}


def iso_date(value: str) -> date:
    result = date.fromisoformat(value)
    if result.isoformat() != value:
        raise ValueError("draw date must be YYYY-MM-DD")
    return result


def aware_time(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timestamp must include UTC offset")
    return result


def validate_observation(record: dict) -> None:
    if type(record.get("round")) is not int or record["round"] <= 0:
        raise ValueError("invalid Numbers4 draw round")
    draw_date = iso_date(record["draw_date"])
    four_digits(record["winning_number"])
    source = record.get("source")
    if source not in PROVIDERS:
        raise ValueError("unknown independent official source")
    url = urlparse(record.get("source_url", ""))
    if (url.scheme != "https" or url.hostname != PROVIDERS[source] or
            url.username or url.password or url.port not in (None, 443)):
        raise ValueError("source URL must use the official, allowlisted HTTPS host")
    stamp = aware_time(record["observed_at_jst"]).astimezone(JST)
    if stamp.date() < draw_date or (stamp.date() == draw_date and stamp.time() < time(18, 30)):
        raise ValueError("cannot cite an observation before the draw-day release window")


def observation_rows(root: Path) -> list[dict]:
    rows = load(root / "data" / OBSERVATION_FILE)
    seen = set()
    for row in rows:
        validate_observation(row)
        key = (row["round"], row["source"])
        if key in seen:
            raise ValueError(f"duplicate source attestation for draw {row['round']}")
        seen.add(key)
    return rows


def record_observation(root: Path, *, round_number: int, draw_date: str,
                       number: str, source: str, url: str,
                       at: datetime | None = None) -> dict:
    when = (at or datetime.now(JST)).astimezone(JST)
    if when > datetime.now(JST) + timedelta(minutes=5):
        raise ValueError("observation time cannot be in the future")
    row = {
        "round": round_number, "draw_date": draw_date, "winning_number": number,
        "source": source, "source_url": url,
        "observed_at_jst": when.isoformat(timespec="seconds"),
        "provenance_scope": "human_entered_claim_not_automatically_fetched",
    }
    validate_observation(row)
    observation_rows(root)
    if any(r["round"] == round_number and r["source"] == source
           for r in observation_rows(root)):
        raise ValueError("source attestation already exists; do not overwrite evidence")
    return append(root / "data" / OBSERVATION_FILE, row)


def reconcile(root: Path) -> dict:
    by_round: dict[int, list[dict]] = defaultdict(list)
    for row in observation_rows(root):
        by_round[row["round"]].append(row)
    result = {}
    for rnd, evidence in sorted(by_round.items()):
        complete = len(evidence) == len(PROVIDERS)
        agrees = len({(r["draw_date"], r["winning_number"]) for r in evidence}) == 1
        state = "two_source_entered_consistent" if complete and agrees else (
            "source_conflict" if complete else "single_source_only")
        data = {"round": rnd, "status": state, "providers": sorted(r["source"] for r in evidence)}
        if state == "two_source_entered_consistent":
            data["draw_date"] = evidence[0]["draw_date"]
            data["winning_number"] = evidence[0]["winning_number"]
            data["observation_sha256"] = sorted(r["event_sha256"] for r in evidence)
        result[rnd] = data
    return result


def corroborated_draws(root: Path) -> list[dict]:
    return [v for v in reconcile(root).values() if v["status"] == "two_source_entered_consistent"]
