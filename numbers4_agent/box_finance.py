"""Research-only Numbers4 BOX regrading of prequential straight candidate sets.

Reinterprets the same five past-only forecast strings as BOX applications.
A 4-equal-digit choice is ineligible and not purchased; no replacement or
post-outcome choice is made. Permutation-equivalent applications are separate
paid tickets and, if matched, each earns the disclosed per-ticket payout.
Neither issued tickets nor actual purchases.
"""
from __future__ import annotations

import csv
from hashlib import sha1
import io
import json
from pathlib import Path
import re

from .rules import four_digits

PAYOUT_CSV=Path("data/secondary_box_payouts.csv")
PAYOUT_META=Path("data/secondary_box_payouts_provenance.json")
VERSION="numbers4-secondary-box-payouts-v1"
STATUS="single_secondary_publisher_not_bank_verified"
REPLAY_VERSION="numbers4-retrospective-box-five-finance-v1"
COST_PER_TICKET=200
ORIGINAL_CANDIDATES_PER_ROUND=5


def _git_sha(raw: bytes) -> str:
    return sha1(b"blob "+str(len(raw)).encode("ascii")+b"\0"+raw).hexdigest()


def box_valid(number: str) -> bool:
    four_digits(number)
    return len(set(number))>1


def signature(number: str) -> str:
    four_digits(number)
    return "".join(sorted(number))


def parse_box_prize(raw: object, winning_number: str) -> int | None:
    valid=box_valid(winning_number)
    if not valid:
        if raw != "":
            raise ValueError("all-equal winning number must have no box payout")
        return None
    if not isinstance(raw,str) or re.fullmatch(r"[1-9][0-9]*",raw) is None:
        raise ValueError("eligible box draw lacks published payout")
    amount=int(raw)
    if amount>20_000_000:
        raise ValueError("box payout exceeds supported cap")
    return amount


def load_box_payouts(root: Path, history: list[dict]) -> tuple[list[int | None], dict]:
    csv_file=root/PAYOUT_CSV
    meta_file=root/PAYOUT_META
    if not csv_file.is_file() or not meta_file.is_file():
        raise ValueError("complete secondary BOX payout source is missing")
    raw=csv_file.read_bytes()
    meta=json.loads(meta_file.read_text(encoding="utf-8"))
    if (meta.get("version")!=VERSION or meta.get("status")!=STATUS or
        meta.get("git_blob_sha1")!=_git_sha(raw) or
        meta.get("record_count")!=len(history) or
        meta.get("first_round")!=1 or meta.get("last_round")!=len(history) or
        meta.get("ticket_price_yen")!=COST_PER_TICKET or
        meta.get("bank_primary_payouts_verified") is not False or
        meta.get("secondary_payout_independence_proven") is not False or
        meta.get("forecast_grading_authorized") is not False or
        meta.get("actual_purchase_records_present") is not False):
        raise ValueError("unsafe or mismatched historical BOX payout evidence")
    source=meta.get("source")
    if (not isinstance(source,dict) or
        not isinstance(source.get("url"),str) or not source["url"].startswith(
            "https://github.com/hazimekom/numbers4-api/blob/") or
        any(not isinstance(source.get(k),str) or
            re.fullmatch(r"[0-9a-f]{40}",source[k]) is None
            for k in ("commit_sha","blob_sha"))):
        raise ValueError("unverifiable BOX payout source revision")
    reader=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if reader.fieldnames!=["round","draw_date","winning_number","box_payout_yen"]:
        raise ValueError("BOX payout CSV columns are unexpected")
    amounts=[]
    ineligible=0
    for r in reader:
        index=len(amounts)
        if index>=len(history):
            raise ValueError("BOX payout file has extra rounds")
        historical=history[index]
        if (r["round"]!=str(index+1) or
            r["draw_date"]!=historical["draw_date"] or
            r["winning_number"]!=historical["winning_number"]):
            raise ValueError("BOX payout does not match historical draw")
        prize=parse_box_prize(r["box_payout_yen"],r["winning_number"])
        ineligible+=prize is None
        amounts.append(prize)
    if (len(amounts)!=len(history) or
        meta.get("first_draw_date")!=history[0]["draw_date"] or
        meta.get("last_draw_date")!=history[-1]["draw_date"] or
        meta.get("first_number")!=history[0]["winning_number"] or
        meta.get("latest_number")!=history[-1]["winning_number"] or
        meta.get("eligible_box_draws")!=len(history)-ineligible or
        meta.get("ineligible_box_draws")!=ineligible):
        raise ValueError("BOX payout archive missing draws or metadata conflict")
    return amounts,meta


def simulate_box(grades: list[dict], history: list[dict], payouts: list[int | None]) -> dict:
    """Score BOX matches (any order) without altering historical forecast strings."""
    if len(history)<2 or len(payouts)!=len(history) or len(grades)!=len(history)-1:
        raise ValueError("incomplete historical BOX simulation")
    wins=[]
    bought=ref_bought=0
    skipped=ref_skipped=0
    win_tickets=ref_win_tickets=0
    awards=ref_awards=0
    for i,entry in enumerate(grades,1):
        historical=history[i]
        if (entry.get("round")!=i+1 or
            entry.get("draw_date")!=historical["draw_date"] or
            entry.get("actual")!=historical["winning_number"] or
            entry.get("data_cutoff_round")!=i):
            raise ValueError("BOX replay chronology or historical result mismatch")
        main=entry.get("selected_numbers")
        baseline=entry.get("uniform_numbers")
        if not isinstance(main,str) or not isinstance(baseline,str):
            raise ValueError("replayed five numbers absent")
        nums,refs=main.split(),baseline.split()
        if any(len(x)!=ORIGINAL_CANDIDATES_PER_ROUND or len(set(x))!=len(x) for x in (nums,refs)):
            raise ValueError("replayed ticket vector invalid")
        for x in nums+refs:
            four_digits(x)
        actual=historical["winning_number"]
        if (entry.get("selected_hit")!=int(actual in nums) or
            entry.get("uniform_hit")!=int(actual in refs)):
            raise ValueError("existing STRAIGHT replay flags are inconsistent")
        valid=[(position,num) for position,num in enumerate(nums,1) if box_valid(num)]
        valid_ref=[(position,num) for position,num in enumerate(refs,1) if box_valid(num)]
        bought+=len(valid)
        skipped+=len(nums)-len(valid)
        ref_bought+=len(valid_ref)
        ref_skipped+=len(refs)-len(valid_ref)
        prize=payouts[i]
        if box_valid(actual) != (prize is not None):
            raise ValueError("BOX eligibility and prize evidence disagree")
        matched=[{"ticket_position":position,"predicted_number":num}
                 for position,num in valid if signature(num)==signature(actual)]
        ref_matched=[(position,num) for position,num in valid_ref
                     if signature(num)==signature(actual)]
        if matched:
            if prize is None:
                raise ValueError("ineligible BOX draw reported a winner")
            win_tickets+=len(matched)
            total=len(matched)*prize
            awards+=total
            wins.append({
                "round":i+1,"draw_date":historical["draw_date"],
                "winning_number":actual,"selected_model":entry["selected_model"],
                "matched_tickets":matched,
                "winning_ticket_count":len(matched),
                "box_payout_yen_per_ticket":prize,
                "hypothetical_box_payout_yen":total,
                "status":"retrospective_simulated_box_win_not_actual_purchase",
            })
        if ref_matched:
            if prize is None:
                raise ValueError("ineligible BOX reference win")
            ref_win_tickets+=len(ref_matched)
            ref_awards+=len(ref_matched)*prize
    spend=bought*COST_PER_TICKET
    reference_spend=ref_bought*COST_PER_TICKET
    return {
        "version":REPLAY_VERSION,
        "status":"historical_simulation_only_not_actual_purchase",
        "ticket_type":"box","requested_tickets_per_round":ORIGINAL_CANDIDATES_PER_ROUND,
        "ticket_unit_cost_yen":COST_PER_TICKET,
        "evaluated_rounds":len(grades),"first_evaluated_round":2,
        "last_evaluated_round":history[-1]["round"],
        "simulated_purchased_tickets":bought,
        "excluded_ineligible_tickets":skipped,
        "historical_winning_draws":len(wins),
        "historical_winning_tickets":win_tickets,
        "simulated_ticket_cost_yen":spend,
        "simulated_payout_yen":awards,
        "simulated_net_yen":awards-spend,
        "simulated_roi_percent":round(100*(awards-spend)/spend,4) if spend else None,
        "baseline_purchased_tickets":ref_bought,
        "baseline_excluded_ineligible_tickets":ref_skipped,
        "baseline_winning_tickets":ref_win_tickets,
        "baseline_ticket_cost_yen":reference_spend,
        "baseline_simulated_payout_yen":ref_awards,
        "baseline_simulated_net_yen":ref_awards-reference_spend,
        "winning_rounds":wins,
        "payout_git_blob_sha1":None,
        "payout_source_status":STATUS,
        "bank_primary_payouts_verified":False,
        "actual_purchase_records_present":False,
        "actual_spend_yen":None,
        "actual_income_yen":None,
        "actual_profit_yen":None,
        "production_promotion_authorized":False,
        "original_predictions_unchanged":True,
        "interpretation":"Post-hoc BOX interpretation of prequential 5-ticket STRAIGHT predictions. All-equal-digit BOX choices are not bought and cost zero; no replacement tickets. Permutations purchased separately receive per-ticket prizes. Secondary publisher prizes are unverified by bank. No actual purchase."
    }
