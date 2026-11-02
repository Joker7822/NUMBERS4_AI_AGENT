"""Safe, bounded public projection; no unregistered or unissued vectors."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import json

from .evaluation import graded_predictions, walk_forward
from .ledger import read_issued
from .sources import JST, reconcile, corroborated_draws
from .store import file_hash

VERSION = "numbers4-dashboard-v1"


def snapshot(root: Path, now: datetime | None = None) -> dict:
    now = (now or datetime.now(JST)).astimezone(JST)
    states = reconcile(root)
    trusted = corroborated_draws(root)
    issued = read_issued(root)
    graded = graded_predictions(root)
    latest = trusted[-1] if trusted else None
    recent_issued = max(issued, key=lambda r: r["target_round"]) if issued else None
    recent_grade = graded[-1] if graded else None
    warnings = []
    conflicts = [rnd for rnd, state in states.items() if state["status"] == "source_conflict"]
    single = [rnd for rnd, state in states.items() if state["status"] == "single_source_only"]
    if conflicts:
        warnings.append("2系統の当せん結果が一致しない回があります。照合・採点しません。")
    if single:
        warnings.append("独立した2系統の登録がそろっていない回があります。")
    if not trusted:
        warnings.append("Numbers4の照合済み結果が未登録です。履歴の成績を生成しません。")
    else:
        age_days=(now.date()-datetime.fromisoformat(latest["draw_date"]).date()).days
        if age_days > 7:
            warnings.append("直近の登録済み結果が7日超前です。自動更新ではありません。")
    if not issued:
        warnings.append("事前発行した予測はありません。研究候補を発行済みとして表示しません。")
    else:
        if recent_issued["target_round"] not in {r["round"] for r in trusted}:
            warnings.append("最新の発行済み5口はまだ2ソース入力の一致結果で採点できません。")
    return {
        "version": VERSION, "generated_at_jst": now.isoformat(timespec="seconds"),
        "product": "Numbers4", "official_auto_fetch_enabled": False,
        "data_scope": "human_entered_official_source_claims_with_hash_chain",
        "source_status": "conflict" if conflicts else "two_source_entered_consistent" if trusted else "no_corroborated_draws",
        "observed_rounds": len(states), "consistent_rounds": len(trusted),
        "latest_consistent_draw": latest,
        "published_forecast": ({k: recent_issued[k] for k in ("target_round", "draw_date", "mode", "numbers", "issued_at_jst", "model_version", "actual_purchase")}
                               if recent_issued else None),
        "latest_graded_issued_forecast": recent_grade,
        "issued_draws": len(issued), "graded_issued_draws": len(graded),
        "historical_research": walk_forward(root),
        "source_file_sha256": file_hash(root / "data" / "source_observations.jsonl"),
        "issuance_file_sha256": file_hash(root / "data" / "issued_forecasts.jsonl"),
        "warnings": warnings,
        "prediction_skill_confirmed": False, "automatic_model_promotion": False,
        "actual_purchase_profit_yen": None,
    }


def write_dashboard(root: Path, output: Path, now: datetime | None = None) -> dict:
    data = snapshot(root, now)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return data
