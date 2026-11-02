"""Numbers4 historical prequential replay + bounded research-only online adaptation.

Every reconstructed prediction for round r is computed from rows [1,r), never
from round r or later.  This is NOT an actual pre-issued forecast ledger.
"""
from __future__ import annotations

import csv
from collections import Counter, deque
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from heapq import heappop, heappush
from math import exp, isfinite, log, prod
from pathlib import Path
import json
import random
from typing import Iterable

from .historical_archive import archive_summary, load_archive
from .rules import four_digits

VERSION = "numbers4-prequential-online-replay-v1"
JST = timezone(timedelta(hours=9))
MODELS = (("positional_60_alpha10", 60, 10),
          ("positional_250_alpha5", 250, 5),
          ("positional_1000_alpha20", 1000, 20))
FIELDS = ("round", "draw_date", "actual", "data_cutoff_round", "selected_model",
          "selected_numbers", "selected_hit", "uniform_numbers", "uniform_hit",
          "selected_log_edge", "selected_brier_edge", "positional_60_log_edge",
          "positional_250_log_edge", "positional_1000_log_edge", "source_status")


def uniform_numbers(round_number: int) -> list[str]:
    """Independent reproducible reference; NEVER chosen using future outcomes."""
    seed = int.from_bytes(sha256(f"{VERSION}:uniform:{round_number}".encode()).digest()[:8], "big")
    return [f"{n:04d}" for n in random.Random(seed).sample(range(10000), 5)]


def positional_probs(history: Iterable[str], alpha: int) -> list[list[float]]:
    if type(alpha) is not int or alpha < 1:
        raise ValueError("alpha must be positive integer")
    values = list(history)
    if not values:
        return [[.1]*10 for _ in range(4)]
    result = []
    for pos in range(4):
        counts = Counter(number[pos] for number in values)
        result.append([(counts[str(n)] + alpha) / (len(values)+alpha*10) for n in range(10)])
    return result


def best_five(q: list[list[float]]) -> list[str]:
    """Top-5 highest probability numbers via exact top-K product search.

    Each marginal list is ordered by descending probability then ascending
    digit, so any as-yet-unseen candidate has a predecessor with at least as
    high probability. The heap extracts five optimal tuples in O(5*4 log 20)
    rather than re-sorting all 10,000 numbers on every round.
    """
    if len(q)!=4 or any(len(x)!=10 for x in q):
        raise ValueError("malformed 4x10 categorical distribution")
    if any(any(not isfinite(x) or x <= 0 for x in p) or abs(sum(p)-1)>1e-9 for p in q):
        raise ValueError("invalid probability vector")
    orders = [sorted(range(10), key=lambda d: (-line[d], d)) for line in q]
    initial=(0,0,0,0)
    def proposal(index: tuple[int,int,int,int]) -> tuple[float,str]:
        digits=tuple(orders[i][v] for i,v in enumerate(index))
        number="".join(str(d) for d in digits)
        prob=prod(q[i][d] for i,d in enumerate(digits))
        return prob,number
    prob,number=proposal(initial)
    queue=[(-prob, number, initial)]
    seen={initial}
    output=[]
    while len(output)<5:
        _,number,index=heappop(queue)
        output.append(number)
        for j in range(4):
            if index[j]>=9:
                continue
            nxt=tuple(index[k]+(1 if j==k else 0) for k in range(4))
            if nxt not in seen:
                seen.add(nxt)
                p,n=proposal(nxt)
                heappush(queue,(-p,n,nxt))
    return output


def grade_prob(q: list[list[float]], actual: str) -> tuple[float,float]:
    n=four_digits(actual)
    p=prod(q[pos][int(d)] for pos,d in enumerate(n))
    norm2=prod(sum(x*x for x in v) for v in q)
    return log(p / .0001), (2*p - norm2 - .0001)


def replay(rows: list[dict]) -> tuple[dict,list[dict]]:
    if len(rows)<2 or rows[0]["round"] != 1:
        raise ValueError("replay requires original round 1 and a subsequent round")
    previous_date=None
    for idx,row in enumerate(rows,1):
        if type(row.get("round")) is not int or row["round"] != idx:
            raise ValueError("history must be complete and sequential from round 1")
        if not isinstance(row.get("draw_date"),str) or (previous_date is not None and row["draw_date"] <= previous_date):
            raise ValueError("draw dates must strictly increase")
        four_digits(row["winning_number"])
        previous_date=row["draw_date"]
    windows={name:deque(maxlen=length) for name,length,_ in MODELS}
    model_scores={name:0.0 for name,_,_ in MODELS}
    score_trace={name:[] for name,_,_ in MODELS}
    selected_hits=reference_hits=0
    selected_scores=[]; selected_brier=[]
    selected_models=Counter()
    grades=[]
    for index,row in enumerate(rows):
        if index:
            actual=row["winning_number"]
            target_round=row["round"]
            # All weights here were updated after earlier rounds ONLY.
            selection="uniform"
            if index>=100:
                eligible=[name for name,_,_ in MODELS if model_scores[name]>0.5 and
                          sum(score_trace[name][-90:])/min(len(score_trace[name]),90)>0]
                if eligible:
                    selection=max(eligible,key=lambda x:(model_scores[x],x))
            prediction=uniform_numbers(target_round)
            baseline=prediction.copy()
            model_preds={}
            current_grades={}
            for name,_,alpha in MODELS:
                q=positional_probs(windows[name], alpha)
                model_preds[name]=best_five(q)
                current_grades[name]=grade_prob(q,actual)
            if selection!="uniform":
                prediction=model_preds[selection]
                logedge,brier=current_grades[selection]
            else:
                logedge,brier=0.0,0.0
            selected_hits+=int(actual in prediction)
            reference_hits+=int(actual in baseline)
            selected_models[selection]+=1
            selected_scores.append(logedge);selected_brier.append(brier)
            grades.append({
                "round":target_round,"draw_date":row["draw_date"],"actual":actual,
                "data_cutoff_round":target_round-1,"selected_model":selection,
                "selected_numbers":" ".join(prediction),"selected_hit":int(actual in prediction),
                "uniform_numbers":" ".join(baseline),"uniform_hit":int(actual in baseline),
                "selected_log_edge":round(logedge,9),"selected_brier_edge":round(brier,12),
                "positional_60_log_edge":round(current_grades[MODELS[0][0]][0],9),
                "positional_250_log_edge":round(current_grades[MODELS[1][0]][0],9),
                "positional_1000_log_edge":round(current_grades[MODELS[2][0]][0],9),
                "source_status":"secondary_public_mirrors_agree_not_officially_verified",
            })
            # Updates occur AFTER predicting and grading the current outcome.
            for name,_,_ in MODELS:
                edge=current_grades[name][0]
                score_trace[name].append(edge)
                # bounded EWMA, a research-policy choice not skill evidence.
                model_scores[name]=.99*model_scores[name]+.2*max(-1.0,min(1.0,edge))
        for name,_,_ in MODELS:
            windows[name].append(row["winning_number"])
    n=len(grades)
    # Latest model candidate is recomputed only from results already in the
    # archive. Its target date is UNKNOWN until the official schedule is
    # checked. It is NEVER an issued, purchased or verified forecast.
    if len(rows)>=100:
        eligible=[name for name,_,_ in MODELS if model_scores[name]>.5 and
                  sum(score_trace[name][-90:])/min(len(score_trace[name]),90)>0]
    else:
        eligible=[]
    next_model=max(eligible,key=lambda x:(model_scores[x],x)) if eligible else "uniform"
    next_n=rows[-1]["round"]+1
    next_numbers=(uniform_numbers(next_n) if next_model=="uniform"
                  else best_five(positional_probs(windows[next_model],
                                     next(v[2] for v in MODELS if v[0]==next_model))))
    result={
        "next_research_candidate":{"target_round":next_n,"data_cutoff_round":rows[-1]["round"],
          "model":next_model,"numbers":next_numbers,"draw_date":None,
          "status":"research_only_not_issued_not_purchased", "accuracy_claim":False},
        "version":VERSION,"status":"historical_walk_forward_reconstruction_only",
        "rounds":len(rows),"first_training_round":1,
        "first_evaluated_round":2,"last_evaluated_round":rows[-1]["round"],
        "last_evaluated_date":rows[-1]["draw_date"],"evaluated_draws":n,
        "training_from_prior_draws_only":True,"historical_frozen_forecasts":False,
        "forecast_grading_authorized":False,"officially_verified":False,
        "selected_top5_straight_hits":selected_hits,
        "uniform_reference_top5_straight_hits":reference_hits,
        "uniform_theoretical_top5_expected_hits":round(n*5/10000,6),
        "selected_mean_log_score_edge_vs_uniform":round(sum(selected_scores)/n,9),
        "selected_mean_brier_improvement_vs_uniform":round(sum(selected_brier)/n,12),
        "research_model_selection_rounds":dict(selected_models),
        "candidate_models":[name for name,_,_ in MODELS],
        "policy":"bounded_previous_100_round_guard_90_round_positive_edge_EWMA_no_production_release",
        "learning_rate":.2,"weight_decay":.99,
        "genuine_prospective_verified_draws":0,
        "prediction_skill_confirmed":False,"production_model_changed":False,
        "actual_purchase_profit_yen":None,
        "interpretation":"Post-hoc reconstruction with strict past-only updates; never a real predraw issuance or prospective proof",
    }
    return result,grades


def write_replay(root: Path, *, report_path: Path=Path("research/online_replay.json"),
                 csv_path: Path=Path("research/online_round_predictions.csv")) -> dict:
    rows,meta=load_archive(root)
    if not rows or meta.get("officially_verified") is not False:
        raise ValueError("strict secondary-source archive required; no prospective data mixing")
    summary,grades=replay(rows)
    summary["archive_git_blob_sha1"]=meta["git_blob_sha1"]
    summary["archive_latest_round"]=meta["last_round"]
    summary["generated_at_jst"]=datetime.now(JST).isoformat(timespec="seconds")
    report_path=root/report_path
    csv_path=root/csv_path
    report_path.parent.mkdir(parents=True,exist_ok=True)
    csv_path.parent.mkdir(parents=True,exist_ok=True)
    with csv_path.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS)
        writer.writeheader();writer.writerows(grades)
    summary["round_predictions_sha256"]=sha256(csv_path.read_bytes()).hexdigest()
    report_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    return summary
