import test from "node:test";
import assert from "node:assert/strict";
import {reconstruct,chartData,chartGeometry} from "../docs/cashflow-chart.mjs";
function fixture(){
  const f={simulated_ticket_cost_yen:600,simulated_payout_yen:1000,simulated_net_yen:400,historical_winning_draws:1,winning_rounds:[{round:3,straight_payout_yen:1000}]};
  const r={hypothetical_net_yen:400,maximum_settled_drawdown_yen:200,longest_consecutive_losing_purchased_tickets:1,gross_recovery_percent:100*1000/600};
  return {f,r};
}
test("exact path keeps prize and pre-prize balance and drawdown",()=>{
  const {f,r}=fixture();const data=reconstruct([[3,200,1000]],4,f,r,"straight");
  assert.deepEqual(data.balance,[[1,0],[2,-200],[3,600],[4,400]]);
  assert.deepEqual(data.drawdown,[[1,0],[2,200],[3,0],[4,200]]);
});
test("BOX skip is free and does not reset losing streak",()=>{
  const f={simulated_ticket_cost_yen:400,simulated_payout_yen:0,simulated_net_yen:-400,historical_winning_draws:0,winning_rounds:[],excluded_ineligible_tickets:1};
  const r={hypothetical_net_yen:-400,maximum_settled_drawdown_yen:400,longest_consecutive_losing_purchased_tickets:2,gross_recovery_percent:0};
  assert.deepEqual(reconstruct([[3,0,0]],4,f,r,"box").balance,[[1,0],[2,-200],[3,-200],[4,-400]]);
});
test("rejects missing or fabricated prizes, unordered exceptions, straight skips and mismatched risk",()=>{
  const {f,r}=fixture();
  for(const e of [[],[[3,200,999]],[[3,200,1000],[2,0,0]],[[2,0,0],[3,200,1000]],[[3,200,1000],[4,200,0]]])
    assert.throws(()=>reconstruct(e,4,f,r,"straight"));
  assert.throws(()=>reconstruct([[3,200,1000]],4,f,{...r,maximum_settled_drawdown_yen:201},"straight"));
});
test("linear losses compress without sampling and geometry includes zero",()=>{
  const f={simulated_ticket_cost_yen:2000,simulated_payout_yen:0,simulated_net_yen:-2000,historical_winning_draws:0,winning_rounds:[]};
  const r={hypothetical_net_yen:-2000,maximum_settled_drawdown_yen:2000,longest_consecutive_losing_purchased_tickets:10,gross_recovery_percent:0};
  const a=reconstruct([],11,f,r,"straight");assert.deepEqual(a.balance,[[1,0],[11,-2000]]);
  const g=chartGeometry([a.balance,a.balance],11);assert.equal(g.min,-2000);assert.equal(g.max,0);assert.equal(g.paths[0],g.paths[1]);
  assert.ok(!chartGeometry([[[1,0],[2,0]],[[1,0],[2,0]]],2).paths[0].includes("NaN"));
});
test("old projection fails chart only",()=>assert.throws(()=>chartData({},{})));
