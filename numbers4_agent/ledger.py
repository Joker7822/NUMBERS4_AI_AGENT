"""Explicit, time-bound, append-only publication, never actual purchases."""
from __future__ import annotations
from datetime import datetime, time, timedelta
from pathlib import Path

from .rules import validate_play, PlayType
from .sources import JST, iso_date, aware_time, corroborated_draws
from .store import append, load, file_hash

ISSUED_FILE = "issued_forecasts.jsonl"
MAX_PUBLICATION_CLOCK = time(18, 30)


def read_issued(root: Path) -> list[dict]:
    records = load(root / "data" / ISSUED_FILE)
    known = set()
    for r in records:
        rnd = r.get("target_round")
        if not isinstance(rnd, int) or isinstance(rnd, bool) or rnd < 1 or rnd in known:
            raise ValueError("duplicate or invalid published forecast round")
        known.add(rnd)
        if not isinstance(r.get("numbers"), list) or len(r["numbers"]) != 5:
            raise ValueError("exactly five issued forecasts are required")
        mode = PlayType(r["mode"])
        for n in r["numbers"]:
            validate_play(n, mode)
        if len(set(r["numbers"])) != 5:
            raise ValueError("duplicate issued numbers")
        if mode is not PlayType.STRAIGHT and len({"".join(sorted(n)) for n in r["numbers"]}) != 5:
            raise ValueError("overlapping box/set permutations")
        raw_deadline = aware_time(r["freeze_deadline_jst"])
        raw_created = aware_time(r["issued_at_jst"])
        if raw_deadline.utcoffset() != timedelta(hours=9) or raw_created.utcoffset() != timedelta(hours=9):
            raise ValueError("forecast publication timestamps must use JST")
        deadline = raw_deadline.astimezone(JST)
        created = raw_created.astimezone(JST)
        when = iso_date(r["draw_date"])
        if (deadline.date() != when or deadline.time() > MAX_PUBLICATION_CLOCK or
                not created < deadline or created.date() > when):
            raise ValueError("issued forecast is not demonstrably pre-deadline")
        if r.get("actual_purchase") is not False or r.get("scope") != "published_advice_not_purchase":
            raise ValueError("publication authority overstated")
    return records


def issue(root: Path, *, target_round: int, draw_date: str,
          mode: str, numbers: list[str], deadline_jst: str,
          model_version: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(JST)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("issue timestamp must be timezone aware")
    now = now.astimezone(JST)
    if not isinstance(target_round, int) or isinstance(target_round, bool) or target_round <= 0:
        raise ValueError("invalid target draw round")
    iso_date(draw_date)
    raw_deadline = aware_time(deadline_jst)
    if raw_deadline.utcoffset() != timedelta(hours=9):
        raise ValueError("deadline must be JST")
    deadline = raw_deadline.astimezone(JST)
    if deadline.date().isoformat() != draw_date or deadline.time() > MAX_PUBLICATION_CLOCK:
        raise ValueError("deadline must be on draw day at or before 18:30 JST")
    if now >= deadline:
        raise ValueError("deadline has passed; retroactive issuance forbidden")
    if len(numbers) != 5:
        raise ValueError("a published portfolio must contain exactly five tickets")
    selected_mode = PlayType(mode)
    for n in numbers:
        validate_play(n, selected_mode)
    if len(set(numbers)) != 5:
        raise ValueError("duplicate issued number")
    if selected_mode is not PlayType.STRAIGHT and len({"".join(sorted(n)) for n in numbers}) != 5:
        raise ValueError("box/set tickets have redundant permutations")
    existing = read_issued(root)
    if any(r["target_round"] == target_round for r in existing):
        raise ValueError("forecast already published for target round")
    draws = corroborated_draws(root)
    if draws and target_round <= max(r["round"] for r in draws):
        raise ValueError("target must be after latest corroborated draw")
    if not model_version or not isinstance(model_version, str) or len(model_version) > 80:
        raise ValueError("invalid model version")
    return append(root / "data" / ISSUED_FILE, {
        "target_round": target_round, "draw_date": draw_date,
        "mode": selected_mode.value, "numbers": list(numbers),
        "freeze_deadline_jst": deadline.isoformat(timespec="seconds"),
        "issued_at_jst": now.isoformat(timespec="seconds"),
        "model_version": model_version,
        "observations_prefix_sha256": file_hash(root / "data" / "source_observations.jsonl"),
        "actual_purchase": False, "scope": "published_advice_not_purchase",
        "promotion_eligible": False,
    })
