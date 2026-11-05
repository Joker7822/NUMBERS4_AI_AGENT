// Pure validator. Distinguish bank/Rakuten matching records from manual claims.
export const VERSION="numbers4-dashboard-v1";
const safeDigits=n=>typeof n==="string"&&/^[0-9]{4}$/.test(n);
const safeTime=t=>typeof t==="string"&&!Number.isNaN(Date.parse(t))&&/[+-]\d\d:\d\d$/.test(t);
export function normalizeStatus(s){
  if(!s||s.version!==VERSION||s.product!=="Numbers4"||
      s.official_auto_fetch_enabled!==true||s.prediction_skill_confirmed!==false||
      typeof s.automatic_model_promotion!=='boolean'||s.actual_purchase_profit_yen!==null||
      !safeTime(s.generated_at_jst)||!Number.isInteger(s.consistent_rounds)||
      !Number.isInteger(s.observed_rounds)||!Number.isInteger(s.issued_draws)||!Number.isInteger(s.auto_verified_rounds)||s.auto_verified_rounds<0||s.auto_verified_rounds>s.consistent_rounds||
      s.graded_issued_draws>s.issued_draws||!Number.isInteger(s.graded_issued_draws)||
      !Array.isArray(s.warnings)||s.warnings.some(x=>typeof x!=="string")||
      !["conflict","two_source_entered_consistent","auto_verified_two_publishers","no_corroborated_draws"].includes(s.source_status)){
    throw new Error("監査JSONの安全性・形式を確認できません");
  }
  // Seven JST calendar dates: prospective issuance and retrospective research
  // have different proof requirements and MUST NEVER share a hit counter.
  const week=s.recent_week;
  if(week!==undefined){
    const end=new Date(Date.parse(s.generated_at_jst)+9*60*60*1000).toISOString().slice(0,10);
    const start=new Date(Date.parse(end+'T00:00:00Z')-6*86400000).toISOString().slice(0,10);
    const inWeek=d=>typeof d==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(d)&&d>=start&&d<=end;
    const descending=rows=>rows.every((r,i)=>i===0||rows[i-1].round>r.round);
    const grade=(n,win,mode)=>{
      if(n===win)return mode==='straight'?'straight':mode==='box'?'box':'set_straight';
      if(mode!=='straight'&&n.split('').sort().join('')===win.split('').sort().join(''))
        return mode==='box'?'box':'set_box';
      return 'miss';
    };
    const issued=week?.issued_forecasts,shadows=week?.shadow_forecasts,research=week?.research_replay;
    if(!week||week.version!=='numbers4-recent-week-v1'||week.days!==7||
       week.start_date!==start||week.end_date!==end||
       !Array.isArray(issued)||!Array.isArray(shadows)||!Array.isArray(research)||
       issued.length>7||shadows.length>7||research.length>7||
       !descending(issued)||!descending(shadows)||!descending(research)||
       issued.some(r=>!Number.isInteger(r.round)||r.round<1||!inWeek(r.draw_date)||
         !safeTime(r.issued_at_jst)||Date.parse(r.issued_at_jst)>Date.parse(s.generated_at_jst)||
         !['straight','box','set'].includes(r.mode)||
         !Array.isArray(r.numbers)||![1,5].includes(r.numbers.length)||
         r.numbers.some(n=>!safeDigits(n))||new Set(r.numbers).size!==r.numbers.length||
         r.actual_purchase!==false||
         !(r.verification==='awaiting_two_source_match'||
           r.verification==='bank_primary_rakuten_publication_match'||
           r.verification==='two_source_manual_attestations_consistent')||
         (r.verification==='awaiting_two_source_match'?
           r.winning_number!==null||r.ticket_results!==null:
           !safeDigits(r.winning_number)||!Array.isArray(r.ticket_results)||
           r.ticket_results.length!==r.numbers.length||
           r.ticket_results.some((v,i)=>v!==grade(r.numbers[i],r.winning_number,r.mode))))||
       shadows.some(r=>!Number.isInteger(r.round)||r.round<1||!inWeek(r.draw_date)||
         !safeDigits(r.number)||!safeTime(r.issued_at_jst)||
         Date.parse(r.issued_at_jst)>Date.parse(s.generated_at_jst)||
         typeof r.model!=='string'||!r.model||
         typeof r.publication_witnessed!=='boolean'||
         typeof r.official_result_verified!=='boolean'||r.actual_purchase!==false||
         (r.official_result_verified?!safeDigits(r.winning_number):r.winning_number!==null)||
         (r.official_result_verified&&r.publication_witnessed?
           r.straight_match!==(r.number===r.winning_number):r.straight_match!==null))||
       research.some(r=>!Number.isInteger(r.round)||r.round<2||!inWeek(r.draw_date)||
         r.data_cutoff_round!==r.round-1||!safeDigits(r.number)||
         !safeDigits(r.reference_result)||typeof r.model!=='string'||!r.model||
         r.straight_match!==(r.number===r.reference_result)||
         r.source_status!=='secondary_history_not_officially_verified'||
         r.issued_before_draw!==false||r.actual_purchase!==false)||
       !Number.isInteger(week.officially_graded_issued)||
       week.officially_graded_issued!==issued.filter(r=>r.ticket_results!==null).length||
       !Number.isInteger(week.officially_matched_shadow)||
       week.officially_matched_shadow!==shadows.filter(r=>r.straight_match!==null).length||
       !Number.isInteger(week.research_reference_matches)||
       week.research_reference_matches!==research.filter(r=>r.straight_match).length){
      throw new Error('直近7日間の予測・照合データの証拠区分または整合性が不正です');
    }
  }
  const e=s.research_evolution;
  if(e){
    const states=['not_yet_run','recursive_research_exploration_not_prospective_evidence',
                  'stale_history_reanalysis'];
    const positiveInt=n=>Number.isInteger(n)&&n>=0;
    if(e.version!=='numbers4-recursive-research-evolution-v1'||
       !states.includes(e.status)||
       !positiveInt(e.generation)||
       !positiveInt(e.evaluated_draws)||
       !positiveInt(e.candidate_models)||e.candidate_models>8||
       !positiveInt(e.research_sources_found)||
       (e.lifetime_unique_sources!==null && e.lifetime_unique_sources!==undefined &&
        (!positiveInt(e.lifetime_unique_sources) ||
         e.lifetime_unique_sources<e.new_unique_sources))||
       (e.new_unique_sources!==undefined &&
        (!positiveInt(e.new_unique_sources) ||
         e.new_unique_sources>e.research_sources_found))||
       (e.requests_attempted!==undefined && !positiveInt(e.requests_attempted))||
       typeof e.web_search_enabled!=='boolean'||
       e.performance_advantage_confirmed!==false||
       e.model_auto_promotion_authorized!==false||
       e.actual_purchase!==false||
       (e.generation===0)!==(e.status==='not_yet_run')||
       (e.status!=='not_yet_run'&&
          (!safeTime(e.generated_at_jst)||!positiveInt(e.research_search_errors)||
           !positiveInt(e.metadata_based_method_leads)||
           e.metadata_based_method_leads>e.research_sources_found||
           e.candidate_models<1||
           e.repeated_historical_cohorts_not_independent!==true))||
       (e.status==='recursive_research_exploration_not_prospective_evidence'&&
          (e.evaluated_draws<1||!safeDigits(e.next_number)||
           typeof e.next_model!=='string'||
           !/^(uniform|rolling_[a-z0-9_]+|ema_[a-z0-9_]+|markov_[a-z0-9_]+)$/.test(e.next_model)))||
       (e.status!=='recursive_research_exploration_not_prospective_evidence'&&
          (e.next_number!==null||e.next_model!==null||
           e.evaluated_draws!==0))){
      throw new Error('研究自己進化の履歴・範囲・予測力の表示は不正です');
    }
  }
  const v=e?.latest_verification;
  if(v!==undefined&&v!==null){
    const safeInteger=n=>Number.isInteger(n)&&n>=0;
    const finiteScore=n=>typeof n==='number'&&Number.isFinite(n)&&Math.abs(n)<=100;
    const auditModelName=n=>typeof n==='string'&&
       /^(uniform|adaptive|(rolling|markov)_[0-9]+_alpha[0-9]+|ema_0p[0-9]+_alpha[0-9]+)$/.test(n);
    const cohort=v.late_cohort;
    const entries=cohort?.model_metrics;
    const recent=v.recent_rounds;
    const names=Array.isArray(entries)?entries.map(m=>m.model):[];
    if(e.status!=='recursive_research_exploration_not_prospective_evidence'||
       v.scope!=='secondary_history_exploratory_reconstruction_only'||
       v.source_status!=='secondary_public_mirrors_agree_not_officially_verified'||
       v.generation!==e.generation||v.generated_at_jst!==e.generated_at_jst||
       v.tickets_per_draw!==1||v.first_round!==2||
       !safeInteger(v.last_round)||v.last_round!==v.evaluated_draws+1||
       v.evaluated_draws!==e.evaluated_draws||
       (s.historical_archive?.last_round!==undefined&&
          v.last_round!==s.historical_archive.last_round)||
       !/^[a-f0-9]{40}$/.test(v.archive_git_blob_sha1)||
       !/^[a-f0-9]{64}$/.test(v.round_predictions_sha256)||
       v.all_rounds_checked_against_archive!==true||
       v.independently_verified_prepublished_forecasts!==false||
       v.bank_primary_all_rounds_verified!==false||
       v.prediction_skill_confirmed!==false||
       v.automatic_model_promotion_authorized!==false||
       v.actual_purchase!==false||
       !safeInteger(v.selected_straight_hits)||
       !safeInteger(v.uniform_reference_straight_hits)||
       v.selected_straight_hits>v.evaluated_draws||
       v.uniform_reference_straight_hits>v.evaluated_draws||
       !finiteScore(v.selected_mean_log_score_edge_vs_uniform)||
       typeof v.full_expected_uniform_hits!=='number'||
       Math.abs(v.full_expected_uniform_hits-v.evaluated_draws/10000)>0.000001||
       !cohort||!safeInteger(cohort.first_round)||
       !safeInteger(cohort.last_round)||
       !safeInteger(cohort.evaluated_draws)||
       cohort.first_round<=2||cohort.last_round!==v.last_round||
       cohort.last_round-cohort.first_round+1!==cohort.evaluated_draws||
       cohort.repeatedly_inspected_not_independent_holdout!==true||
       !Array.isArray(entries)||entries.length!==e.candidate_models+2||
       !names.includes('uniform')||!names.includes('adaptive')||
       new Set(names).size!==names.length||
       entries.some(m=>!auditModelName(m.model)||
          !safeInteger(m.straight_hits)||m.straight_hits>cohort.evaluated_draws||
          !finiteScore(m.mean_log_score_edge_vs_uniform)||
          !finiteScore(m.mean_brier_edge_vs_uniform))||
       entries.find(m=>m.model==='uniform').mean_log_score_edge_vs_uniform!==0||
       !Array.isArray(recent)||recent.length!==Math.min(12,v.evaluated_draws)||
       recent.some((r,i)=>
          r.round!==v.last_round-i||
          !/^\d{4}-\d{2}-\d{2}$/.test(r.draw_date)||
          r.data_cutoff_round!==r.round-1||
          !safeDigits(r.actual)||!safeDigits(r.selected_number)||
          !safeDigits(r.uniform_number)||!names.includes(r.selected_model)||
          r.selected_model==='adaptive'||
          r.selected_hit!==(r.selected_number===r.actual)||
          r.uniform_hit!==(r.uniform_number===r.actual)||
          (r.selected_model==='uniform'&&r.selected_number!==r.uniform_number))){
      throw new Error('最新の過去予測結果の検証データが不正です');
    }
  }else if(e&&e.status==='stale_history_reanalysis'&&v!==null&&v!==undefined){
    throw new Error('履歴不一致の過去検証を表示できません');
  }
  const current=s.latest_research_forecast;
  if(current!==undefined&&current!==null){
    const safeModel=n=>typeof n==='string'&&
      /^(uniform|positional_(60|250|1000)_alpha(5|10|20)|(rolling|markov)_[0-9]+_alpha[0-9]+|ema_0p[0-9]+_alpha[0-9]+)$/.test(n);
    if(current.version!=='numbers4-latest-research-forecast-v1'||
       !['validated_research_evolution','validated_single_ticket_replay'].includes(current.source)||
       current.status!=='research_only_not_issued_not_purchased'||
       current.actual_purchase!==false||
       current.officially_verified!==false||
       current.prediction_skill_confirmed!==false||
       !Number.isInteger(current.target_round)||current.target_round<2||
       !Number.isInteger(current.data_cutoff_round)||
       current.data_cutoff_round!==current.target_round-1||
       !safeDigits(current.number)||!safeModel(current.model)||
       !safeTime(current.computed_at_jst)||
       !safeTime(current.last_changed_at_jst)||
       Date.parse(current.last_changed_at_jst)>Date.parse(s.generated_at_jst)||
       typeof current.changed_since_previous_snapshot!=='boolean'||
       !/^[a-f0-9]{40}$/.test(current.archive_git_blob_sha1)||
       (current.source==='validated_research_evolution'&&
          (!Number.isInteger(current.research_generation)||current.research_generation<1))||
       (current.source==='validated_single_ticket_replay'&&
          current.research_generation!==null)){
      throw new Error('最新の研究予測の更新情報と未発行状態を確認できません');
    }
  }
  const a=s.auto_learning;
  if(a){
    const acceptedModels=['uniform','positional_60_alpha10','positional_250_alpha5','positional_1000_alpha20'];
    const statuses=['no_shadow_forecasts','evidence_integrity_blocked',
      'insufficient_true_prospective_draws','eligible_under_preregistered_uniform_null',
      'no_confirmed_advantage'];
    if(a.version!=='numbers4-prospective-auto-learning-v1'||
       typeof a.protocol_sha256!=='string'||!/^[0-9a-f]{64}$/.test(a.protocol_sha256)||
       a.feature_implemented!==true||!statuses.includes(a.status)||
       !acceptedModels.includes(a.active_champion)||
       !acceptedModels.includes(a.eligible_champion)||
       s.automatic_model_promotion!==(a.active_champion!=='uniform')||
       a.required_prospective_draws!==500||
       !Number.isInteger(a.officially_verified_training_rounds)||
       a.officially_verified_training_rounds<0||
       a.officially_verified_training_rounds>s.auto_verified_rounds||
       !Number.isInteger(a.shadow_forecasts_recorded)||a.shadow_forecasts_recorded<0||
       !Number.isInteger(a.pre_draw_github_witnesses)||a.pre_draw_github_witnesses<0||
       a.pre_draw_github_witnesses>a.shadow_forecasts_recorded||
       !Number.isInteger(a.eligible_prospective_draws)||a.eligible_prospective_draws<0||
       a.eligible_prospective_draws>a.pre_draw_github_witnesses||
       (a.integrity_blocker!==null&&typeof a.integrity_blocker!=='string')||
       a.model_code_from_search_results_executed!==false||
       a.unverified_secondary_training_authorized!==false||
       a.actual_purchase!==false){
      throw new Error('自動学習・本番昇格の出典と保護条件を確認できません');
    }
    if(a.status==='eligible_under_preregistered_uniform_null'&&
       (a.eligible_prospective_draws<500||a.eligible_champion==='uniform')){
      throw new Error('将来検証を満たさない自動昇格の主張です');
    }
  }else if(s.automatic_model_promotion!==false){
    throw new Error('本番モデル昇格の根拠がありません');
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
         ![1,5].includes(p.numbers.length)||!p.numbers.every(safeDigits)||
         new Set(p.numbers).size!==p.numbers.length||p.actual_purchase!==false||!safeTime(p.issued_at_jst)||
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
         !Array.isArray(g.tickets)||![1,5].includes(g.tickets.length)||
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
    const oneTicket=online.tickets_per_draw===1;
    if(online.tickets_per_draw!==undefined&&!oneTicket){
      throw new Error('一口予測の形式が不正です');
    }
    const ticketCount=oneTicket?1:5; // only for validation of frozen legacy v1
    const selectedHits=oneTicket?online.selected_straight_hits:online.selected_top5_straight_hits;
    const uniformHits=oneTicket?online.uniform_reference_straight_hits:online.uniform_reference_top5_straight_hits;
    if(online.status==='historical_walk_forward_reconstruction_only'){
      const next=online.next_research_candidate;
      if(online.forecast_grading_authorized!==false||online.production_model_changed!==false||
         online.first_evaluated_round!==2||!Number.isInteger(online.last_evaluated_round)||
         online.evaluated_draws!==online.last_evaluated_round-1||
         !Number.isInteger(selectedHits)||
         !Number.isInteger(uniformHits)||
         selectedHits<0||selectedHits>online.evaluated_draws||
         uniformHits<0||uniformHits>online.evaluated_draws||
         typeof online.selected_mean_log_score_edge_vs_uniform!=='number'||
         !Number.isFinite(online.selected_mean_log_score_edge_vs_uniform)||
         typeof online.selected_mean_brier_improvement_vs_uniform!=='number'||
         !Number.isFinite(online.selected_mean_brier_improvement_vs_uniform)||
         !next||next.status!=='research_only_not_issued_not_purchased'||next.accuracy_claim!==false||
         next.data_cutoff_round!==online.last_evaluated_round||
         next.target_round!==online.last_evaluated_round+1||next.draw_date!==null||
         !['uniform','positional_60_alpha10','positional_250_alpha5','positional_1000_alpha20'].includes(next.model)||
         !Array.isArray(next.numbers)||next.numbers.length!==ticketCount||!next.numbers.every(safeDigits)||
         new Set(next.numbers).size!==ticketCount){
        throw new Error('未来を混入した再現予測・架空の本番昇格は拒否します');
      }
      const audit=online.research_statistical_audit;
      if(audit!=null&&(
          typeof audit!=='object'||
          audit.scope!=='descriptive_historical_reconstruction_not_preregistered'||
          audit.statistical_significance_is_prospective_proof!==false||
          typeof audit.selected_hit_tail_probability_given_uniform_null!=='number'||
          !Number.isFinite(audit.selected_hit_tail_probability_given_uniform_null)||
          audit.selected_hit_tail_probability_given_uniform_null<0||
          audit.selected_hit_tail_probability_given_uniform_null>1||
          !Number.isInteger(audit.nonuniform_model_selected_rounds)||
          audit.nonuniform_model_selected_rounds<0||
          audit.nonuniform_model_selected_rounds>online.evaluated_draws
      )){
        throw new Error('過去研究の偶然確率を未来の予測実証として表示できません');
      }
      if(s.historical_archive?.status==='secondary_public_mirrors_agree_not_officially_verified'&&
         (online.last_evaluated_round!==s.historical_archive.last_round||
          online.archive_git_blob_sha1!==s.historical_archive.git_blob_sha1)){
        throw new Error('履歴と逐次予測の参照が一致していません');
      }
    }
  }
  if(online?.status==='historical_walk_forward_reconstruction_only'&&online.retrospective_finance){
    const f=online.retrospective_finance;
    const yen=n=>Number.isSafeInteger(n)&&n>=0;
    const payout=f.winning_rounds;
    if(f.version!==(online.tickets_per_draw===1?'numbers4-retrospective-straight-one-finance-v2':'numbers4-retrospective-straight-five-finance-v1')||
       f.status!=='historical_simulation_only_not_actual_purchase'||
       f.ticket_type!=='straight'||f.ticket_unit_cost_yen!==200||
       f.tickets_per_draw!==(online.tickets_per_draw===1?1:5)||f.first_evaluated_round!==2||
       f.evaluated_rounds!==online.evaluated_draws||
       f.last_evaluated_round!==online.last_evaluated_round||
       f.historical_winning_draws!==(online.tickets_per_draw===1?online.selected_straight_hits:online.selected_top5_straight_hits)||
       !yen(f.simulated_ticket_cost_yen)||
       f.simulated_ticket_cost_yen!==online.evaluated_draws*(online.tickets_per_draw===1?200:1000)||
       !yen(f.simulated_payout_yen)||
       !Number.isSafeInteger(f.simulated_net_yen)||
       f.simulated_net_yen!==f.simulated_payout_yen-f.simulated_ticket_cost_yen||
       typeof f.simulated_roi_percent!=='number'||!Number.isFinite(f.simulated_roi_percent)||
       Math.abs(f.simulated_roi_percent -
         Math.round(1000000*f.simulated_net_yen/f.simulated_ticket_cost_yen)/10000)>0.0001||
       !yen(f.baseline_winning_draws)||
       f.baseline_winning_draws!==(online.tickets_per_draw===1?online.uniform_reference_straight_hits:online.uniform_reference_top5_straight_hits)||
       !yen(f.baseline_simulated_payout_yen)||
       !Number.isSafeInteger(f.baseline_simulated_net_yen)||
       f.baseline_simulated_net_yen!==f.baseline_simulated_payout_yen-f.simulated_ticket_cost_yen||
       f.payout_source_status!=='single_secondary_publisher_not_bank_verified'||
       f.bank_primary_payouts_verified!==false||f.actual_purchase_records_present!==false||
       f.production_promotion_authorized!==false||
       f.actual_spend_yen!==null||f.actual_income_yen!==null||f.actual_profit_yen!==null||
       typeof f.payout_git_blob_sha1!=='string'||!/^[0-9a-f]{40}$/.test(f.payout_git_blob_sha1)||
       !Array.isArray(payout)||payout.length!==f.historical_winning_draws||
       payout.some((w,i)=>(
         !Number.isInteger(w.round)||w.round<2||w.round>online.last_evaluated_round||
         (i>0&&w.round<=payout[i-1].round)||
         !/^\d{4}-\d{2}-\d{2}$/.test(w.draw_date)||
         !safeDigits(w.winning_number)||w.matched_prediction!==w.winning_number||
         !Number.isInteger(w.ticket_position)||w.ticket_position<1||w.ticket_position>(online.tickets_per_draw===1?1:5)||
         !yen(w.straight_payout_yen)||w.straight_payout_yen===0||
         w.hypothetical_ticket_cost_yen!==(online.tickets_per_draw===1?200:1000)||
         w.status!=='retrospective_simulated_hit_not_actual_purchase'))||
       payout.reduce((sum,w)=>sum+w.straight_payout_yen,0)!==f.simulated_payout_yen){
      throw new Error('過去シミュレーションの当せん履歴・収支根拠が不正です');
    }
  }
  if(online?.status==='historical_walk_forward_reconstruction_only'&&online.retrospective_box_finance){
    const f=online.retrospective_box_finance;
    const isMoney=n=>Number.isSafeInteger(n)&&n>=0;
    const win=f.winning_rounds;
    const actualBox=n=>typeof n==='string'&&safeDigits(n)&&new Set(n).size>1;
    const sameBox=(a,b)=>a.split('').sort().join('')===b.split('').sort().join('');
    if(f.version!==(online.tickets_per_draw===1?'numbers4-retrospective-box-one-finance-v2':'numbers4-retrospective-box-five-finance-v1')||
       f.status!=='historical_simulation_only_not_actual_purchase'||
       f.ticket_type!=='box'||f.requested_tickets_per_round!==(online.tickets_per_draw===1?1:5)||
       f.ticket_unit_cost_yen!==200||
       f.first_evaluated_round!==2||f.evaluated_rounds!==online.evaluated_draws||
       f.last_evaluated_round!==online.last_evaluated_round||
       !isMoney(f.simulated_purchased_tickets)||!isMoney(f.excluded_ineligible_tickets)||
       f.simulated_purchased_tickets+f.excluded_ineligible_tickets!==f.evaluated_rounds*(online.tickets_per_draw===1?1:5)||
       !isMoney(f.simulated_ticket_cost_yen)||
       f.simulated_ticket_cost_yen!==f.simulated_purchased_tickets*200||
       !isMoney(f.simulated_payout_yen)||
       !Number.isSafeInteger(f.simulated_net_yen)||
       f.simulated_net_yen!==f.simulated_payout_yen-f.simulated_ticket_cost_yen||
       (f.simulated_ticket_cost_yen>0
         ?typeof f.simulated_roi_percent!=='number'||
          !Number.isFinite(f.simulated_roi_percent)||
          Math.abs(f.simulated_roi_percent-
            Math.round(1000000*f.simulated_net_yen/f.simulated_ticket_cost_yen)/10000)>0.0001
         :f.simulated_roi_percent!==null)||
       !isMoney(f.historical_winning_draws)||!isMoney(f.historical_winning_tickets)||
       f.historical_winning_tickets>f.simulated_purchased_tickets||
       !isMoney(f.baseline_purchased_tickets)||!isMoney(f.baseline_excluded_ineligible_tickets)||
       f.baseline_purchased_tickets+f.baseline_excluded_ineligible_tickets!==f.evaluated_rounds*(online.tickets_per_draw===1?1:5)||
       !isMoney(f.baseline_ticket_cost_yen)||f.baseline_ticket_cost_yen!==f.baseline_purchased_tickets*200||
       !isMoney(f.baseline_winning_tickets)||f.baseline_winning_tickets>f.baseline_purchased_tickets||
       !isMoney(f.baseline_simulated_payout_yen)||!Number.isSafeInteger(f.baseline_simulated_net_yen)||
       f.baseline_simulated_net_yen!==f.baseline_simulated_payout_yen-f.baseline_ticket_cost_yen||
       f.payout_source_status!=='single_secondary_publisher_not_bank_verified'||
       f.bank_primary_payouts_verified!==false||f.actual_purchase_records_present!==false||
       f.original_predictions_unchanged!==true||f.production_promotion_authorized!==false||
       f.actual_spend_yen!==null||f.actual_income_yen!==null||f.actual_profit_yen!==null||
       typeof f.payout_git_blob_sha1!=='string'||!/^[0-9a-f]{40}$/.test(f.payout_git_blob_sha1)||
       !Array.isArray(win)||win.length!==f.historical_winning_draws||
       win.some((w,i)=>(
         !Number.isInteger(w.round)||w.round<2||w.round>online.last_evaluated_round||
         (i>0&&w.round<=win[i-1].round)||
         !/^\d{4}-\d{2}-\d{2}$/.test(w.draw_date)||
         !actualBox(w.winning_number)||
         !Array.isArray(w.matched_tickets)||w.matched_tickets.length<1||
         w.matched_tickets.length>(online.tickets_per_draw===1?1:5)||w.winning_ticket_count!==w.matched_tickets.length||
         !isMoney(w.box_payout_yen_per_ticket)||w.box_payout_yen_per_ticket===0||
         w.hypothetical_box_payout_yen!==w.box_payout_yen_per_ticket*w.winning_ticket_count||
         w.status!=='retrospective_simulated_box_win_not_actual_purchase'||
         w.matched_tickets.some((t,j)=>(
           !Number.isInteger(t.ticket_position)||t.ticket_position<1||t.ticket_position>(online.tickets_per_draw===1?1:5)||
           !actualBox(t.predicted_number)||!sameBox(t.predicted_number,w.winning_number)||
           (j>0&&t.ticket_position<=w.matched_tickets[j-1].ticket_position)
         ))
       ))||
       win.reduce((sum,w)=>sum+w.winning_ticket_count,0)!==f.historical_winning_tickets||
       win.reduce((sum,w)=>sum+w.hypothetical_box_payout_yen,0)!==f.simulated_payout_yen){
      throw new Error('ボックス購入の再現的中・配当・収支の証拠が不正です');
    }
  }
  const ops=s.online_operations;
  if(ops){
    const goodStates=['not_verified','source_unavailable','secondary_publication_lag','stale',
      'manual_review_required','online_monitoring_active_secondary_research_only'];
    const ruleStates=['not_checked','legacy_read_only_unreviewed',
      'official_rule_anchors_consistent','degraded_official_rules_unverified',
      'rule_change_requires_review'];
    const feedStates=['not_checked','validated_no_new_draws',
      'appended_secondary_history_not_officially_verified',
      'network_unavailable_old_archive_preserved',
      'secondary_mirror_lag_old_archive_preserved'];
    const timestamp=t=>t===null||safeTime(t);
    const age=t=>t===null||(typeof t==='number'&&Number.isFinite(t)&&t>=0);
    if(ops.version!=='numbers4-online-production-monitor-status-v1'||
       !goodStates.includes(ops.state)||!ruleStates.includes(ops.official_rule_status)||
       !feedStates.includes(ops.secondary_feed_status)||
       !Number.isInteger(ops.rule_sources_consistent)||
       ops.rule_sources_consistent<0||ops.rule_sources_consistent>3||
       ops.rule_sources_required!==3||
       !timestamp(ops.rule_checked_at_jst)||!timestamp(ops.secondary_checked_at_jst)||
       !age(ops.rule_audit_age_hours)||!age(ops.secondary_audit_age_hours)||
       ops.max_freshness_hours!==96||
       ops.rule_auto_adoption!==false||
       ops.bank_first_party_draws_verified_by_this_monitor!==false||
       ops.bank_first_party_payouts_verified_by_this_monitor!==false||
       ops.predictive_skill_confirmed!==false||
       ops.model_auto_promotion!==false||
       ops.real_purchases_enabled!==false||
       !Array.isArray(ops.warnings)||ops.warnings.some(x=>typeof x!=='string')){
      throw new Error('オンライン本番監査の出典・権限・状態が不正です');
    }
  }
  const ageMinutes=(Date.now()-Date.parse(s.generated_at_jst))/60000;
  return {...s,ageMinutes,stale:ageMinutes>90||ageMinutes< -5};
}
