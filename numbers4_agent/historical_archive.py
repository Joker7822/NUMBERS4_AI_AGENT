"""Strict Numbers4 secondary historical archive (not official attestation).

Historical archive is never a source for the Production issuance/graded ledger.
All 4-digit numbers remain strings so leading zeroes are preserved.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .rules import four_digits

ARCHIVE = Path("data/historical_results.csv")
PROVENANCE = Path("data/historical_archive_provenance.json")
VERSION = "numbers4-historical-archive-v1"
STATUS = "secondary_public_mirrors_agree_not_officially_verified"
JST = timezone(timedelta(hours=9))


def _git_blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def load_archive(root: Path) -> tuple[list[dict], dict]:
    """Return a complete, sequential history or fail closed; never fill gaps."""
    csv_path = root / ARCHIVE
    meta_path = root / PROVENANCE
    if not csv_path.is_file() and not meta_path.is_file():
        return [], {
            "status": "not_loaded", "record_count": 0,
            "officially_verified": False, "forecast_grading_authorized": False,
        }
    if not csv_path.is_file() or not meta_path.is_file():
        raise ValueError("historical archive and provenance must both be present")
    raw = csv_path.read_bytes()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if (meta.get("version") != VERSION or meta.get("status") != STATUS or
            meta.get("officially_verified") is not False or
            meta.get("forecast_grading_authorized") is not False or
            meta.get("source_independence_not_established") is not True or
            meta.get("git_blob_sha1") != _git_blob_sha1(raw)):
        raise ValueError("historical archive provenance mismatch or unsafe authority")
    upstream = meta.get("public_source_revisions")
    if (not isinstance(upstream, list) or len(upstream) != 2 or
            not all(isinstance(x, dict) and isinstance(x.get("commit_sha"), str) and
                    re.fullmatch(r"[0-9a-f]{40}", x["commit_sha"]) and
                    isinstance(x.get("blob_sha"), str) and
                    re.fullmatch(r"[0-9a-f]{40}", x["blob_sha"]) and
                    isinstance(x.get("url"), str) and
                    x["url"].startswith("https://github.com/") for x in upstream)):
        raise ValueError("historical archive source revisions missing")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if reader.fieldnames != ["round", "draw_date", "winning_number"]:
        raise ValueError("historical archive CSV header mismatch")
    rows = []
    previous_date = None
    today = datetime.now(JST).date()
    for record in reader:
        if record["round"] != str(len(rows) + 1):
            raise ValueError("historical archive missing, duplicate or reordered round")
        n = record.get("winning_number")
        four_digits(n)
        draw_date = date.fromisoformat(record["draw_date"])
        if draw_date.isoformat() != record["draw_date"] or (
                previous_date is not None and draw_date <= previous_date
        ) or draw_date > today or draw_date.weekday() > 4:
            raise ValueError("historical archive draw date invalid or out of order")
        if set(record) != {"round", "draw_date", "winning_number"}:
            raise ValueError("historical archive has unknown fields")
        rows.append({"round": len(rows) + 1, "draw_date": record["draw_date"],
                     "winning_number": n})
        previous_date = draw_date
    if not rows or meta.get("record_count") != len(rows) or meta.get("first_round") != 1 or (
            meta.get("last_round") != len(rows)
    ) or meta.get("first_draw_date") != rows[0]["draw_date"] or (
            meta.get("last_draw_date") != rows[-1]["draw_date"]
    ) or meta.get("latest_number") != rows[-1]["winning_number"]:
        raise ValueError("historical archive counts or endpoints mismatch")
    return rows, meta


def archive_summary(root: Path) -> dict:
    rows, meta = load_archive(root)
    if not rows:
        return meta
    return {
        "status": STATUS,
        "record_count": len(rows),
        "first_round": rows[0]["round"],
        "first_draw_date": rows[0]["draw_date"],
        "last_round": rows[-1]["round"],
        "last_draw_date": rows[-1]["draw_date"],
        "latest_number": rows[-1]["winning_number"],
        "officially_verified": False,
        "forecast_grading_authorized": False,
        "source_independence_not_established": True,
        "git_blob_sha1": meta["git_blob_sha1"],
    }
