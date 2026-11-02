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
  assert.equal(data.official_auto_fetch_enabled,false);
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
