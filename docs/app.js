import {normalizeStatus} from "./dashboard.mjs?v=20261102";
const byId=id=>document.getElementById(id);
const set=(id,value)=>{const n=byId(id);if(n)n.textContent=value==null?"—":String(value)};
const create=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!=null)n.textContent=String(text);return n};
const japaneseTime=t=>new Intl.DateTimeFormat("ja-JP",{timeZone:"Asia/Tokyo",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}).format(new Date(t))+" JST";
function render(data){
  set("draw-count",data.consistent_rounds);set("issue-count",data.issued_draws);set("graded-count",data.graded_issued_draws);
  const label=data.source_status==="conflict"?"ソース不一致":data.consistent_rounds?"2系統の手入力が一致":"抽せん結果未登録";
  set("status-pill",label);byId("status-pill").className="pill"+(data.source_status==="conflict"?" block":data.stale||!data.consistent_rounds?" warn":"");
  set("refresh-time","生成 "+japaneseTime(data.generated_at_jst)+(data.stale?"・監視更新遅延":""));
  const draw=data.latest_consistent_draw;
  set("draw-number",draw?draw.winning_number.split("").join(" "):"— — — —");
  set("draw-details",draw?`第${draw.round}回 ・ ${draw.draw_date} ・ みずほ銀行／宝くじ公式サイトの入力値が一致`:"照合一致した抽せん情報はまだありません。");
  const issued=data.published_forecast,holder=byId("issued-numbers");holder.replaceChildren();
  set("issued-meta",issued?`第${issued.target_round}回 / ${issued.draw_date} / ${issued.mode} / 発行: ${japaneseTime(issued.issued_at_jst)}`:"事前発行した予測はありません。研究候補は公開済みとして扱いません。");
  if(issued)for(const [i,num] of issued.numbers.entries()){
    const card=create("div","ticket");card.append(create("small","",`予測 ${i+1}`),create("strong","",num));holder.append(card);
  }
  const graded=data.latest_graded_issued_forecast,grades=byId("grades");grades.replaceChildren();
  set("grade-meta",graded?`第${graded.round}回 ・ 当せん番号 ${graded.winning_number} ・ 5口中 ${graded.winning_tickets}口一致 ・ 手動2ソース記録の一致`:"2ソース入力一致と抽せん前発行の両方を確認できる成績はまだありません。");
  if(graded)for(const t of graded.tickets){const c=create("div","grade");
    c.append(create("b","",t.number),create("small","","照合結果"),create("strong","",({straight:"ストレート",box:"ボックス",set_straight:"セット（ストレート）",set_box:"セット（ボックス）",miss:"不一致"})[t.result]));grades.append(c);
  }
  const research=data.historical_research||{};
  set("backtest-count",research.evaluated_draws+"回");set("backtest-hits",research.status==="historical_exploratory_only"?research.top5_straight_hit_draws+"回":"未検証");
  const warnings=byId("warning-list");warnings.replaceChildren();
  for(const warning of data.warnings)warnings.append(create("p","",warning));
  if(!data.warnings.length)warnings.append(create("p","ok","重大な入力不一致はありません。ただし予測精度は実証されていません。"));
}
export async function refresh(){
  const button=byId("refresh"),error=byId("error");button.disabled=true;error.hidden=true;
  try{
    const response=await fetch("./data/status.json?b="+Date.now(),{cache:"no-store",headers:{Accept:"application/json"}});
    if(!response.ok)throw new Error("HTTP "+response.status);
    render(normalizeStatus(await response.json()));
  }catch(e){error.textContent="公開データを取得・検証できません: "+String(e.message||e);error.hidden=false;
    set("status-pill","データ検証不可");byId("status-pill").className="pill block";
  }finally{button.disabled=false}
}
byId("refresh").addEventListener("click",refresh);refresh();
