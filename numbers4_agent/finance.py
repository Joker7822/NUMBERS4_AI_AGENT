"""Hypothetical straight-ticket finance based on historical reconstruction only.

Neither a purchase ledger nor official bank payout verification.
"""
from __future__ import annotations

import csv
from datetime import date
from hashlib import sha1
import io
import json
from pathlib import Path
import re

from .rules import four_digits

PAYOUT_CSV=Path("data/secondary_straight_payouts.csv")
PAYOUT_META=Path("data/secondary_straight_payouts_provenance.json")
VERSION="numbers4-secondary-straight-payouts-v1"
STATUS="single_secondary_publisher_not_bank_verified"
TICKET_PRICE_YEN=200
TICKETS_PER_ROUND=5


def git_blob_sha1(data: bytes) -> str:
    return sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()


def _payout_int(raw: object) -> int:
    if not isinstance(raw,str) or not re.fullmatch(r"(?:0|[1-9]\d*)",raw):
        raise ValueError("invalid historical straight payout")
    value=int(raw)
    if value<=0 or value>20_000_000:
        raise ValueError("historical straight payout outside accepted range")
    return value


def load_payouts(root: Path, archive_rows: list[dict]) -> tuple[list[int], dict]:
    csv_path=root/PAYOUT_CSV
    meta_path=root/PAYOUT_META
    if not csv_path.exists() or not meta_path.exists():
        raise ValueError("full historical straight payout evidence is missing")
    raw=csv_path.read_bytes()
    meta=json.loads(meta_path.read_text(encoding="utf-8"))
    if (meta.get("version")!=VERSION or meta.get("status")!=STATUS or
        meta.get("git_blob_sha1")!=git_blob_sha1(raw) or
        meta.get("record_count")!=len(archive_rows) or
        meta.get("first_round")!=1 or meta.get("last_round")!=len(archive_rows) or
        meta.get("ticket_price_yen")!=TICKET_PRICE_YEN or
        meta.get("bank_primary_payouts_verified") is not False or
        meta.get("secondary_payout_independence_proven") is not False or
        meta.get("forecast_grading_authorized") is not False or
        meta.get("actual_purchase_records_present") is not False):
        raise ValueError("historical payout evidence lacks safe provenance")
    source=meta.get("source")
    if (not isinstance(source,dict) or
        not isinstance(source.get("url"),str) or
        not source["url"].startswith("https://github.com/hazimekom/numbers4-api/blob/") or
        any(not isinstance(source.get(k),str) or
            re.fullmatch(r"[0-9a-f]{40}",source[k]) is None
            for k in ("commit_sha","blob_sha"))):
        raise ValueError("historical payout upstream provenance missing")
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if reader.fieldnames!=["round","draw_date","winning_number","straight_payout_yen"]:
        raise ValueError("historical payout columns changed")
    payout=[]
    for row in reader:
        i=len(payout)
        if i>=len(archive_rows):
            raise ValueError("payout rows exceed history")
        historical=archive_rows[i]
        if (row["round"]!=str(i+1) or
            row["draw_date"]!=historical["draw_date"] or
            four_digits(row["winning_number"])!=historical["winning_number"]):
            raise ValueError("payout rows do not match historical draw archive")
        payout.append(_payout_int(row["straight_payout_yen"]))
    if len(payout)!=len(archive_rows):
        raise ValueError("payout history is incomplete")
    if (meta.get("first_draw_date")!=archive_rows[0]["draw_date"] or
        meta.get("last_draw_date")!=archive_rows[-1]["draw_date"] or
        meta.get("first_number")!=archive_rows[0]["winning_number"] or
        meta.get("latest_number")!=archive_rows[-1]["winning_number"]):
        raise ValueError("payout endpoints differ from history")
    return payout,meta


def summarize_reconstruction(grades: list[dict], archive_rows: list[dict],
                             payouts: list[int]) -> dict:
    """Only exact 5-ticket STRAIGHT matches, scored against prior-only replay."""
    if len(archive_rows)<2 or len(payouts)!=len(archive_rows) or len(grades)!=len(archive_rows)-1:
        raise ValueError("cannot evaluate incomplete hypothetical portfolio")
    winners=[]
    winning_total=0
    baseline_total=0
    baseline_hits=0
    for i,grade in enumerate(grades,1):
        history=archive_rows[i]
        nums=grade.get("selected_numbers")
        baseline=grade.get("uniform_numbers")
        if (grade.get("round")!=i+1 or grade.get("draw_date")!=history["draw_date"] or
            grade.get("actual")!=history["winning_number"] or
            grade.get("data_cutoff_round")!=i or
            not isinstance(nums,str) or not isinstance(baseline,str)):
            raise ValueError("replayed grade does not match historical archive")
        selected=nums.split()
        uniform=baseline.split()
        if (len(selected)!=TICKETS_PER_ROUND or
            len(set(selected))!=TICKETS_PER_ROUND or
            len(uniform)!=TICKETS_PER_ROUND or
            len(set(uniform))!=TICKETS_PER_ROUND):
            raise ValueError("invalid number of hypothetical tickets")
        for number in selected+uniform:
            four_digits(number)
        winning=history["winning_number"]
        match=winning in selected
        ref_match=winning in uniform
        if (grade.get("selected_hit")!=int(match) or grade.get("uniform_hit")!=int(ref_match)):
            raise ValueError("reported win count does not match original candidate set")
        if match:
            award=payouts[i]
            winning_total+=award
            winners.append({
                "round":i+1,"draw_date":history["draw_date"],
                "winning_number":winning,"matched_prediction":winning,
                "ticket_position":selected.index(winning)+1,
                "selected_model":grade["selected_model"],
                "straight_payout_yen":award,
                "hypothetical_ticket_cost_yen":TICKETS_PER_ROUND*TICKET_PRICE_YEN,
                "status":"retrospective_simulated_hit_not_actual_purchase",
            })
        if ref_match:
            baseline_hits+=1
            baseline_total+=payouts[i]
    evaluated=len(grades)
    total_cost=evaluated*TICKETS_PER_ROUND*TICKET_PRICE_YEN
    return {
        "version":"numbers4-retrospective-straight-five-finance-v1",
        "status":"historical_simulation_only_not_actual_purchase",
        "ticket_type":"straight","tickets_per_draw":TICKETS_PER_ROUND,
        "ticket_unit_cost_yen":TICKET_PRICE_YEN,
        "evaluated_rounds":evaluated,
        "first_evaluated_round":2,"last_evaluated_round":archive_rows[-1]["round"],
        "historical_winning_draws":len(winners),
        "simulated_ticket_cost_yen":total_cost,
        "simulated_payout_yen":winning_total,
        "simulated_net_yen":winning_total-total_cost,
        "simulated_roi_percent":round(100*(winning_total-total_cost)/total_cost,4),
        "baseline_winning_draws":baseline_hits,
        "baseline_simulated_payout_yen":baseline_total,
        "baseline_simulated_net_yen":baseline_total-total_cost,
        "winning_rounds":winners,
        "payout_git_blob_sha1":None,
        "payout_source_status":STATUS,
        "bank_primary_payouts_verified":False,
        "actual_purchase_records_present":False,
        "actual_spend_yen":None,
        "actual_income_yen":None,
        "actual_profit_yen":None,
        "production_promotion_authorized":False,
        "interpretation":"Counterfactual research: 5 distinct straight entries at 200 yen each, every draw from 2 onward. Only historical payouts from a single secondary publisher; no actual ticket purchases or verified income."
    }
