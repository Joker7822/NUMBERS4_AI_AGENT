"""Conservative public status derived from timestamped, bounded online source audits."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from .online_monitor import VERSION as RULE_VERSION

SOURCE_VERSION="numbers4-online-secondary-source-refresh-v1"
CHECK_LIMIT_HOURS=96


def _read(root: Path, relative: str) -> dict | None:
    p=root/relative
    if not p.is_file():
        return None
    data=json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data,dict):
        raise ValueError("online audit file is not an object")
    return data


def _age(now: datetime, checked: object) -> float | None:
    if not isinstance(checked,str):
        return None
    try:
        dt=datetime.fromisoformat(checked)
    except ValueError:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    age=(now.astimezone(timezone.utc)-dt.astimezone(timezone.utc)).total_seconds()/3600
    return round(age,3) if age>=-0.1 else None


def snapshot(root: Path, now: datetime) -> dict:
    """Monitoring adoption is distinct from authority to grade official tickets."""
    ref=_read(root,"research/online_reference_audit.json")
    feed=_read(root,"research/online_source_audit.json")
    rule_status="not_checked"
    feed_status="not_checked"
    sources_ok=0
    latest_check=None
    feed_check=None
    notes=[]
    if ref:
        if ref.get("version") != RULE_VERSION:
            rule_status="legacy_read_only_unreviewed"
            notes.append("旧形式のURL到達確認はルール検証済みと認めません。")
        else:
            rule_status=ref.get("status","not_checked")
            if rule_status not in {
                "official_rule_anchors_consistent",
                "degraded_official_rules_unverified",
                "rule_change_requires_review"
            }:
                raise ValueError("unknown official rule monitoring state")
            if (ref.get("automatic_lottery_rules_adoption") is not False or
                ref.get("official_draw_result_verified_by_this_audit") is not False or
                ref.get("official_payouts_verified_by_this_audit") is not False or
                ref.get("model_auto_promotion_authorized") is not False or
                ref.get("required_rule_sources")!=3 or
                not isinstance(ref.get("rule_sources_consistent"),int) or
                not isinstance(ref.get("rule_sources_changed"),int) or
                not isinstance(ref.get("rule_sources_unavailable"),int) or
                ref["rule_sources_consistent"]+ref["rule_sources_changed"]+
                   ref["rule_sources_unavailable"]!=3):
                raise ValueError("unsafe or inconsistent online rule report")
            sources_ok=ref["rule_sources_consistent"]
            latest_check=ref.get("checked_at_jst")
    if feed:
        if (feed.get("version")!=SOURCE_VERSION or
            feed.get("official_bank_verified") is not False or
            feed.get("issued_forecast_grading_authorized") is not False or
            feed.get("automatic_model_promotion") is not False):
            raise ValueError("unsafe or unknown historical online feed report")
        feed_status=feed.get("status","not_checked")
        if feed_status not in {
            "validated_no_new_draws","appended_secondary_history_not_officially_verified",
            "network_unavailable_old_archive_preserved",
            "secondary_mirror_lag_old_archive_preserved"
        }:
            raise ValueError("unknown historical feed status: manual review required")
        feed_check=feed.get("checked_at_jst")
    hours_ref=_age(now,latest_check)
    hours_feed=_age(now,feed_check)
    stale_ref=(hours_ref is None or hours_ref>CHECK_LIMIT_HOURS)
    stale_feed=(hours_feed is None or hours_feed>CHECK_LIMIT_HOURS)
    if rule_status=="rule_change_requires_review":
        state="manual_review_required"
        notes.append("公開元の公式ルールから必須文言が確認できず、ルールの自動採用を停止しています。")
    elif rule_status=="degraded_official_rules_unverified":
        state="source_unavailable"
        notes.append("公式ルールの一部が取得できず、最新条件を確認できません。")
    elif rule_status!="official_rule_anchors_consistent":
        state="not_verified"
    elif feed_status=="network_unavailable_old_archive_preserved":
        state="source_unavailable"
        notes.append("公開データの取得失敗により旧履歴を維持しています。")
    elif (feed_status=="secondary_mirror_lag_old_archive_preserved" or
          (feed and feed.get("deferred_unmatched_rows",0)>0)):
        state="secondary_publication_lag"
        notes.append("二次公開元の最新回に1回分の反映差があり、未照合の回は研究学習から除外しています。照合済み履歴のみ保持・使用します。")
    elif stale_ref or stale_feed:
        state="stale"
        notes.append("定期監査結果が96時間以内に更新されていません。GitHub Actionsの実行状況を確認してください。")
    else:
        state="online_monitoring_active_secondary_research_only"
    return {
        "version":"numbers4-online-production-monitor-status-v1",
        "state":state,
        "official_rule_status":rule_status,
        "rule_sources_consistent":sources_ok,
        "rule_sources_required":3,
        "rule_checked_at_jst":latest_check,
        "rule_audit_age_hours":hours_ref,
        "secondary_feed_status":feed_status,
        "secondary_checked_at_jst":feed_check,
        "secondary_audit_age_hours":hours_feed,
        "max_freshness_hours":CHECK_LIMIT_HOURS,
        "rule_auto_adoption":False,
        "bank_first_party_draws_verified_by_this_monitor":False,
        "bank_first_party_payouts_verified_by_this_monitor":False,
        "predictive_skill_confirmed":False,
        "model_auto_promotion":False,
        "real_purchases_enabled":False,
        "warnings":notes,
    }
