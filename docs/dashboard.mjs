// Pure validator. Distinguish bank/Rakuten matching records from manual claims.
export const VERSION="numbers4-dashboard-v1";
const safeDigits=n=>typeof n==="string"&&/^[0-9]{4}$/.test(n);
const safeTime=t=>typeof t==="string"&&!Number.isNaN(Date.parse(t))&&/[+-]\d\d:\d\d$/.test(t);
export function normalizeStatus(s){
  if(!s||s.version!==VERSION||s.product!=="Numbers4"||
      s.official_auto_fetch_enabled!==true||s.prediction_skill_confirmed!==false||
      s.automatic_model_promotion!==false||s.actual_purchase_profit_yen!==null||
      !safeTime(s.generated_at_jst)||!Number.isInteger(s.consistent_rounds)||
      !Number.isInteger(s.observed_rounds)||!Number.isInteger(s.issued_draws)||!Number.isInteger(s.auto_verified_rounds)||s.auto_verified_rounds<0||s.auto_verified_rounds>s.consistent_rounds||
      s.graded_issued_draws>s.issued_draws||!Number.isInteger(s.graded_issued_draws)||
      !Array.isArray(s.warnings)||s.warnings.some(x=>typeof x!=="string")||
      !["conflict","two_source_entered_consistent","auto_verified_two_publishers","no_corroborated_draws"].includes(s.source_status)){
    throw new Error("監査JSONの安全性・形式を確認できません");
  }
  const d=s.latest_consistent_draw;
  if(d&&(!["two_source_entered_consistent","auto_verified_two_publishers"].includes(d.status)||!safeDigits(d.winning_number)||
       !Number.isInteger(d.round)||typeof d.draw_date!=="string")){
    throw new Error("照合結果の形式が不正です");
  }
  const u=s.latest_unverified_draw;
  if(u&&(u.status!=="publisher_only_not_officially_verified"||
      u.source!=="rakuten_lottery_publication_only"||
      !safeDigits(u.winning_number)||!Number.isInteger(u.round)||u.round<1||
      typeof u.draw_date!=="string"||!/^\d{4}-\d{2}-\d{2}$/.test(u.draw_date)||
      (d&&d.round===u.round&&d.winning_number!==u.winning_number))){
    throw new Error("参考情報の公表元・未照合状態が不正です");
  }
  const p=s.published_forecast;
  if(p&&(!Number.isInteger(p.target_round)||!Array.isArray(p.numbers)||
         p.numbers.length!==5||!p.numbers.every(safeDigits)||
         new Set(p.numbers).size!==5||p.actual_purchase!==false||!safeTime(p.issued_at_jst)||
         !["straight","box","set"].includes(p.mode))){
    throw new Error("事前発行の証拠を確認できません");
  }
  const g=s.latest_graded_issued_forecast;
  const grade=(number,win,mode)=>{
    if(number===win)return mode==="straight"?"straight":mode==="box"?"box":"set_straight";
    if(number.split("").sort().join("")===win.split("").sort().join("")&&mode!=="straight")
      return mode==="box"?"box":"set_box";
    return "miss";
  };
  if(g&&(!d||!["two_source_manual_attestations_consistent","bank_primary_rakuten_publication_match"].includes(g.verification)||
         g.actual_purchase!==false||g.actual_profit_yen!==null||
         !Number.isInteger(g.round)||!safeDigits(g.winning_number)||
         !["straight","box","set"].includes(g.mode)||
         !Array.isArray(g.tickets)||g.tickets.length!==5||
         g.tickets.some(t=>!safeDigits(t.number)||!["straight","box","set_straight","set_box","miss"].includes(t.result))||
         g.tickets.some(t=>t.result!==grade(t.number,g.winning_number,g.mode))||
         g.winning_tickets!==g.tickets.filter(t=>t.result!=="miss").length||
         (d&&g.round===d.round&&g.winning_number!==d.winning_number)||
         (p&&g.round===p.target_round&&(g.mode!==p.mode||
            g.tickets.some((t,i)=>t.number!==p.numbers[i]))))){
    throw new Error("採点済み予測の整合性が不正です");
  }
  const proof=s.historical_accuracy_proof;
  if(!proof || !["not_yet_run","insufficient_history","historical_exploratory_only"].includes(proof.status) ||
     proof.prediction_skill_confirmed!==false||!Number.isInteger(proof.evaluated_draws)||proof.evaluated_draws<0||
     (proof.mean_log_likelihood_edge_vs_uniform!=null&&
      (typeof proof.mean_log_likelihood_edge_vs_uniform!=="number"||!Number.isFinite(proof.mean_log_likelihood_edge_vs_uniform)))){
    throw new Error("過去研究の権限と計算結果を検証できません");
  }
  const archive=s.historical_archive;
  if(archive){
    if(archive.officially_verified!==false || archive.forecast_grading_authorized!==false ||
       !Number.isInteger(archive.record_count) || archive.record_count<0 ||
       !["not_loaded","secondary_public_mirrors_agree_not_officially_verified"].includes(archive.status) ||
       (archive.status==="not_loaded"&&archive.record_count!==0) ||
       (archive.status!=="not_loaded"&&(
         archive.first_round!==1 || archive.last_round!==archive.record_count ||
         !Number.isInteger(archive.last_round) ||
         typeof archive.latest_number!=="string" || !safeDigits(archive.latest_number) ||
         archive.source_independence_not_established!==true ||
         typeof archive.git_blob_sha1!=="string" || !/^[0-9a-f]{40}$/.test(archive.git_blob_sha1)
       ))){
      throw new Error("過去履歴の出典・検証状態が不正です");
    }
  }
  const online=s.online_prequential_replay;
  if(online){
    if(!['not_yet_run','historical_walk_forward_reconstruction_only','stale_or_mismatched_input'].includes(online.status)||
       online.prediction_skill_confirmed!==false||online.officially_verified!==false||
       !Number.isInteger(online.evaluated_draws)||online.evaluated_draws<0){
      throw new Error('逐次予測の研究権限・形式を確認できません');
    }
    if(online.status==='historical_walk_forward_reconstruction_only'){
      const next=online.next_research_candidate;
      if(online.forecast_grading_authorized!==false||online.production_model_changed!==false||
         online.first_evaluated_round!==2||!Number.isInteger(online.last_evaluated_round)||
         online.evaluated_draws!==online.last_evaluated_round-1||
         !Number.isInteger(online.selected_top5_straight_hits)||
         !Number.isInteger(online.uniform_reference_top5_straight_hits)||
         online.selected_top5_straight_hits<0||online.selected_top5_straight_hits>online.evaluated_draws||
         online.uniform_reference_top5_straight_hits<0||online.uniform_reference_top5_straight_hits>online.evaluated_draws||
         typeof online.selected_mean_log_score_edge_vs_uniform!=='number'||
         !Number.isFinite(online.selected_mean_log_score_edge_vs_uniform)||
         typeof online.selected_mean_brier_improvement_vs_uniform!=='number'||
         !Number.isFinite(online.selected_mean_brier_improvement_vs_uniform)||
         !next||next.status!=='research_only_not_issued_not_purchased'||next.accuracy_claim!==false||
         next.data_cutoff_round!==online.last_evaluated_round||
         next.target_round!==online.last_evaluated_round+1||next.draw_date!==null||
         !['uniform','positional_60_alpha10','positional_250_alpha5','positional_1000_alpha20'].includes(next.model)||
         !Array.isArray(next.numbers)||next.numbers.length!==5||!next.numbers.every(safeDigits)||
         new Set(next.numbers).size!==5){
        throw new Error('未来を混入した再現予測・架空の本番昇格は拒否します');
      }
      if(s.historical_archive?.status==='secondary_public_mirrors_agree_not_officially_verified'&&
         (online.last_evaluated_round!==s.historical_archive.last_round||
          online.archive_git_blob_sha1!==s.historical_archive.git_blob_sha1)){
        throw new Error('履歴と逐次予測の参照が一致していません');
      }
    }
  }
  const ageMinutes=(Date.now()-Date.parse(s.generated_at_jst))/60000;
  return {...s,ageMinutes,stale:ageMinutes>90||ageMinutes< -5};
}
