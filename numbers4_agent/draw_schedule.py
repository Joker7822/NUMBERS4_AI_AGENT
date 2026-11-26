"""Reviewed schedule validation. A human review is not independent publisher proof."""
from __future__ import annotations

from datetime import datetime, time
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlsplit

from .sources import JST, aware_time, iso_date
from .store import canonical

SCHEDULE_PATH = Path("research/approved_draw_schedule.json")
VERSION = "numbers4-approved-draw-schedule-v1"
DEADLINE_CLOCK = time(18, 0)
HOSTS = {"www.mizuhobank.co.jp", "www.takarakuji-official.jp"}


def entry_hash(item: dict) -> str:
    return sha256(canonical(item)).hexdigest()


def reviewed_schedule(root: Path) -> list[dict]:
    path = root / SCHEDULE_PATH
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("version") != VERSION
            or not isinstance(data.get("rounds"), list)):
        raise ValueError("invalid reviewed draw schedule")
    last_round = 0
    last_date = None
    for item in data["rounds"]:
        if (not isinstance(item, dict)
                or type(item.get("round")) is not int or item["round"] < 2
                or item["round"] <= last_round or item.get("human_reviewed") is not True):
            raise ValueError("invalid or duplicate reviewed draw round")
        day = iso_date(item["draw_date"])
        if day.weekday() >= 5 or (last_date is not None and day <= last_date):
            raise ValueError("invalid, duplicate or unordered reviewed draw date")
        source = urlsplit(item["source_url"])
        if (source.scheme != "https" or source.hostname not in HOSTS
                or source.username or source.password or source.port not in (None, 443)
                or not source.path or source.path == "/"):
            raise ValueError("reviewed schedule requires an official HTTPS source page")
        reviewed = aware_time(item["reviewed_at_jst"]).astimezone(JST)
        if reviewed >= datetime.combine(day, DEADLINE_CLOCK, JST):
            raise ValueError("schedule review must precede the freeze deadline")
        last_round, last_date = item["round"], day
    return data["rounds"]


def target_for_date(root: Path, draw_date: str) -> dict | None:
    iso_date(draw_date)
    return next((item for item in reviewed_schedule(root)
                 if item["draw_date"] == draw_date), None)


def require_target(root: Path, round_number: int, draw_date: str,
                   issued: datetime) -> dict:
    item = target_for_date(root, draw_date)
    if item is None or item["round"] != round_number:
        raise ValueError("no reviewed official schedule for the target round/date")
    if issued.utcoffset() is None or aware_time(item["reviewed_at_jst"]) > issued:
        raise ValueError("schedule review occurred after forecast issuance")
    return item


def validate_forecast_schedule(root: Path, forecast: dict) -> None:
    day = iso_date(forecast["draw_date"])
    issued = aware_time(forecast["issued_at_jst"]).astimezone(JST)
    deadline = aware_time(forecast["freeze_deadline_jst"]).astimezone(JST)
    if (type(forecast.get("round")) is not int or forecast["round"] < 2
            or issued.date() != day or issued >= deadline
            or deadline != datetime.combine(day, DEADLINE_CLOCK, JST)):
        raise ValueError("invalid pre-draw forecast timestamp or deadline")
    item = require_target(root, forecast["round"], forecast["draw_date"], issued)
    if forecast.get("schedule_entry_sha256") != entry_hash(item):
        raise ValueError("reviewed schedule evidence changed after forecast issuance")
