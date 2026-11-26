import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {loadPublicSnapshots,createRefreshGate,shouldAutoRefresh,recoveryPercent} from "../docs/dashboard-refresh.mjs";
const response=value=>({ok:true,json:async()=>value});
test("two stable snapshot URLs start concurrently and request revalidation",async()=>{
  const calls=[],pending=[];
  const fetcher=(url,options)=>new Promise(resolve=>{calls.push({url,options});pending.push(resolve)});
  const result=loadPublicSnapshots(fetcher);
  assert.equal(calls.length,2);
  assert.deepEqual(calls.map(x=>x.url),["./data/status.json","./data/integrated-research.json"]);
  assert.ok(calls.every(x=>x.options.cache==="no-cache"&&x.options.signal instanceof AbortSignal));
  pending[1](response({audit:1}));pending[0](response({main:1}));
  assert.deepEqual(await result,{status:{main:1},integrated:{status:"fulfilled",value:{audit:1}}});
});
test("integrated failure does not suppress validated main input; main failure rejects",async()=>{
  const fetcher=async path=>path.includes("integrated")?{ok:false,status:404}:response({main:1});
  const r=await loadPublicSnapshots(fetcher);
  assert.deepEqual(r.status,{main:1});assert.equal(r.integrated.status,"rejected");
  await assert.rejects(loadPublicSnapshots(async()=>({ok:false,status:503})),/503/);
});
test("invalid JSON and timeout reject; integrated failure remains isolated",async()=>{
  const broken=async path=>path.includes("status")?{ok:true,json:async()=>{throw Error("bad JSON")}}:response({});
  await assert.rejects(loadPublicSnapshots(broken),/bad JSON/);
  const timed=(path,{signal})=>new Promise((resolve,reject)=>{
    if(path.includes("status"))resolve(response({}));
    else signal.addEventListener("abort",()=>reject(Error("timeout")),{once:true});
  });
  const controller=new AbortController();
  const pending=loadPublicSnapshots(timed,{timeoutSignal:()=>controller.signal});
  controller.abort();
  assert.equal((await pending).integrated.status,"rejected");
});
test("refresh gate coalesces triggers and releases after failure",async()=>{
  let calls=0,release;
  const g=createRefreshGate(()=>{calls++;return new Promise((resolve,reject)=>{release=reject})});
  const a=g.run(),b=g.run();assert.equal(a,b);assert.equal(g.busy,true);
  await Promise.resolve();assert.equal(calls,1);
  release(Error("failed"));await assert.rejects(a,/failed/);assert.equal(g.busy,false);
  const next=g.run();await Promise.resolve();assert.equal(calls,2);release(Error("again"));await assert.rejects(next,/again/);
});
test("auto refresh respects hidden tabs, active requests and cadence",()=>{
  const state={hidden:false,busy:false,lastAttempt:1000,now:121000,interval:120000};
  assert.equal(shouldAutoRefresh(state),true);
  assert.equal(shouldAutoRefresh({...state,hidden:true}),false);
  assert.equal(shouldAutoRefresh({...state,busy:true}),false);
  assert.equal(shouldAutoRefresh({...state,now:120999}),false);
  assert.equal(shouldAutoRefresh({...state,now:999}),true);
});
test("gross recovery is distinct from net ROI, and missing or zero cost is unknown",()=>{
  const f={simulated_ticket_cost_yen:200,simulated_payout_yen:100,simulated_net_yen:-100,simulated_roi_percent:-50};
  assert.equal(recoveryPercent(f,true),50);assert.equal(recoveryPercent(f,false),null);
  assert.equal(recoveryPercent({...f,simulated_ticket_cost_yen:0},true),null);
  assert.equal(recoveryPercent({...f,simulated_payout_yen:0},true),0);
});
test("overview precedes detail, fragment targets exist, and failed main render hides evidence",()=>{
  const html=readFileSync(new URL("../docs/index.html",import.meta.url),"utf8");
  const app=readFileSync(new URL("../docs/app.js",import.meta.url),"utf8");
  const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(x=>x[1]);
  assert.equal(ids.length,new Set(ids).size);
  for(const [,id] of html.matchAll(/href="#([^"]+)"/g))assert.ok(ids.includes(id),id);
  assert.ok(html.indexOf('id="overview"')<html.indexOf('id="recent-week-forecast-audit"'));
  assert.ok(html.includes('id="dashboard-content" hidden'));
  assert.ok(app.includes("content.hidden=true"));assert.ok(app.includes("content.hidden=false"));
  assert.ok(app.includes("normalizeIntegratedResearch(result.value,status)"));
});
