"""Automated secondary-mirror research updates, NEVER official bank verification.

Two public GitHub mirrors are checked at immutable commit refs. They may have a
shared upstream; matching numbers does NOT imply independent-source evidence.
If either mirror fails or a historical entry changes, the existing archive
remains untouched and no predictive model is promoted.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone, timedelta, date
from hashlib import sha1, sha256
from io import BytesIO, StringIO
import json
from pathlib import Path
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

from .historical_archive import load_archive, _git_blob_sha1, VERSION as ARCHIVE_VERSION, STATUS
from .finance import PAYOUT_CSV, PAYOUT_META, VERSION as PAYOUT_VERSION, STATUS as PAYOUT_STATUS, _payout_int, load_payouts
from .box_finance import PAYOUT_CSV as BOX_CSV, PAYOUT_META as BOX_META, VERSION as BOX_VERSION, STATUS as BOX_STATUS, load_box_payouts, parse_box_prize
from .rules import four_digits

JST=timezone(timedelta(hours=9))
VERSION="numbers4-online-secondary-source-refresh-v1"
REPOS=(
    ("hazimekom", "numbers4-api", "data/numbers4_results_v2.csv"),
    ("kodai721229", "kujilab", "public/data/numbers4.json"),
)
RELATED=(
    ("mizuho_rules", "https://www.mizuhobank.co.jp/takarakuji/products/numbers/index.html"),
    ("official_n4_rules", "https://www.takarakuji-official.jp/brand/suji/lineup-numbers4/"),
    ("scoring_rule_research", "https://stat.uw.edu/research/tech-reports/strictly-proper-scoring-rules-prediction-and-estimation"),
)
MAX_BODY=1_600_000


def _host(url: str) -> str:
    u=urlparse(url)
    if (u.scheme!="https" or u.username or u.password or u.port not in (None,443)
        or u.fragment or u.hostname not in {"api.github.com", "raw.githubusercontent.com",
          "www.mizuhobank.co.jp", "www.takarakuji-official.jp", "stat.uw.edu"}):
        raise ValueError("untrusted online evidence URL")
    return u.hostname


def read_url(url: str) -> bytes:
    host=_host(url)
    request=urllib.request.Request(url, headers={"User-Agent":"NUMBERS4_AI_AGENT/0.3 read-only-research-audit", "Accept":"*/*"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            if _host(response.geturl())!=host or response.status!=200:
                raise ValueError("online source redirected or not successful")
            raw=response.read(MAX_BODY+1)
            if len(raw)>MAX_BODY:
                raise ValueError("online evidence exceeds 1.6MB limit")
            return raw
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ConnectionError("online source unavailable") from e


def parse_csv(raw: bytes) -> list[dict]:
    try:
        reader=csv.DictReader(StringIO(raw.decode("utf-8-sig")))
        if not {"draw_no","draw_date","winning_number"}.issubset(reader.fieldnames or []):
            raise ValueError("missing secondary source CSV headers")
        out=[]
        for r in reader:
            number=four_digits(r["winning_number"])
            if "digit1" in r and "".join(r[k] for k in ("digit1","digit2","digit3","digit4"))!=number:
                raise ValueError("source digit columns mismatch")
            out.append({"round":int(r["draw_no"]),"draw_date":r["draw_date"],"winning_number":number})
        return out
    except (UnicodeError,KeyError,TypeError) as e:
        raise ValueError("secondary source CSV malformed") from e


def parse_json(raw: bytes) -> list[tuple[int,str]]:
    try:
        parsed=json.loads(raw)
        if not isinstance(parsed,list):raise ValueError("secondary JSON is not a list")
        out=[]
        for record in parsed:
            if not isinstance(record,list) or len(record)!=2 or type(record[0]) is not int:
                raise ValueError("secondary JSON record malformed")
            out.append((record[0],four_digits(record[1])))
        return out
    except (ValueError,TypeError,UnicodeError) as e:
        raise ValueError("secondary source JSON invalid") from e


def validate_pair(rows: list[dict], corroborator: list[tuple[int,str]], as_of: date) -> list[dict]:
    if not rows or not corroborator or len(rows)!=len(corroborator):
        raise ValueError("secondary mirrors missing or disagree on coverage")
    prev_date=None
    if len(rows)>20000:raise ValueError("unreasonably large secondary history")
    for idx,(r,pair) in enumerate(zip(rows,corroborator),1):
        d=date.fromisoformat(r["draw_date"])
        if (r["round"]!=idx or pair!=(idx,r["winning_number"]) or
                r["draw_date"]!=d.isoformat() or d>as_of or
                (prev_date is not None and d<=prev_date) or d.weekday()>4):
            raise ValueError("secondary mirrors disagree or have missing/invalid draw rows")
        prev_date=d
    return rows


def refresh(root: Path, *, now: datetime|None=None, fetch=read_url) -> dict:
    now=(now or datetime.now(JST)).astimezone(JST)
    old,meta=load_archive(root)
    result={"version":VERSION,"checked_at_jst":now.isoformat(timespec="seconds"),
            "status":"pending", "previous_rows":len(old),"new_rows":0,
            "secondary_source_independence_proven":False,
            "official_bank_verified":False,"issued_forecast_grading_authorized":False,
            "automatic_model_promotion":False,"sources":[],"errors":[]}
    sources=[]; data=[]
    try:
        for owner,name,path in REPOS:
            api=f"https://api.github.com/repos/{owner}/{name}/commits/main"
            metadata=json.loads(fetch(api))
            rev=metadata.get("sha")
            if not isinstance(rev,str) or not re.fullmatch("[0-9a-f]{40}",rev):
                raise ValueError("repository has no immutable commit SHA")
            raw_url=f"https://raw.githubusercontent.com/{owner}/{name}/{rev}/{path}"
            raw=fetch(raw_url)
            sources.append({"url":f"https://github.com/{owner}/{name}/blob/{rev}/{path}",
                            "commit_sha":rev,"blob_sha":_git_blob_sha1(raw),
                            "sha256":sha256(raw).hexdigest()})
            data.append(raw)
        rows=validate_pair(parse_csv(data[0]),parse_json(data[1]),now.date())
        # Payouts come from one secondary publisher only. The second mirror
        # corroborates winning digits, never award amounts.
        previous_payouts=[]
        payout_enabled=(root/PAYOUT_CSV).exists() or (root/PAYOUT_META).exists()
        if payout_enabled:
            previous_payouts,_=load_payouts(root,old)
            publisher_payout_rows=list(csv.DictReader(StringIO(data[0].decode("utf-8-sig"))))
            if len(publisher_payout_rows)!=len(rows):
                raise ValueError("secondary payout rows do not match draw coverage")
            fresh_payouts=[]
            for idx,(r,src) in enumerate(zip(rows,publisher_payout_rows),1):
                if (src.get("draw_no")!=str(idx) or src.get("draw_date")!=r["draw_date"] or
                    four_digits(src.get("winning_number"))!=r["winning_number"]):
                    raise ValueError("payout record does not match independently corroborated draw")
                fresh_payouts.append(_payout_int(src.get("straight_payout")))
            if fresh_payouts[:len(previous_payouts)]!=previous_payouts:
                raise ValueError("historical secondary payout was rewritten; refuse update")
        box_enabled=(root/BOX_CSV).exists() or (root/BOX_META).exists()
        if box_enabled:
            old_box,_=load_box_payouts(root,old)
            publisher_box_rows=list(csv.DictReader(StringIO(data[0].decode("utf-8-sig"))))
            if len(publisher_box_rows)!=len(rows):
                raise ValueError("secondary BOX payout rows do not match draw coverage")
            new_box=[]
            for idx,(r,src) in enumerate(zip(rows,publisher_box_rows),1):
                if (src.get("draw_no")!=str(idx) or
                    src.get("draw_date")!=r["draw_date"] or
                    src.get("winning_number")!=r["winning_number"]):
                    raise ValueError("BOX payout differs from secondary draw outcome")
                new_box.append(parse_box_prize(src.get("box_payout"),r["winning_number"]))
            if new_box[:len(old_box)]!=old_box:
                raise ValueError("secondary BOX payout history was retroactively revised")
        if len(rows)<len(old) or rows[:len(old)]!=old:
            raise ValueError("source history was rewritten, shortened, or now inconsistent with stored archive")
        result["sources"]=sources
        result["current_rows"]=len(rows)
        result["new_rows"]=len(rows)-len(old)
        result["status"]="validated_no_new_draws"
        if len(rows)>len(old):
            # Append-only semantics: never replace any pre-existing draw.
            text="round,draw_date,winning_number\n"+"".join(
                f"{r['round']},{r['draw_date']},{r['winning_number']}\n" for r in rows)
            csv_bytes=text.encode("utf-8")
            provenance={
                "version":ARCHIVE_VERSION, "status":STATUS,
                "record_count":len(rows), "first_round":1,"last_round":len(rows),
                "first_draw_date":rows[0]["draw_date"],
                "last_draw_date":rows[-1]["draw_date"],
                "latest_number":rows[-1]["winning_number"],
                "git_blob_sha1":_git_blob_sha1(csv_bytes),
                "officially_verified":False,"forecast_grading_authorized":False,
                "source_independence_not_established":True,
                "cross_source_number_mismatches":0,
                "evidence_scope":"two_public_GitHub_archives_exact_numbers_agree_bank_first_party_not_verified_same_upstream_possible",
                "imported_as_of_jst_date":now.date().isoformat(),
                "public_source_revisions":[{**{k:v for k,v in src.items() if k in ("url","commit_sha","blob_sha")},
                                            "provides":"round_date_result" if i==0 else "round_result"}
                                           for i,src in enumerate(sources)]
            }
            csv_file=root/"data/historical_results.csv"
            meta_file=root/"data/historical_archive_provenance.json"
            csv_file.parent.mkdir(parents=True,exist_ok=True)
            csv_file.write_bytes(csv_bytes)
            meta_file.write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            if payout_enabled:
                # Append only after verifying the complete historical prefix.
                payout_text="round,draw_date,winning_number,straight_payout_yen\n"+"".join(
                    f"{r['round']},{r['draw_date']},{r['winning_number']},{p}\n"
                    for r,p in zip(rows,fresh_payouts))
                payout_raw=payout_text.encode("utf-8")
                pay_meta={
                    "version":PAYOUT_VERSION, "status":PAYOUT_STATUS,
                    "git_blob_sha1":_git_blob_sha1(payout_raw),
                    "record_count":len(rows),"first_round":1,"last_round":len(rows),
                    "first_draw_date":rows[0]["draw_date"],
                    "last_draw_date":rows[-1]["draw_date"],
                    "first_number":rows[0]["winning_number"],
                    "latest_number":rows[-1]["winning_number"],
                    "ticket_price_yen":200,
                    "bank_primary_payouts_verified":False,
                    "secondary_payout_independence_proven":False,
                    "forecast_grading_authorized":False,
                    "actual_purchase_records_present":False,
                    "source":{"url":sources[0]["url"],"commit_sha":sources[0]["commit_sha"],
                              "blob_sha":sources[0]["blob_sha"]},
                    "bank_primary_url":"https://www.mizuhobank.co.jp/takarakuji/check/numbers/numbers4/index.html",
                    "interpretation":"Historical single-publisher straight payouts, hypothetical research P/L only.",
                }
                (root/PAYOUT_CSV).write_bytes(payout_raw)
                (root/PAYOUT_META).write_text(json.dumps(pay_meta,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
                validated,_=load_payouts(root,rows)
                if validated!=fresh_payouts:
                    raise ValueError("new historical payout ledger postwrite verification failed")
            if box_enabled:
                box_text="round,draw_date,winning_number,box_payout_yen\n"+"".join(
                    f"{r['round']},{r['draw_date']},{r['winning_number']},{'' if p is None else p}\n"
                    for r,p in zip(rows,new_box))
                box_raw=box_text.encode("utf-8")
                excluded=sum(p is None for p in new_box)
                box_provenance={
                    "version":BOX_VERSION,"status":BOX_STATUS,
                    "git_blob_sha1":_git_blob_sha1(box_raw),
                    "record_count":len(rows),"first_round":1,"last_round":len(rows),
                    "first_draw_date":rows[0]["draw_date"],
                    "last_draw_date":rows[-1]["draw_date"],
                    "first_number":rows[0]["winning_number"],
                    "latest_number":rows[-1]["winning_number"],
                    "eligible_box_draws":len(rows)-excluded,
                    "ineligible_box_draws":excluded,
                    "ticket_price_yen":200,
                    "bank_primary_payouts_verified":False,
                    "secondary_payout_independence_proven":False,
                    "forecast_grading_authorized":False,
                    "actual_purchase_records_present":False,
                    "source":{"url":sources[0]["url"],"commit_sha":sources[0]["commit_sha"],
                              "blob_sha":sources[0]["blob_sha"]},
                    "other_source_number_crosscheck":sources[1]["url"],
                    "official_rule_url":"https://www.mizuhobank.co.jp/takarakuji/products/numbers/index.html",
                    "interpretation":"Historical secondhand BOX payouts; blank means all four digits same and BOX application ineligible. No purchases."
                }
                (root/BOX_CSV).write_bytes(box_raw)
                (root/BOX_META).write_text(json.dumps(box_provenance,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
                valid_box,_=load_box_payouts(root,rows)
                if valid_box!=new_box:
                    raise ValueError("post-write secondary BOX payout validation failed")
            if len(load_archive(root)[0])!=len(rows):
                raise ValueError("historical archive failed post-commit integrity check")
            result["status"]="appended_secondary_history_not_officially_verified"
    except (ConnectionError,urllib.error.URLError,TimeoutError) as e:
        result["status"]="network_unavailable_old_archive_preserved"
        result["errors"].append(str(e))
    return result


def audit_related(now: datetime|None=None, *, fetch=read_url) -> dict:
    """Search-like bounded refresh of known authoritative references; no code execution.

    A successful HTTP fetch only verifies accessibility and response hashes;
    it does not imply the remote source endorsed this model or algorithm.
    """
    now=(now or datetime.now(JST)).astimezone(JST)
    records=[]
    for label,url in RELATED:
        try:
            raw=fetch(url)
            records.append({"topic":label,"url":url,"status":"fetched_read_only_unreviewed",
                            "response_sha256":sha256(raw).hexdigest(),"size_bytes":len(raw)})
        except (ConnectionError,ValueError,UnicodeError) as e:
            records.append({"topic":label,"url":url,"status":"unavailable_or_unverified",
                            "reason":str(e)[:90]})
    return {"version":"numbers4-related-sources-online-audit-v1",
            "checked_at_jst":now.isoformat(timespec="seconds"),
            "topics":records,"paper_relevance_confirmed":False,
            "automatic_external_code_execution":False,
            "lottery_predictive_improvement_confirmed":False}
