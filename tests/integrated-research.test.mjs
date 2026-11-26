import test from "node:test";
import assert from "node:assert/strict";
import {normalizeIntegratedResearch as normalize} from "../docs/integrated-research.mjs";
const a="a".repeat(40), b="b".repeat(40), c="c".repeat(40);
function fixture(){
  const reference={evaluated_rounds:7121,expected_gross_recovery_percent:47.8,simulated_loss_fraction:.8,simulations:10000};
  const risk={gross_recovery_percent:95.9,hypothetical_net_yen:-58300,maximum_settled_drawdown_yen:1408000,longest_consecutive_losing_purchased_tickets:7040};
  const models=names=>Object.fromEntries(names.map(n=>[n,{evaluated_draws:6122,mean_log_edge:0}]));
  const report={version:"numbers4-public-integrated-research-v1",scope:"secondary_history_only",actual_purchase:false,production_promotion_authorized:false,positive_expected_value_confirmed:false,purchase_decision:"SKIP",last_round:7122,last_draw_date:"2026-11-25",archive_git_blob_sha1:a,straight_payout_git_blob_sha1:b,box_payout_git_blob_sha1:c,straight_reference:{...reference},box_reference:{...reference},straight_risk:{...risk},box_risk:{...risk},payout_late_count:2122,payout_mae_yen:{expanding_mean:1,rolling_30:2,rolling_100:3},box_models:models(["uniform_ordered","dirichlet_100","dirichlet_1000","dirichlet_10000"]),ensemble_models:models(["uniform","equal_experts","uniform50","uniform90"])};
  const status={historical_archive:{last_round:7122,last_draw_date:"2026-11-25",git_blob_sha1:a},online_prequential_replay:{retrospective_finance:{payout_git_blob_sha1:b},retrospective_box_finance:{payout_git_blob_sha1:c}}};
  return {report,status};
}
test("accepts matching historical report",()=>{const {report,status}=fixture();assert.equal(normalize(report,status),report)});
test("rejects stale archive and payout hashes",()=>{const {report,status}=fixture();status.historical_archive.last_round++;assert.throws(()=>normalize(report,status));status.historical_archive.last_round--;status.online_prequential_replay.retrospective_finance.payout_git_blob_sha1=c;assert.throws(()=>normalize(report,status))});
test("rejects unsafe claims and malformed metrics",()=>{const {report,status}=fixture();report.actual_purchase=true;assert.throws(()=>normalize(report,status));report.actual_purchase=false;report.straight_reference.simulated_loss_fraction=2;assert.throws(()=>normalize(report,status))});
test("rejects missing replay provenance",()=>{const {report,status}=fixture();delete status.online_prequential_replay;assert.throws(()=>normalize(report,status))});
