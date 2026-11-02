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
  s.historical_archive={
    status:'secondary_public_mirrors_agree_not_officially_verified',
    record_count:7104,first_round:1,last_round:7104,
    first_draw_date:'1994-10-07',last_draw_date:'2026-10-30',
    latest_number:'5805',officially_verified:false,
    forecast_grading_authorized:false,source_independence_not_established:true,
    git_blob_sha1:'b85c1d9fe3cb4899446d8ef0269d9fb3e2cd7466'
  };
  const valid=normalizeStatus(s);
  assert.equal(valid.historical_archive.record_count,7104);
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
  const total=online.evaluated_draws*1000;
  online.selected_top5_straight_hits=1;
  const payout=900000;
  online.retrospective_finance={
    version:'numbers4-retrospective-straight-five-finance-v1',
    status:'historical_simulation_only_not_actual_purchase',
    ticket_type:'straight',tickets_per_draw:5,ticket_unit_cost_yen:200,
    first_evaluated_round:2,last_evaluated_round:online.last_evaluated_round,
    evaluated_rounds:online.evaluated_draws,historical_winning_draws:1,
    simulated_ticket_cost_yen:total,simulated_payout_yen:payout,
    simulated_net_yen:payout-total,
    simulated_roi_percent:Math.round(1000000*(payout-total)/total)/10000,
    baseline_winning_draws:online.uniform_reference_top5_straight_hits,
    baseline_simulated_payout_yen:2200000,
    baseline_simulated_net_yen:2200000-total,
    winning_rounds:[{
      round:3,draw_date:'1994-10-21',winning_number:'0097',
      matched_prediction:'0097',ticket_position:3,selected_model:'uniform',
      straight_payout_yen:payout,hypothetical_ticket_cost_yen:1000,
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
  const bought=online.evaluated_draws*5-2;
  const spend=bought*200;
  const payout=84000;
  online.retrospective_box_finance={
    version:'numbers4-retrospective-box-five-finance-v1',
    status:'historical_simulation_only_not_actual_purchase',
    ticket_type:'box',requested_tickets_per_round:5,ticket_unit_cost_yen:200,
    evaluated_rounds:online.evaluated_draws,first_evaluated_round:2,
    last_evaluated_round:online.last_evaluated_round,
    simulated_purchased_tickets:bought,excluded_ineligible_tickets:2,
    historical_winning_draws:1,historical_winning_tickets:2,
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
      matched_tickets:[{ticket_position:1,predicted_number:'7594'},
                       {ticket_position:2,predicted_number:'9475'}],
      winning_ticket_count:2,box_payout_yen_per_ticket:42000,
      hypothetical_box_payout_yen:84000,
      status:'retrospective_simulated_box_win_not_actual_purchase'
    }],
    payout_git_blob_sha1:'fddbb69e36a70103733e8e55a351b66187fac70c',
    payout_source_status:'single_secondary_publisher_not_bank_verified',
    bank_primary_payouts_verified:false,
    actual_purchase_records_present:false,
    actual_spend_yen:null,actual_income_yen:null,actual_profit_yen:null,
    original_predictions_unchanged:true,production_promotion_authorized:false
  };
  assert.equal(normalizeStatus(s).online_prequential_replay.retrospective_box_finance.historical_winning_tickets,2);
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
