"""Unified read-only research evidence audit, not a ticket decision engine."""
from __future__ import annotations

from pathlib import Path

from . import box_calibration, cashflow_risk, ensemble_audit, payout_research, return_audit
from .automatic_learning import assess as assess_prospective

VERSION = "numbers4-integrated-evidence-audit-v1"
AUDITS = {
    "returns": (return_audit.VERSION, "last_evaluated_round", "last_evaluated_date"),
    "payouts": (payout_research.VERSION, "last_round", "last_draw_date"),
    "box": (box_calibration.VERSION, "last_round", "last_draw_date"),
    "ensemble": (ensemble_audit.VERSION, "last_round", "last_draw_date"),
    "cashflow": (cashflow_risk.VERSION, "last_evaluated_round", "last_evaluated_date"),
}
PAYOUT_AUDITS = ("returns", "payouts", "cashflow")


def _require_same(values: list, label: str):
    if not values or values[0] is None or any(x != values[0] for x in values):
        raise ValueError(f"inconsistent {label} across research audits")
    return values[0]


def integrate(reports: dict, prospective: dict) -> dict:
    """Reject inconsistent provenance and unsafe claims; never promote a model."""
    if set(reports) != set(AUDITS):
        raise ValueError("missing or unexpected research audit")
    rounds, dates, hashes = [], [], []
    for name, (version, round_key, date_key) in AUDITS.items():
        report = reports[name]
        if report.get("version") != version:
            raise ValueError(f"unexpected audit version: {name}")
        if (report.get("actual_purchase") is not False
                or report.get("prospective_skill_confirmed") is not False
                or report.get("production_promotion_authorized") is not False
                or report.get("purchase_decision") != "SKIP"):
            raise ValueError(f"unsafe research authority claim: {name}")
        rounds.append(report.get(round_key))
        dates.append(report.get(date_key))
        hashes.append(report.get("archive_git_blob_sha1"))
    last_round = _require_same(rounds, "last draw")
    last_date = _require_same(dates, "last date")
    archive_hash = _require_same(hashes, "archive provenance")
    payout_hashes = {key: _require_same([reports[n].get(key) for n in PAYOUT_AUDITS], key)
                     for key in ("straight_payout_git_blob_sha1", "box_payout_git_blob_sha1")}
    if (prospective.get("secondary_historical_training_authorized") is not False
            or prospective.get("purchases_automated") is not False):
        raise ValueError("unexpected prospective evidence policy")
    if (type(prospective.get("eligible_prospective_draws")) is not int
            or type(prospective.get("required_prospective_draws")) is not int
            or prospective["eligible_prospective_draws"] < 0
            or prospective["required_prospective_draws"] <= 0):
        raise ValueError("invalid prospective evidence counts")
    blockers = ["official_payout_provenance_not_established",
                "positive_expected_value_not_established"]
    if prospective.get("integrity_blocker"):
        blockers.append("prospective_integrity_blocked")
    if prospective["eligible_prospective_draws"] < prospective["required_prospective_draws"]:
        blockers.append("insufficient_verified_prospective_draws")
    return {
        "version": VERSION,
        "status": "historical_research_only",
        "last_round": last_round,
        "last_draw_date": last_date,
        "archive_git_blob_sha1": archive_hash,
        **payout_hashes,
        "historical_audit_count": len(reports),
        "historical_reports": reports,
        "prospective_evidence": prospective,
        "blockers": blockers,
        "positive_expected_value_confirmed": False,
        "actual_purchase": False,
        "production_promotion_authorized": False,
        "purchase_decision": "SKIP",
        "interpretation": (
            "Different audit cohorts and BOX sampling rules must not be pooled. "
            "This report does not establish future profitability or modify the champion."
        ),
    }


def audit(root: Path, *, simulations: int = 10000, seed: int = 20261126) -> dict:
    reports = {
        "returns": return_audit.audit(root, simulations=simulations, seed=seed),
        "payouts": payout_research.audit(root),
        "box": box_calibration.audit(root),
        "ensemble": ensemble_audit.audit(root),
        "cashflow": cashflow_risk.audit(root),
    }
    return integrate(reports, assess_prospective(root))
