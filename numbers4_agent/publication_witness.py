"""Check GitHub server event timestamps before treating a shadow as prospective.

A local timestamp, SHA chain, commit author date or retrospective CSV is NEVER
sufficient. A receipt is issued only when the forecast line appears for the
first time in a Git commit that triggered a public GitHub 'push' workflow run
whose GitHub server created_at predates the draw's shadow freeze deadline.
This verifies observable GitHub publication, not an independent digital
signature or a guarantee that lotteries are predictable.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .automatic_learning import (
    FORECAST_PATH, VERSION, WITNESS_PATH, _time, _validated_witnesses,
)
from .store import append, load

PUBLIC_REPO = "Joker7822/NUMBERS4_AI_AGENT"
API = f"https://api.github.com/repos/{PUBLIC_REPO}/actions/runs"
COMMIT = re.compile(r"^[a-f0-9]{40}$")


def _git(root: Path, *args: str) -> str:
    cp = subprocess.run(["git", *args], cwd=root, text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        timeout=15, check=False)
    if cp.returncode != 0:
        raise ValueError("Git publication history unavailable")
    return cp.stdout


def _find_introduction_commit(root: Path, row: dict) -> str:
    """Check the first commit that contains the actual SHA-chained forecast."""
    target = row["event_sha256"]
    path = FORECAST_PATH.as_posix()
    commits = _git(root, "log", "--format=%H", "HEAD", "--", path).splitlines()
    earliest = None
    for sha in reversed(commits):
        if not COMMIT.fullmatch(sha):
            raise ValueError("invalid Git history")
        text = _git(root, "show", f"{sha}:{path}")
        lines = [json.loads(x) for x in text.splitlines()]
        if any(x.get("event_sha256") == target and x == row for x in lines):
            earliest = sha
            break
    if not earliest:
        raise ValueError("forecast was never committed to public Git history")
    return earliest


def _github_runs(commit: str, *, fetch=None) -> list[dict]:
    if not COMMIT.fullmatch(commit):
        raise ValueError("invalid GitHub commit reference")
    query = urlencode({"head_sha": commit, "per_page": 100})
    if fetch is None:
        headers = {"Accept": "application/vnd.github+json",
                   "User-Agent": "numbers4-prospective-proof/1"}
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        # Fixed GitHub API endpoint, no user-supplied arbitrary redirect host.
        with urlopen(Request(API + "?" + query, headers=headers), timeout=12) as rsp:
            data = json.load(rsp)
    else:
        data = fetch(commit)
    if not isinstance(data, dict) or not isinstance(data.get("workflow_runs"), list):
        raise ValueError("GitHub API did not provide workflow runs")
    return data["workflow_runs"]


def verify_and_record(root: Path, *, fetch=None) -> dict:
    """Record independently verified push-run witnesses; append only.

    On an outage or missing match, do NOT generate any witness. The next run
    can retry. The appended result is an audit cache of a verified API event,
    not cryptographic proof against a malicious repository owner.
    """
    forecasts = load(root / FORECAST_PATH)
    existing = _validated_witnesses(root, forecasts)
    new = 0
    pending = []
    for row in forecasts:
        if row["round"] in existing:
            continue
        commit = _find_introduction_commit(root, row)
        accepted = []
        for run in _github_runs(commit, fetch=fetch):
            if not isinstance(run, dict):
                continue
            if (run.get("event") not in {"push", "workflow_dispatch"} or
                    run.get("head_sha") != commit or
                    run.get("head_branch") != "main" or
                    run.get("name") != "Numbers4 CI" or
                    type(run.get("id")) is not int):
                continue
            try:
                created = _time(run["created_at"])
                issued = _time(row["issued_at_jst"])
                deadline = _time(row["freeze_deadline_jst"])
            except (ValueError, TypeError, KeyError):
                continue
            if not issued <= created < deadline:
                continue
            accepted.append((created, run["id"]))
        if not accepted:
            pending.append(row["round"])
            continue
        when, run_id = min(accepted)
        append(root / WITNESS_PATH, {
            "version": VERSION, "round": row["round"],
            "forecast_event_sha256": row["event_sha256"],
            "github_repo": PUBLIC_REPO, "github_event": (
                "workflow_dispatch" if any(x.get("event") == "workflow_dispatch"
                and x.get("id") == run_id for x in _github_runs(commit, fetch=fetch))
                else "push"),
            "github_workflow": "Numbers4 CI",
            "github_head_sha": commit, "github_run_id": run_id,
            "github_run_created_at": when.astimezone(timezone.utc).isoformat(),
            "github_server_verified": True,
            "authority_scope": "public_push_run_created_before_draw_no_digital_signature",
        })
        new += 1
    return {
        "status": "github_publication_witness_attempted",
        "new_verified_witnesses": new,
        "total_verified_witnesses": len(existing) + new,
        "unwitnessed_rounds": pending,
        "independent_from_local_forecast_timestamp": True,
        "digital_signature": False,
        "eligible_for_automatic_purchase": False,
    }
