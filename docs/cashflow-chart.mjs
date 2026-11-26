// Exact historical reconstruction from sparse exceptions to a 200-yen losing draw.
// Only invoked after both the main and integrated provenance validators succeed.
const int=x=>Number.isSafeInteger(x);
const fail=()=>{throw Error("仮想収支グラフの証拠が不一致です")};
const safe=x=>{if(!int(x))fail();return x};
function appendPoint(points,round,value){
  const a=points.at(-2),b=points.at(-1);
  if(a&&b&&(b[1]-a[1])*(round-b[0])===(value-b[1])*(b[0]-a[0]))points.pop();
  points.push([round,value]);
}
export function reconstruct(exceptions,last,finance,risk,mode){
  if(!["straight","box"].includes(mode)||!int(last)||last<2||last>100000||
     !Array.isArray(exceptions)||exceptions.length>last-1||!finance||!risk)fail();
  const wins=new Map();
  if(!Array.isArray(finance.winning_rounds))fail();
  for(const w of finance.winning_rounds){
    const prize=mode==="straight"?w.straight_payout_yen:w.hypothetical_box_payout_yen;
    if(!int(w.round)||w.round<2||w.round>last||wins.has(w.round)||!int(prize)||prize<=0)fail();
    wins.set(w.round,prize);
  }
  const e=new Map();let prior=1;
  for(const row of exceptions){
    if(!Array.isArray(row)||row.length!==3)fail();
    const [round,cost,award]=row;
    if(!int(round)||round<=prior||round>last||!int(award)||award<0||
       ![0,200].includes(cost)||(mode==="straight"&&cost!==200)||
       (cost===0&&award!==0)||(cost===200&&award===0)||
       award!==(wins.get(round)??0))fail();
    prior=round;e.set(round,[cost,award]);
  }
  let net=0,peak=0,maxDrawdown=0,spend=0,payout=0,skipped=0,hits=0,miss=0,maxMiss=0;
  const balance=[[1,0]],drawdown=[[1,0]];
  for(let round=2;round<=last;round++){
    const [cost,award]=e.get(round)??[200,0];
    if(award!==(wins.get(round)??0))fail();
    spend=safe(spend+cost);payout=safe(payout+award);net=safe(net+award-cost);
    peak=Math.max(peak,net);
    const dd=safe(peak-net);maxDrawdown=Math.max(maxDrawdown,dd);
    if(!cost)skipped++;
    else if(award){hits++;miss=0}
    else{miss++;maxMiss=Math.max(maxMiss,miss)}
    appendPoint(balance,round,net);appendPoint(drawdown,round,dd);
  }
  if(spend!==finance.simulated_ticket_cost_yen||payout!==finance.simulated_payout_yen||
     net!==finance.simulated_net_yen||net!==risk.hypothetical_net_yen||
     hits!==finance.historical_winning_draws||hits!==wins.size||
     maxDrawdown!==risk.maximum_settled_drawdown_yen||
     maxMiss!==risk.longest_consecutive_losing_purchased_tickets||
     (mode==="box"&&skipped!==finance.excluded_ineligible_tickets)||
     (spend===0?risk.gross_recovery_percent!==null:
       !Number.isFinite(risk.gross_recovery_percent)||Math.abs(100*payout/spend-risk.gross_recovery_percent)>1e-9))fail();
  return {balance,drawdown,net,maxDrawdown,skipped,hits};
}
export function chartData(report,status){
  const c=report.cashflow_chart,o=status.online_prequential_replay;
  if(!c||c.version!=="numbers4-cashflow-exceptions-v1"||c.first_round!==2||
     c.last_round!==report.last_round||c.default_cost_yen!==200||
     o?.tickets_per_draw!==1)fail();
  return {last:c.last_round,
    straight:reconstruct(c.straight,c.last_round,o.retrospective_finance,report.straight_risk,"straight"),
    box:reconstruct(c.box,c.last_round,o.retrospective_box_finance,report.box_risk,"box")};
}
export function chartGeometry(series,last){
  if(!int(last)||last<2||!Array.isArray(series)||series.length!==2)fail();
  const values=series.flatMap(s=>s.map(p=>p[1]));
  const lo=Math.min(0,...values),hi=Math.max(0,...values);
  const min=lo===hi?lo-1:lo,max=lo===hi?hi+1:hi;
  const x=r=>72+(r-1)/(last-1)*652;
  const y=v=>18+(max-v)/(max-min)*218;
  return {min,max,zero:y(0),paths:series.map(s=>s.map(([r,v],i)=>
    (i?"L":"M")+x(r).toFixed(2)+" "+y(v).toFixed(2)).join(" ")),
    ticks:[min,min+(max-min)/2,max].map(v=>({value:v,y:y(v)}))};
}
const NS="http://www.w3.org/2000/svg";
function node(doc,name,attrs={},label){
  const el=doc.createElementNS(NS,name);
  for(const [k,v] of Object.entries(attrs))el.setAttribute(k,String(v));
  if(label!==undefined)el.textContent=label;
  return el;
}
export function drawChart(container,data,key,label){
  const doc=container.ownerDocument;
  const g=chartGeometry([data.straight[key],data.box[key]],data.last);
  const svg=node(doc,"svg",{viewBox:"0 0 748 270",role:"img","aria-label":label});
  svg.append(node(doc,"title",{},label));
  for(const tick of g.ticks){
    svg.append(node(doc,"line",{x1:72,x2:724,y1:tick.y,y2:tick.y,class:"cashflow-grid"}),
      node(doc,"text",{x:64,y:tick.y+4,"text-anchor":"end",class:"cashflow-axis"},(tick.value/10000).toLocaleString("ja-JP",{maximumFractionDigits:1})+"万"));
  }
  svg.append(node(doc,"line",{x1:72,x2:724,y1:g.zero,y2:g.zero,class:"cashflow-zero"}));
  g.paths.forEach((d,i)=>svg.append(node(doc,"path",{d,fill:"none",class:i?"cashflow-box":"cashflow-straight"})));
  svg.append(node(doc,"text",{x:72,y:255,class:"cashflow-axis"},"第1回終了時（基準0）"),
    node(doc,"text",{x:724,y:255,"text-anchor":"end",class:"cashflow-axis"},"第"+data.last+"回"));
  container.replaceChildren(svg);
}
