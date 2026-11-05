import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {normalizeStatus} from '../docs/dashboard.mjs';
const source=()=>JSON.parse(readFileSync(new URL('../docs/data/status.json',import.meta.url),'utf8'));
test('actual checked-in public Numbers4 status is honest and safe',()=>{
  const data=normalizeStatus(source());
  assert.equal(data.product,'Numbers4');
  assert.equal(data.consistent_rounds>=0,true);
  assert.equal(data.issued_draws>=0,true);
  assert.equal(data.prediction_skill_confirmed,false);
  assert.equal(data.official_auto_fetch_enabled,true);
});
test('cannot fake a successful prediction or source proof',()=>{
  const s=source();s.prediction_skill_confirmed=true;
  assert.throws(()=>normalizeStatus(s),/安全性/);
  s.prediction_skill_confirmed=false;s.latest_consistent_draw={round:1,winning_number:'0000',status:'unverified'};
  assert.throws(()=>normalizeStatus(s),/照合結果/);
});

test('a forged graded result cannot be shown as a win',()=>{
  const s=source();s.consistent_rounds=1;s.observed_rounds=1;s.issued_draws=1;s.graded_issued_draws=1;
  s.published_forecast=null;
  s.latest_consistent_draw={round:10,draw_date:'2026-10-30',winning_number:'0001',status:'two_source_entered_consistent'};
  s.latest_graded_issued_forecast={round:10,mode:'straight',winning_number:'0001',
    verification:'two_source_manual_attestations_consistent',actual_purchase:false,actual_profit_yen:null,
    winning_tickets:1,tickets:['1111','1112','1113','1114','1115'].map(number=>({number,result:'miss'}))};
  assert.throws(()=>normalizeStatus(s),/採点済み/);
});

test('single-publisher reference result is visible only with strict unverified status',()=>{
  const s=source();
  s.latest_unverified_draw={round:7104,draw_date:'2026-10-30',winning_number:'5805',
    status:'publisher_only_not_officially_verified',source:'rakuten_lottery_publication_only'};
  const v=normalizeStatus(s);
  assert.equal(v.latest_unverified_draw.winning_number,'5805');
  assert.equal(v.consistent_rounds,0);
  assert.equal(v.prediction_skill_confirmed,false);
  s.latest_unverified_draw.status='auto_verified_two_publishers';
  assert.throws(()=>normalizeStatus(s),/参考情報/);
});

test('all historical rows are labelled as secondary, never officially graded',()=>{
  const s=source();
  const actual=s.historical_archive;
  assert.equal(actual.status,'secondary_public_mirrors_agree_not_officially_verified');
  assert.ok(actual.record_count>=7104);
  const valid=normalizeStatus(s);
  assert.equal(valid.historical_archive.record_count,actual.record_count);
  assert.equal(valid.consistent_rounds,source().consistent_rounds);
  assert.equal(valid.prediction_skill_confirmed,false);
  s.historical_archive.officially_verified=true;
  assert.throws(()=>normalizeStatus(s),/過去履歴/);
  s.historical_archive.officially_verified=false;
  s.historical_archive.forecast_grading_authorized=true;
  assert.throws(()=>normalizeStatus(s),/過去履歴/);
});

test('round-two replay is historical only and never published as a winning prediction',()=>{
  const s=source();
  // This isolated 4-round legacy replay fixture is not the latest 7103-round
  // generation. Remove that unrelated projection instead of fabricating its evidence.
  delete s.research_evolution;
  s.historical_archive={
    status:'secondary_public_mirrors_agree_not_officially_verified',
    record_count:4,first_round:1,last_round:4,
    first_draw_date:'1994-10-07',last_draw_date:'1994-10-28',
    latest_number:'0171',officially_verified:false,
    forecast_grading_authorized:false,source_independence_not_established:true,
    git_blob_sha1:'b85c1d9fe3cb4899446d8ef0269d9fb3e2cd7466'};
  s.online_prequential_replay={
    status:'historical_walk_forward_reconstruction_only',
    evaluated_draws:3,first_evaluated_round:2,last_evaluated_round:4,
    selected_top5_straight_hits:0,uniform_reference_top5_straight_hits:0,
    selected_mean_log_score_edge_vs_uniform:0,selected_mean_brier_improvement_vs_uniform:0,
    archive_git_blob_sha1:s.historical_archive.git_blob_sha1,
    forecast_grading_authorized:false,production_model_changed:false,
    prediction_skill_confirmed:false,officially_verified:false,
    next_research_candidate:{target_round:5,data_cutoff_round:4,
      model:'uniform',numbers:['0000','0001','0002','0003','0004'],draw_date:null,
      status:'research_only_not_issued_not_purchased',accuracy_claim:false}};
  assert.equal(normalizeStatus(s).online_prequential_replay.evaluated_draws,3);
  s.online_prequential_replay.forecast_grading_authorized=true;
  assert.throws(()=>normalizeStatus(s),/再現予測/);
  s.online_prequential_replay.forecast_grading_authorized=false;
  s.online_prequential_replay.next_research_candidate.data_cutoff_round=5;
  assert.throws(()=>normalizeStatus(s),/再現予測/);
});

test('hypothetical per-round payouts and non-misses are strictly validated',()=>{
  const s=source();
  const online=s.online_prequential_replay;
  assert.equal(online.status,'historical_walk_forward_reconstruction_only');
  const total=online.evaluated_draws*200;
  online.selected_straight_hits=1;
  const payout=900000;
  online.retrospective_finance={
    version:'numbers4-retrospective-straight-one-finance-v2',
    status:'historical_simulation_only_not_actual_purchase',
    ticket_type:'straight',tickets_per_draw:1,ticket_unit_cost_yen:200,
    first_evaluated_round:2,last_evaluated_round:online.last_evaluated_round,
    evaluated_rounds:online.evaluated_draws,historical_winning_draws:1,
    simulated_ticket_cost_yen:total,simulated_payout_yen:payout,
    simulated_net_yen:payout-total,
    simulated_roi_percent:Math.round(1000000*(payout-total)/total)/10000,
    baseline_winning_draws:online.uniform_reference_straight_hits,
    baseline_simulated_payout_yen:2200000,
    baseline_simulated_net_yen:2200000-total,
    winning_rounds:[{
      round:3,draw_date:'1994-10-21',winning_number:'0097',
      matched_prediction:'0097',ticket_position:1,selected_model:'uniform',
      straight_payout_yen:payout,hypothetical_ticket_cost_yen:200,
      status:'retrospective_simulated_hit_not_actual_purchase'
    }],
    payout_git_blob_sha1:'464a0231226aee980d539cdacdcca75e75a8e25a',
    payout_source_status:'single_secondary_publisher_not_bank_verified',
    bank_primary_payouts_verified:false,actual_purchase_records_present:false,
    actual_spend_yen:null,actual_income_yen:null,actual_profit_yen:null,
    production_promotion_authorized:false
  };
  assert.equal(normalizeStatus(s).online_prequential_replay.retrospective_finance.historical_winning_draws,1);
  online.retrospective_finance.simulated_payout_yen+=100;
  assert.throws(()=>normalizeStatus(s),/シミュレーション/);
  online.retrospective_finance.simulated_payout_yen=payout;
  online.retrospective_finance.actual_profit_yen=1;
  assert.throws(()=>normalizeStatus(s),/シミュレーション/);
  online.retrospective_finance.actual_profit_yen=null;
  online.retrospective_finance.bank_primary_payouts_verified=true;
  assert.throws(()=>normalizeStatus(s),/シミュレーション/);
});

test('BOX finance is never mistaken for actual purchases or STRAIGHT outcomes',()=>{
  const s=source();
  const online=s.online_prequential_replay;
  assert.equal(online.status,'historical_walk_forward_reconstruction_only');
  const bought=online.evaluated_draws-2;
  const spend=bought*200;
  const payout=42000;
  online.retrospective_box_finance={
    version:'numbers4-retrospective-box-one-finance-v2',
    status:'historical_simulation_only_not_actual_purchase',
    ticket_type:'box',requested_tickets_per_round:1,ticket_unit_cost_yen:200,
    evaluated_rounds:online.evaluated_draws,first_evaluated_round:2,
    last_evaluated_round:online.last_evaluated_round,
    simulated_purchased_tickets:bought,excluded_ineligible_tickets:2,
    historical_winning_draws:1,historical_winning_tickets:1,
    simulated_ticket_cost_yen:spend,simulated_payout_yen:payout,
    simulated_net_yen:payout-spend,
    simulated_roi_percent:Math.round(1000000*(payout-spend)/spend)/10000,
    baseline_purchased_tickets:bought,baseline_excluded_ineligible_tickets:2,
    baseline_winning_tickets:1,
    baseline_ticket_cost_yen:spend,
    baseline_simulated_payout_yen:42000,
    baseline_simulated_net_yen:42000-spend,
    winning_rounds:[{
      round:212,draw_date:'1996-12-03',
      winning_number:'9475',selected_model:'uniform',
      matched_tickets:[{ticket_position:1,predicted_number:'7594'}],
      winning_ticket_count:1,box_payout_yen_per_ticket:42000,
      hypothetical_box_payout_yen:42000,
      status:'retrospective_simulated_box_win_not_actual_purchase'
    }],
    payout_git_blob_sha1:'fddbb69e36a70103733e8e55a351b66187fac70c',
    payout_source_status:'single_secondary_publisher_not_bank_verified',
    bank_primary_payouts_verified:false,
    actual_purchase_records_present:false,
    actual_spend_yen:null,actual_income_yen:null,actual_profit_yen:null,
    original_predictions_unchanged:true,production_promotion_authorized:false
  };
  assert.equal(normalizeStatus(s).online_prequential_replay.retrospective_box_finance.historical_winning_tickets,1);
  const f=online.retrospective_box_finance;
  f.simulated_payout_yen+=1;
  assert.throws(()=>normalizeStatus(s),/ボックス購入/);
  f.simulated_payout_yen=payout;
  f.winning_rounds[0].matched_tickets[0].predicted_number='7593';
  assert.throws(()=>normalizeStatus(s),/ボックス購入/);
  f.winning_rounds[0].matched_tickets[0].predicted_number='7594';
  f.actual_profit_yen=1;
  assert.throws(()=>normalizeStatus(s),/ボックス購入/);
  f.actual_profit_yen=null;
  f.bank_primary_payouts_verified=true;
  assert.throws(()=>normalizeStatus(s),/ボックス購入/);
});

test('dashboard displays both STRAIGHT and BOX simulations independently',()=>{
  const html=readFileSync(new URL('../docs/index.html',import.meta.url),'utf8');
  const code=readFileSync(new URL('../docs/app.js',import.meta.url),'utf8');
  const straightIds=['simulation-straight-wins','simulation-straight-spend','simulation-straight-income',
    'simulation-straight-net','simulation-straight-roi','simulation-straight-baseline',
    'historical-straight-wins','historical-straight-wins-meta','actual-straight-profit'];
  const boxIds=['simulation-box-wins','simulation-box-tickets','simulation-ineligible',
    'simulation-spend','simulation-income','simulation-net','simulation-roi',
    'historical-wins','historical-wins-meta','actual-profit'];
  for(const id of straightIds.concat(boxIds)){
    assert.ok(html.includes('id="'+id+'"'), 'missing UI output '+id);
    assert.ok(code.includes('"'+id+'"'), 'missing UI binding '+id);
  }
  const data=normalizeStatus(source());
  assert.equal(data.online_prequential_replay.status,'historical_walk_forward_reconstruction_only');
  const s=data.online_prequential_replay.retrospective_finance;
  const b=data.online_prequential_replay.retrospective_box_finance;
  assert.equal(s.ticket_type,'straight');
  assert.equal(b.ticket_type,'box');
  assert.equal(s.simulated_net_yen,s.simulated_payout_yen-s.simulated_ticket_cost_yen);
  assert.equal(b.simulated_net_yen,b.simulated_payout_yen-b.simulated_ticket_cost_yen);
  assert.equal(s.historical_winning_draws,s.winning_rounds.length);
  assert.equal(b.historical_winning_draws,b.winning_rounds.length);
  assert.equal(s.actual_profit_yen,null);
  assert.equal(b.actual_profit_yen,null);
  assert.equal(data.prediction_skill_confirmed,false);
});

test('online production monitor remains research-only and has real UI fields',()=>{
  const html=readFileSync(new URL('../docs/index.html',import.meta.url),'utf8');
  const js=readFileSync(new URL('../docs/app.js',import.meta.url),'utf8');
  const ids=['ops-state','ops-rules','ops-last-rules','ops-source-status','ops-last-feed'];
  for(const id of ids){
    assert.ok(html.includes('id="'+id+'"'),'missing monitor UI: '+id);
    assert.ok(js.includes('"'+id+'"'),'missing monitor binding: '+id);
  }
  const s=source();
  s.online_operations={
    version:'numbers4-online-production-monitor-status-v1',
    state:'online_monitoring_active_secondary_research_only',
    official_rule_status:'official_rule_anchors_consistent',
    rule_sources_consistent:3,rule_sources_required:3,
    rule_checked_at_jst:'2026-11-02T15:00:00+09:00',rule_audit_age_hours:0,
    secondary_feed_status:'validated_no_new_draws',
    secondary_checked_at_jst:'2026-11-02T15:00:00+09:00',secondary_audit_age_hours:0,
    max_freshness_hours:96,rule_auto_adoption:false,
    bank_first_party_draws_verified_by_this_monitor:false,
    bank_first_party_payouts_verified_by_this_monitor:false,
    predictive_skill_confirmed:false,model_auto_promotion:false,
    real_purchases_enabled:false,warnings:[]
  };
  assert.equal(normalizeStatus(s).online_operations.rule_sources_consistent,3);
  s.online_operations.bank_first_party_draws_verified_by_this_monitor=true;
  assert.throws(()=>normalizeStatus(s),/オンライン本番監査/);
  s.online_operations.bank_first_party_draws_verified_by_this_monitor=false;
  s.online_operations.model_auto_promotion=true;
  assert.throws(()=>normalizeStatus(s),/オンライン本番監査/);
});

test('historical chance benchmark cannot be forged into prospective proof',()=>{
  const s=source();
  s.online_prequential_replay.research_statistical_audit={
    scope:'descriptive_historical_reconstruction_not_preregistered',
    statistical_significance_is_prospective_proof:true,
    selected_hit_tail_probability_given_uniform_null:0.284292006,
    nonuniform_model_selected_rounds:41,
  };
  assert.throws(()=>normalizeStatus(s),/過去研究の偶然確率/);
  s.online_prequential_replay.research_statistical_audit.statistical_significance_is_prospective_proof=false;
  assert.doesNotThrow(()=>normalizeStatus(s));
  s.online_prequential_replay.research_statistical_audit.selected_hit_tail_probability_given_uniform_null=2;
  assert.throws(()=>normalizeStatus(s),/過去研究の偶然確率/);
});

test('new one-ticket reports never validate as five-ticket portfolios',()=>{
  const s=source();
  const online=s.online_prequential_replay;
  assert.equal(online.status,'historical_walk_forward_reconstruction_only');
  const old=online.next_research_candidate.numbers.slice();
  online.tickets_per_draw=1;
  online.selected_straight_hits=0;
  online.uniform_reference_straight_hits=0;
  online.next_research_candidate.numbers=[old[0]];
  delete online.retrospective_finance;
  delete online.retrospective_box_finance;
  assert.doesNotThrow(()=>normalizeStatus(s));
  online.next_research_candidate.numbers=[old[0],old[0]];
  assert.throws(()=>normalizeStatus(s),/再現予測/);
  online.next_research_candidate.numbers=[old[0]];
  online.tickets_per_draw=2;
  assert.throws(()=>normalizeStatus(s),/一口予測/);
});

test('prospective auto-learning never promotes on zero verified bank results or forged metrics',()=>{
  const s=source();
  s.auto_learning={
    version:'numbers4-prospective-auto-learning-v1',
    feature_implemented:true,protocol_sha256:'a'.repeat(64),
    status:'no_shadow_forecasts',active_champion:'uniform',
    eligible_champion:'uniform',officially_verified_training_rounds:0,
    shadow_forecasts_recorded:0,pre_draw_github_witnesses:0,
    eligible_prospective_draws:0,required_prospective_draws:500,
    integrity_blocker:null,model_assessments:{},
    model_code_from_search_results_executed:false,
    unverified_secondary_training_authorized:false,actual_purchase:false,
  };
  assert.doesNotThrow(()=>normalizeStatus(s));
  s.automatic_model_promotion=true;
  assert.throws(()=>normalizeStatus(s),/自動学習/);
  s.automatic_model_promotion=false;
  s.auto_learning.eligible_prospective_draws=500;
  assert.throws(()=>normalizeStatus(s),/自動学習/);
  s.auto_learning.eligible_prospective_draws=0;
  s.auto_learning.model_code_from_search_results_executed=true;
  assert.throws(()=>normalizeStatus(s),/自動学習/);
});

test('predictive automatic-learning panel is connected to validated status fields',()=>{
  const html=readFileSync(new URL('../docs/index.html',import.meta.url),'utf8');
  const js=readFileSync(new URL('../docs/app.js',import.meta.url),'utf8');
  for(const id of ['auto-learning-status','auto-learning-champion',
                   'auto-learning-bank-count','auto-learning-witnesses',
                   'auto-learning-prospective','auto-learning-promotion']){
    assert.ok(html.includes('id="'+id+'"'),id+' missing from markup');
    assert.ok(js.includes('"'+id+'"'),id+' missing from renderer');
  }
});

test('recursive evolution cannot masquerade as independent proof or production promotion',()=>{
  const s=source();
  s.research_evolution={
    version:'numbers4-recursive-research-evolution-v1',
    status:'recursive_research_exploration_not_prospective_evidence',
    generation:2,evaluated_draws:7103,candidate_models:5,
    research_sources_found:3,web_search_enabled:false,
    research_search_errors:0,metadata_based_method_leads:2,
    next_model:'rolling_60_alpha10',next_number:'0123',
    generated_at_jst:'2026-11-02T18:20:00+09:00',
    repeated_historical_cohorts_not_independent:true,
    performance_advantage_confirmed:false,
    model_auto_promotion_authorized:false,actual_purchase:false,
  };
  assert.doesNotThrow(()=>normalizeStatus(s));
  s.research_evolution.performance_advantage_confirmed=true;
  assert.throws(()=>normalizeStatus(s),/自己進化/);
  s.research_evolution.performance_advantage_confirmed=false;
  s.research_evolution.model_auto_promotion_authorized=true;
  assert.throws(()=>normalizeStatus(s),/自己進化/);
  s.research_evolution.model_auto_promotion_authorized=false;
  s.research_evolution.next_number='12345';
  assert.throws(()=>normalizeStatus(s),/自己進化/);
});

test('cumulative online sources can exceed earlier forty-result UI ceiling',()=>{
  const s=source();
  s.research_evolution={
    version:'numbers4-recursive-research-evolution-v1',
    status:'recursive_research_exploration_not_prospective_evidence',
    generation:1200,evaluated_draws:7103,candidate_models:6,
    research_sources_found:143,web_search_enabled:false,
    lifetime_unique_sources:20000,new_unique_sources:120,
    requests_attempted:8,research_search_errors:0,
    metadata_based_method_leads:98,
    next_model:'uniform',next_number:'6993',
    generated_at_jst:'2026-11-02T19:20:00+09:00',
    repeated_historical_cohorts_not_independent:true,
    performance_advantage_confirmed:false,
    model_auto_promotion_authorized:false,actual_purchase:false,
  };
  assert.doesNotThrow(()=>normalizeStatus(s));
  s.research_evolution.new_unique_sources=144;
  assert.throws(()=>normalizeStatus(s),/自己進化/);
  s.research_evolution.new_unique_sources=120;
  s.research_evolution.lifetime_unique_sources=10;
  assert.throws(()=>normalizeStatus(s),/自己進化/);
});

test('self-evolution research controls are visible but clearly exploratory',()=>{
  const html=readFileSync(new URL('../docs/index.html',import.meta.url),'utf8');
  const js=readFileSync(new URL('../docs/app.js',import.meta.url),'utf8');
  for(const id of ['evolution-status','evolution-generation','evolution-draws',
                   'evolution-models','evolution-sources',
                   'evolution-next','evolution-time']){
    assert.ok(html.includes('id="'+id+'"'),id);
    assert.ok(js.includes('"'+id+'"'),id);
  }
  assert.ok(html.includes('同じ過去データを再利用するため'));
});

test('latest historical one-ticket validation is displayed but never upgraded to official proof',()=>{
  const s=source();
  const e=s.research_evolution;
  const report=JSON.parse(readFileSync(new URL('../research/evolution_report.json',import.meta.url),'utf8'));
  // Secondary draw history can advance before research evolution catches up.
  // This fixture tests one internally consistent *hypothetical fresh generation*.
  e.status='recursive_research_exploration_not_prospective_evidence';
  e.evaluated_draws=s.historical_archive.last_round-1;
  e.candidate_models=report.model_ids.length;
  e.next_model='uniform';
  e.next_number='1234';
  const models=['uniform','adaptive',...report.model_ids];
  const last=s.historical_archive.last_round;
  const n=last-5000;
  const v={
    scope:'secondary_history_exploratory_reconstruction_only',
    generation:e.generation,generated_at_jst:e.generated_at_jst,
    source_status:'secondary_public_mirrors_agree_not_officially_verified',
    archive_git_blob_sha1:'a'.repeat(40),
    round_predictions_sha256:'b'.repeat(64),
    tickets_per_draw:1,first_round:2,last_round:last,
    evaluated_draws:e.evaluated_draws,
    selected_straight_hits:1,uniform_reference_straight_hits:1,
    selected_mean_log_score_edge_vs_uniform:0,
    full_expected_uniform_hits:e.evaluated_draws/10000,
    late_cohort:{
      first_round:5001,last_round:last,evaluated_draws:n,
      model_metrics:models.map(model=>({
        model,straight_hits:0,mean_log_score_edge_vs_uniform:0,
        mean_brier_edge_vs_uniform:0
      })),
      repeatedly_inspected_not_independent_holdout:true,
    },
    recent_rounds:Array.from({length:12},(_,i)=>({
      round:last-i,draw_date:'2026-10-30',
      data_cutoff_round:last-i-1,
      selected_number:'1234',selected_model:'uniform',
      actual:'9999',selected_hit:false,
      uniform_number:'1234',uniform_hit:false,
    })),
    all_rounds_checked_against_archive:true,
    independently_verified_prepublished_forecasts:false,
    bank_primary_all_rounds_verified:false,
    prediction_skill_confirmed:false,
    automatic_model_promotion_authorized:false,
    actual_purchase:false
  };
  e.latest_verification=v;
  assert.doesNotThrow(()=>normalizeStatus(s));
  v.recent_rounds[0].selected_hit=true;
  assert.throws(()=>normalizeStatus(s),/最新の過去予測結果/);
  v.recent_rounds[0].selected_hit=false;
  v.bank_primary_all_rounds_verified=true;
  assert.throws(()=>normalizeStatus(s),/最新の過去予測結果/);
  v.bank_primary_all_rounds_verified=false;
  v.selected_straight_hits=v.evaluated_draws+1;
  assert.throws(()=>normalizeStatus(s),/最新の過去予測結果/);
});

test('latest historical verification UI has full-period, late-cohort and round-by-round tables',()=>{
  const html=readFileSync(new URL('../docs/index.html',import.meta.url),'utf8');
  const js=readFileSync(new URL('../docs/app.js',import.meta.url),'utf8');
  for(const id of [
    'replay-audit-generation','replay-audit-scope','replay-audit-hits',
    'replay-audit-uniform','replay-audit-difference','replay-audit-logscore',
    'replay-audit-expected','replay-audit-state','replay-audit-late-meta',
    'replay-audit-models','replay-audit-recent',
  ]){
    assert.ok(html.includes('id="'+id+'"'),id);
    assert.ok(js.includes('"'+id+'"'),id);
  }
  assert.ok(html.includes('後期区間のモデル別比較'));
  assert.ok(html.includes('最新12回の再予測照合'));
  assert.ok(html.includes('二次公開履歴に基づく後付け研究'));
  assert.ok(js.includes('create("tr")'));
});


test('current one-ticket research forecast is valid and its last-change state cannot claim issuance',()=>{
  const s=source();
  s.latest_research_forecast={
    version:'numbers4-latest-research-forecast-v1',
    source:'validated_research_evolution',
    target_round:7106,data_cutoff_round:7105,
    number:'2903',model:'rolling_250_alpha10',
    research_generation:12,
    computed_at_jst:'2026-11-02T07:30:00+09:00',
    last_changed_at_jst:'2026-11-02T07:40:00+09:00',
    changed_since_previous_snapshot:true,
    archive_git_blob_sha1:'a'.repeat(40),
    status:'research_only_not_issued_not_purchased',
    actual_purchase:false,officially_verified:false,
    prediction_skill_confirmed:false,
  };
  assert.doesNotThrow(()=>normalizeStatus(s));
  s.latest_research_forecast.number='29034';
  assert.throws(()=>normalizeStatus(s),/最新の研究予測/);
  s.latest_research_forecast.number='2903';
  s.latest_research_forecast.actual_purchase=true;
  assert.throws(()=>normalizeStatus(s),/最新の研究予測/);
  s.latest_research_forecast.actual_purchase=false;
  s.latest_research_forecast.data_cutoff_round=7106;
  assert.throws(()=>normalizeStatus(s),/最新の研究予測/);
  s.latest_research_forecast.data_cutoff_round=7105;
  s.latest_research_forecast.last_changed_at_jst='2099-01-01T00:00:00+09:00';
  assert.throws(()=>normalizeStatus(s),/最新の研究予測/);
});

test('open dashboard auto-updates changed research candidate and shows computation and change time',()=>{
  const html=readFileSync(new URL('../docs/index.html',import.meta.url),'utf8');
  const app=readFileSync(new URL('../docs/app.js',import.meta.url),'utf8');
  for(const id of ['latest-candidate-meta','latest-candidate-numbers',
                   'latest-candidate-source','latest-candidate-computed',
                   'latest-candidate-last-change','latest-candidate-change']){
    assert.ok(html.includes('id="'+id+'"'),id);
    assert.ok(app.includes('"'+id+'"'),id);
  }
  assert.ok(app.includes('data.latest_research_forecast'));
  assert.ok(app.includes('FORECAST_REFRESH_INTERVAL_MS=120_000'));
  assert.ok(app.includes('document.addEventListener("visibilitychange"'));
  assert.ok(html.includes('画面を開いたままでも2分おき'));
});


test('seven-day official versus retrospective table has bounded evidence and correct date window',()=>{
  const s=source();
  const end=new Date(Date.parse(s.generated_at_jst)+9*3600000).toISOString().slice(0,10);
  const start=new Date(Date.parse(end+'T00:00:00Z')-6*86400000).toISOString().slice(0,10);
  s.recent_week={
    version:'numbers4-recent-week-v1',days:7,start_date:start,end_date:end,
    issued_forecasts:[],shadow_forecasts:[],
    research_replay:[{
      round:7106,draw_date:'2026-11-03',data_cutoff_round:7105,
      number:'2903',model:'uniform',reference_result:'5870',
      straight_match:false,source_status:'secondary_history_not_officially_verified',
      issued_before_draw:false,actual_purchase:false
    }],
    officially_graded_issued:0,officially_matched_shadow:0,research_reference_matches:0
  };
  assert.doesNotThrow(()=>normalizeStatus(s));
  s.recent_week.research_replay[0].straight_match=true;
  assert.throws(()=>normalizeStatus(s),/直近7日間/);
  s.recent_week.research_replay[0].straight_match=false;
  s.recent_week.research_replay[0].issued_before_draw=true;
  assert.throws(()=>normalizeStatus(s),/直近7日間/);
  s.recent_week.research_replay[0].issued_before_draw=false;
  s.recent_week.research_replay[0].source_status='bank_primary_rakuten_publication_match';
  assert.throws(()=>normalizeStatus(s),/直近7日間/);
  s.recent_week.research_replay[0].source_status='secondary_history_not_officially_verified';
  s.recent_week.research_reference_matches=1;
  assert.throws(()=>normalizeStatus(s),/直近7日間/);
  s.recent_week.research_reference_matches=0;
  s.recent_week.issued_forecasts=[{
    round:7106,draw_date:'2026-11-03',numbers:['2903'],mode:'straight',
    issued_at_jst:'2026-11-03T16:00:00+09:00',
    winning_number:null,verification:'awaiting_two_source_match',
    ticket_results:null,actual_purchase:false
  }];
  assert.doesNotThrow(()=>normalizeStatus(s));
  s.recent_week.issued_forecasts[0].verification='bank_primary_rakuten_publication_match';
  assert.throws(()=>normalizeStatus(s),/直近7日間/);
  s.recent_week.issued_forecasts[0].verification='awaiting_two_source_match';
  s.recent_week.start_date='2026-10-01';
  assert.throws(()=>normalizeStatus(s),/直近7日間/);
});

test('weekly forecast comparison is prominent and both evidence classes have separate tables',()=>{
  const html=readFileSync(new URL('../docs/index.html',import.meta.url),'utf8');
  const app=readFileSync(new URL('../docs/app.js',import.meta.url),'utf8');
  for(const id of [
    'recent-week-forecast-audit','recent-week-window','recent-week-issued-count',
    'recent-week-shadow-count','recent-week-research-count',
    'recent-week-prospective-rows','recent-week-research-rows',
    'recent-week-evidence-note'
  ]){
    assert.ok(html.includes('id="'+id+'"'),id);
  }
  assert.ok(html.indexOf('id="recent-week-forecast-audit"')<
            html.indexOf('id="recursive-research-evolution"'));
  assert.ok(app.includes('data.recent_week'));
  assert.ok(app.includes('研究再現の一致を正式な予測精度へ加算しません'));
});

test('two-hour learning lag is safely displayed without granting model authority',()=>{
  const s=source();
  s.online_operations.state='secondary_publication_lag';
  s.online_operations.secondary_feed_status='secondary_mirror_lag_old_archive_preserved';
  assert.doesNotThrow(()=>normalizeStatus(s));
  s.online_operations.model_auto_promotion=true;
  assert.throws(()=>normalizeStatus(s),/オンライン本番監査/);
});

test('dashboard freshness follows 120-minute learning schedule plus 30-minute grace',()=>{
  const data=source();
  const original=Date.now;
  const base=Date.parse(data.generated_at_jst);
  try{
    Date.now=()=>base+145*60*1000;
    assert.equal(normalizeStatus(data).stale,false);
    Date.now=()=>base+151*60*1000;
    assert.equal(normalizeStatus(data).stale,true);
  }finally{
    Date.now=original;
  }
});
