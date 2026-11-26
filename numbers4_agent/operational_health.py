"""Bounded, read-only operational diagnostics; no prediction or purchase authority."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from .draw_schedule import reviewed_schedule, DEADLINE_CLOCK
from .sources import JST, aware_time
from .store import file_hash

VERSION = "numbers4-operational-health-v1"
INGESTION_PATH = Path("research/official_ingestion_status.json")
MAX_AGE_HOURS = 96  # includes the normal weekend pause
HOSTS = {"mizuhobank", "rakuten"}


def _count(report, key):
    value = report.get(key)
    if type(value) is not int or value < 0:
        raise ValueError("invalid operational counter: " + key)
    return value


def compact_ingestion(report: dict) -> dict:
    """Persist only counters and publisher names, not arbitrary error messages."""
    if (report.get("version") != "numbers4-official-fetch-v1"
            or report.get("automatic_model_promotion") is not False
            or report.get("verified_claim_only_on_matching_records") is not True):
        raise ValueError("unsafe official ingestion report")
    stamp = aware_time(report["checked_at_jst"]).astimezone(JST).isoformat(timespec="seconds")
    bank, rakuten, matched, new = (_count(report, k) for k in
                                  ("bank_rows", "rakuten_rows", "publisher_matched_rows", "new_verified_rows"))
    status = report.get("status")
    if (new > matched or matched > min(bank, rakuten)
            or status not in {"publisher_disagreement", "verified", "blocked_no_bank_verified_results"}
            or (status == "verified" and matched == 0)
            or (status == "blocked_no_bank_verified_results" and matched != 0)):
        raise ValueError("inconsistent official ingestion counters")
    denied = report.get("publisher_access_denials")
    if not isinstance(denied, dict) or set(denied) - HOSTS:
        raise ValueError("invalid publisher denial diagnostic")
    ledger = report.get("ledger_sha256")
    if not isinstance(ledger, str) or len(ledger) != 64 or any(c not in "0123456789abcdef" for c in ledger):
        raise ValueError("invalid official ledger hash")
    return {
        "version": "numbers4-official-ingestion-summary-v1",
        "checked_at_jst": stamp, "status": status, "bank_rows": bank,
        "rakuten_rows": rakuten, "publisher_matched_rows": matched,
        "new_verified_rows": new, "denied_publishers": sorted(denied),
        "requests_skipped_after_access_denial": _count(report, "requests_skipped_after_access_denial"),
        "ledger_sha256": ledger, "actual_purchase": False,
    }


def ingestion_health(root: Path, now: datetime) -> dict:
    base = {"state": "not_checked", "checked_at_jst": None, "age_hours": None,
            "bank_rows": None, "rakuten_rows": None, "matched_rows": None,
            "denied_publishers": [], "skipped_requests": None}
    path = root / INGESTION_PATH
    if not path.is_file():
        return base
    try:
        r = json.loads(path.read_text(encoding="utf-8"))
        if r.get("version") != "numbers4-official-ingestion-summary-v1" or r.get("actual_purchase") is not False:
            raise ValueError("unsafe ingestion summary")
        stamp = aware_time(r["checked_at_jst"])
        age = (now - stamp).total_seconds() / 3600
        bank, rakuten, matched, new, skipped = (_count(r, k) for k in
            ("bank_rows", "rakuten_rows", "publisher_matched_rows", "new_verified_rows", "requests_skipped_after_access_denial"))
        denied = r["denied_publishers"]
        if (age < -0.1 or not isinstance(denied, list) or len(denied) != len(set(denied))
                or set(denied) - HOSTS or matched > min(bank, rakuten) or new > matched
                or r["status"] not in {"publisher_disagreement", "verified", "blocked_no_bank_verified_results"}
                or (r["status"] == "verified" and not matched)
                or (r["status"] == "blocked_no_bank_verified_results" and matched)
                or r["ledger_sha256"] != file_hash(root / "data/auto_verified_draws.jsonl")):
            raise ValueError("invalid or mismatched ingestion evidence")
        state = ("stale" if age > MAX_AGE_HOURS else
                 "publisher_disagreement" if r["status"] == "publisher_disagreement" else
                 "access_denied" if denied else
                 "no_matches" if not matched else "matched")
        return {"state": state, "checked_at_jst": stamp.astimezone(JST).isoformat(timespec="seconds"),
                "age_hours": round(max(0, age), 3), "bank_rows": bank,
                "rakuten_rows": rakuten, "matched_rows": matched,
                "denied_publishers": denied, "skipped_requests": skipped}
    except (ValueError, KeyError, TypeError, AttributeError, OSError):
        return {**base, "state": "invalid_evidence"}


def snapshot(root: Path, now: datetime, prospective: dict) -> dict:
    now = now.astimezone(JST)
    official = ingestion_health(root, now)
    today = now.date().isoformat()
    try:
        calendar = reviewed_schedule(root)
        item = next((x for x in calendar if x["draw_date"] == today), None)
        future = sum(x["draw_date"] >= today for x in calendar)
        schedule_state = ("no_reviewed_target" if item is None else
                          "review_not_yet_effective" if aware_time(item["reviewed_at_jst"]) > now else
                          "freeze_window_closed" if now.time() >= DEADLINE_CLOCK else "reviewed_target")
        schedule = {"state": schedule_state, "reviewed_entries_today_or_later": future,
                    "target_round": item["round"] if item else None}
    except (ValueError, KeyError, TypeError, OSError):
        schedule = {"state": "invalid_schedule", "reviewed_entries_today_or_later": None, "target_round": None}
    rows = _count(prospective, "verified_official_draws_available")
    shadow = _count(prospective, "shadow_forecasts_recorded")
    witnesses = _count(prospective, "independently_witnessed_forecasts")
    eligible = _count(prospective, "eligible_prospective_draws")
    required = _count(prospective, "required_prospective_draws")
    if not required or not eligible <= witnesses <= shadow or eligible > rows:
        raise ValueError("invalid prospective operational counters")
    integrity = bool(prospective.get("integrity_blocker"))
    return {
        "version": VERSION, "official_ingestion": official, "schedule": schedule,
        "training": {"state": "integrity_blocked" if integrity else "no_verified_draws" if not rows else "verified_history_available", "verified_draws": rows},
        "publication": {"state": "integrity_blocked" if integrity else "no_forecasts" if not shadow else "witnesses_pending" if witnesses < shadow else "witnesses_recorded",
                        "forecasts": shadow, "witnesses": witnesses},
        "prospective": {"state": "integrity_blocked" if integrity else "insufficient_draws" if eligible < required else "minimum_count_met_not_proof",
                        "eligible": eligible, "required": required},
        "max_ingestion_age_hours": MAX_AGE_HOURS,
        "actual_purchase": False, "promotion_authorized_by_monitor": False,
    }


if __name__ == "__main__":
    print(json.dumps(compact_ingestion(json.load(sys.stdin)), ensure_ascii=False, indent=2, allow_nan=False))
