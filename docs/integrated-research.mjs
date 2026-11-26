// Isolated optional panel: stale or malformed research must not hide the main dashboard.
export function normalizeIntegratedResearch(report, status) {
  const fail=()=>{throw new Error("統合研究データの来歴・数値を確認できません")};
  const a=status?.historical_archive, o=status?.online_prequential_replay;
  const hash=x=>typeof x==="string"&&/^[0-9a-f]{40}$/.test(x);
  const finite=x=>typeof x==="number"&&Number.isFinite(x);
  const count=x=>Number.isSafeInteger(x)&&x>=0;
  if(!report||report.version!=="numbers4-public-integrated-research-v1"||
     report.scope!=="secondary_history_only"||report.actual_purchase!==false||
     report.production_promotion_authorized!==false||report.positive_expected_value_confirmed!==false||
     report.purchase_decision!=="SKIP"||!count(report.last_round)||report.last_round<2||
     report.last_round!==a?.last_round||report.last_draw_date!==a?.last_draw_date||
     !hash(report.archive_git_blob_sha1)||report.archive_git_blob_sha1!==a?.git_blob_sha1||
     !hash(report.straight_payout_git_blob_sha1)||
     report.straight_payout_git_blob_sha1!==o?.retrospective_finance?.payout_git_blob_sha1||
     !hash(report.box_payout_git_blob_sha1)||
     report.box_payout_git_blob_sha1!==o?.retrospective_box_finance?.payout_git_blob_sha1)fail();
  for(const v of [report.straight_reference,report.box_reference]){
    if(!v||v.evaluated_rounds!==report.last_round-1||
       !finite(v.expected_gross_recovery_percent)||v.expected_gross_recovery_percent<0||
       !finite(v.simulated_loss_fraction)||v.simulated_loss_fraction<0||v.simulated_loss_fraction>1||
       !count(v.simulations)||v.simulations<1)fail();
  }
  for(const v of [report.straight_risk,report.box_risk]){
    if(!v||!(v.gross_recovery_percent===null||(finite(v.gross_recovery_percent)&&v.gross_recovery_percent>=0))||
       !Number.isSafeInteger(v.hypothetical_net_yen)||!count(v.maximum_settled_drawdown_yen)||
       !count(v.longest_consecutive_losing_purchased_tickets))fail();
  }
  const names=["expanding_mean","rolling_30","rolling_100"];
  if(!count(report.payout_late_count)||!report.payout_mae_yen||
     (report.payout_late_count>0&&names.some(n=>!finite(report.payout_mae_yen[n])||report.payout_mae_yen[n]<0)))fail();
  for(const [models,keys] of [[report.box_models,["uniform_ordered","dirichlet_100","dirichlet_1000","dirichlet_10000"]],
     [report.ensemble_models,["uniform","equal_experts","uniform50","uniform90"]]]){
    if(!models||keys.some(n=>!models[n]||!count(models[n].evaluated_draws)||
       (models[n].evaluated_draws===0?models[n].mean_log_edge!==null:!finite(models[n].mean_log_edge))))fail();
  }
  return report;
}
