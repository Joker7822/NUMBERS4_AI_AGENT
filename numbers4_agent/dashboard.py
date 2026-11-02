"""Safe, bounded public projection; no unregistered or unissued vectors."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import csv
import json

from .rules import four_digits
from .sources import iso_date

from .evaluation import graded_predictions, walk_forward
from .ledger import read_issued
from .sources import JST, reconcile, corroborated_draws
from .store import file_hash
from .historical_archive import archive_summary, load_archive
from .finance import load_payouts, summarize_reconstruction
from .box_finance import load_box_payouts, simulate_box
from .online_learning import VERSION as ONLINE_VERSION
from .online_ops import snapshot as operational_snapshot
from .evolution import public_status as evolution_status
from .automatic_learning import (assess as assess_auto_learning,
                                  VERSION as AUTO_VERSION)
from hashlib import sha256

VERSION = "numbers4-dashboard-v1"


def snapshot(root: Path, now: datetime | None = None) -> dict:
    now = (now or datetime.now(JST)).astimezone(JST)
    states = reconcile(root)
    trusted = corroborated_draws(root)
    archive = archive_summary(root)
    evolution = evolution_status(root, archive)
    operations = operational_snapshot(root,now)
    prospective = assess_auto_learning(root)
    champion_name = prospective["current_champion"]
    model_automation = {
        "version": AUTO_VERSION,
        "status": prospective["status"],
        "active_champion": champion_name,
        "eligible_champion": prospective["eligible_champion"],
        "feature_implemented": True,
        "protocol_sha256": prospective["protocol_sha256"],
        "officially_verified_training_rounds": prospective["verified_official_draws_available"],
        "shadow_forecasts_recorded": prospective["shadow_forecasts_recorded"],
        "pre_draw_github_witnesses": prospective["independently_witnessed_forecasts"],
        "eligible_prospective_draws": prospective["eligible_prospective_draws"],
        "required_prospective_draws": prospective["required_prospective_draws"],
        "integrity_blocker": prospective["integrity_blocker"],
        "model_assessments": prospective["model_assessments"],
        "model_code_from_search_results_executed": False,
        "unverified_secondary_training_authorized": False,
        "actual_purchase": False,
    }
    issued = read_issued(root)
    graded = graded_predictions(root)
    latest = trusted[-1] if trusted else None
    recent_issued = max(issued, key=lambda r: r["target_round"]) if issued else None
    recent_grade = graded[-1] if graded else None
    warnings = []
    if evolution["status"] == "stale_history_reanalysis":
        warnings.append("研究自己進化の第2回からの再解析が現在の二次履歴より古いため、最新の評価値を保留しています。")
    if prospective["integrity_blocker"]:
        warnings.append("将来予測の公開証拠または一次照合に不備があるため、AIの自動昇格を停止しています。")
    if prospective["verified_official_draws_available"] == 0:
        warnings.append("予測AI自動学習に使える銀行照合済み当せん結果は現在0件です。")
    conflicts = [rnd for rnd, state in states.items() if state["status"] == "source_conflict"]
    single = [rnd for rnd, state in states.items() if state["status"] == "single_source_only"]
    if conflicts:
        warnings.append("2系統の当せん結果が一致しない回があります。照合・採点しません。")
    if single:
        warnings.append("独立した2系統の登録がそろっていない回があります。")
    auto_draws = [r for r in trusted if r["status"] == "auto_verified_two_publishers"]
    if not trusted:
        warnings.append("Numbers4の2公開元照合済み結果が未登録です。公式銀行の取得に失敗した場合は採点しません。")
    else:
        age_days=(now.date()-datetime.fromisoformat(latest["draw_date"]).date()).days
        if age_days > 7:
            warnings.append("直近の登録済み結果が7日超前です。公式銀行の自動取得が停止または未反映の可能性があります。")
    if not trusted and (root / "research" / "historical_unverified.json").is_file():
        warnings.append("楽天宝くじの結果は参考情報です。銀行未照合のため、事前発行予測の正式採点には使いません。")
    if archive["status"] != "not_loaded":
        warnings.append("全回の過去履歴は二次公開リポジトリの一致記録です。銀行公式未照合のため、発行済み予測の正式採点には使いません。")
    warnings.extend(operations["warnings"])
    if not issued:
        warnings.append("事前発行した予測はありません。研究候補を発行済みとして表示しません。")
    else:
        if recent_issued["target_round"] not in {r["round"] for r in trusted}:
            warnings.append("最新の発行済み予測はまだ2ソース入力の一致結果で採点できません。")
    cache_path = root / "research" / "historical_unverified.json"
    unverified = None
    if cache_path.is_file():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        if (cache.get("version") != "numbers4-research-source-v1" or
                cache.get("verified_official") is not False or
                cache.get("publisher") != "rakuten_lottery_publication_only" or
                cache.get("rows_count") != len(cache.get("rows", []))):
            raise ValueError("unverified research source provenance is malformed")
        rows = cache["rows"]
        if rows:
            latest_unverified = max(rows, key=lambda r: r["round"])
            four_digits(latest_unverified["winning_number"])
            iso_date(latest_unverified["draw_date"])
            unverified = {
                "round": latest_unverified["round"],
                "draw_date": latest_unverified["draw_date"],
                "winning_number": latest_unverified["winning_number"],
                "status": "publisher_only_not_officially_verified",
                "source": "rakuten_lottery_publication_only",
            }
            if latest and latest["round"] == unverified["round"] and latest["winning_number"] != unverified["winning_number"]:
                raise ValueError("unverified publisher conflicts with official matched result")
    research_path = root / "research" / "historical_backtest.json"
    research = {}
    if research_path.is_file():
        report = json.loads(research_path.read_text(encoding="utf-8"))
        research = report.get("research_unverified_history", {})
        if research.get("prediction_skill_confirmed") is not False or research.get("production_promotion_allowed") is not False:
            raise ValueError("unauthorized research-to-production claim")
    replay_path=root/"research/online_replay.json"
    round_path=root/"research/online_round_predictions.csv"
    if replay_path.is_file() and round_path.is_file():
        replay=json.loads(replay_path.read_text(encoding="utf-8"))
        if (replay.get("version") not in {ONLINE_VERSION, "numbers4-prequential-online-replay-v1"} or
                replay.get("prediction_skill_confirmed") is not False or
                replay.get("forecast_grading_authorized") is not False or
                replay.get("officially_verified") is not False or
                replay.get("production_model_changed") is not False or
                replay.get("historical_frozen_forecasts") is not False):
            raise ValueError("unsafe historical online replay authority")
        fresh=(replay.get("version")==ONLINE_VERSION and replay.get("tickets_per_draw")==1 and
               archive.get("git_blob_sha1")==replay.get("archive_git_blob_sha1") and
               archive.get("last_round")==replay.get("archive_latest_round") and
               sha256(round_path.read_bytes()).hexdigest()==replay.get("round_predictions_sha256") and
               replay.get("evaluated_draws")==archive.get("record_count",0)-1 and
               replay.get("first_evaluated_round")==2)
        if fresh:
            online={key:replay.get(key) for key in (
                "status","evaluated_draws","first_evaluated_round","last_evaluated_round","tickets_per_draw",
                "selected_straight_hits","uniform_reference_straight_hits",
                "uniform_theoretical_expected_hits","selected_mean_log_score_edge_vs_uniform",
                "selected_mean_brier_improvement_vs_uniform","research_model_selection_rounds",
                "research_statistical_audit",
                "next_research_candidate","archive_git_blob_sha1","generated_at_jst")}
            audit=online["research_statistical_audit"]
            if audit is not None and (
                audit.get("scope")!="descriptive_historical_reconstruction_not_preregistered"
                or audit.get("statistical_significance_is_prospective_proof") is not False
                or not isinstance(audit.get("selected_hit_tail_probability_given_uniform_null"),(int,float))
                or not 0 <= audit["selected_hit_tail_probability_given_uniform_null"] <= 1
                or not isinstance(audit.get("nonuniform_model_selected_rounds"),int)
                or not 0 <= audit["nonuniform_model_selected_rounds"] <= online["evaluated_draws"]
            ):
                raise ValueError("unsafe historical chance benchmark")
            online.update({"prediction_skill_confirmed":False,"officially_verified":False,
                           "forecast_grading_authorized":False,"production_model_changed":False})
            finance=replay.get("retrospective_finance")
            if finance is not None:
                archive_rows,_=load_archive(root)
                payout_rows,payout_meta=load_payouts(root,archive_rows)
                with round_path.open(encoding="utf-8",newline="") as handle:
                    history=list(csv.DictReader(handle))
                for grade in history:
                    for key in ("round","data_cutoff_round","selected_hit","uniform_hit"):
                        grade[key]=int(grade[key])
                verified_sim=summarize_reconstruction(history,archive_rows,payout_rows)
                verified_sim["payout_git_blob_sha1"]=payout_meta["git_blob_sha1"]
                if verified_sim!=finance:
                    raise ValueError("simulated financial totals or winning rounds differ from source evidence")
                if (finance["historical_winning_draws"]!=online["selected_straight_hits"] or
                    finance["baseline_winning_draws"]!=online["uniform_reference_straight_hits"]):
                    raise ValueError("simulation win counts differ from replay")
                online["retrospective_finance"]=verified_sim
                box_finance=replay.get("retrospective_box_finance")
                if box_finance is not None:
                    box_payouts,box_meta=load_box_payouts(root,archive_rows)
                    box_verified=simulate_box(history,archive_rows,box_payouts)
                    box_verified["payout_git_blob_sha1"]=box_meta["git_blob_sha1"]
                    if box_verified!=box_finance:
                        raise ValueError("simulated BOX wins or finances differ from source evidence")
                    online["retrospective_box_finance"]=box_verified
                else:
                    warnings.append("ボックスの仮想収支はまだ再計算されていません。")
            else:
                warnings.append("過去の模擬収支は計算待ちです。実購入の収支は未確認です。")
        else:
            online={"status":"stale_or_mismatched_input","evaluated_draws":0,
                    "prediction_skill_confirmed":False,"officially_verified":False}
            warnings.append("第2回からの1口予測が未再計算、または現在の履歴と一致しないため、表示を保留しています。旧5口報告は歴史的参考として保持します。")
    else:
        online={"status":"not_yet_run","evaluated_draws":0,
                "prediction_skill_confirmed":False,"officially_verified":False}
    return {
        "version": VERSION, "generated_at_jst": now.isoformat(timespec="seconds"),
        "product": "Numbers4", "official_auto_fetch_enabled": True,
        "data_scope": "bank_primary_plus_rakuten_publication_only_or_manual_entry",
        "source_status": "conflict" if conflicts else "auto_verified_two_publishers" if auto_draws else "two_source_entered_consistent" if trusted else "no_corroborated_draws",
        "observed_rounds": len(states), "consistent_rounds": len(trusted),
        "auto_verified_rounds": len(auto_draws),
        "latest_consistent_draw": latest,
        "latest_unverified_draw": unverified,
        "published_forecast": ({k: recent_issued[k] for k in ("target_round", "draw_date", "mode", "numbers", "issued_at_jst", "model_version", "actual_purchase")}
                               if recent_issued else None),
        "latest_graded_issued_forecast": recent_grade,
        "issued_draws": len(issued), "graded_issued_draws": len(graded),
        "historical_research": walk_forward(root),
        "historical_archive": archive,
        "online_prequential_replay": online,
        "research_evolution": evolution,
        "online_operations": operations,
        "auto_learning": model_automation,
        "historical_accuracy_proof": {
            "status": research.get("status", "not_yet_run"),
            "scope": research.get("scope", "no_historical_source"),
            "evaluated_draws": research.get("evaluated_draws", 0),
            "top5_model_hits": research.get("top5_model_hits"),
            "top5_reference_hits": research.get("top5_reference_hits"),
            "uniform_expected_top5_hit_draws": research.get("uniform_expected_top5_hit_draws"),
            "mean_log_likelihood_edge_vs_uniform": research.get("mean_log_likelihood_edge_vs_uniform"),
            "descriptive_moving_block_bootstrap_95pct": research.get("descriptive_moving_block_bootstrap_95pct"),
            "prediction_skill_confirmed": False,
        },
        "source_file_sha256": file_hash(root / "data" / "source_observations.jsonl"),
        "issuance_file_sha256": file_hash(root / "data" / "issued_forecasts.jsonl"),
        "warnings": warnings,
        "prediction_skill_confirmed": False,
        "automatic_model_promotion": champion_name != "uniform",
        "actual_purchase_profit_yen": None,
    }


def write_dashboard(root: Path, output: Path, now: datetime | None = None) -> dict:
    data = snapshot(root, now)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return data
