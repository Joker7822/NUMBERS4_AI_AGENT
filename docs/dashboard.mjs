// Pure validator. Never interpret manually entered observations as auto-fetched official data.
export const VERSION="numbers4-dashboard-v1";
const safeDigits=n=>typeof n==="string"&&/^[0-9]{4}$/.test(n);
const safeTime=t=>typeof t==="string"&&!Number.isNaN(Date.parse(t))&&/[+-]\d\d:\d\d$/.test(t);
export function normalizeStatus(s){
  if(!s||s.version!==VERSION||s.product!=="Numbers4"||
      s.official_auto_fetch_enabled!==false||s.prediction_skill_confirmed!==false||
      s.automatic_model_promotion!==false||s.actual_purchase_profit_yen!==null||
      !safeTime(s.generated_at_jst)||!Number.isInteger(s.consistent_rounds)||
      !Number.isInteger(s.observed_rounds)||!Number.isInteger(s.issued_draws)||
      s.graded_issued_draws>s.issued_draws||!Number.isInteger(s.graded_issued_draws)||
      !Array.isArray(s.warnings)||s.warnings.some(x=>typeof x!=="string")||
      !["conflict","two_source_entered_consistent","no_corroborated_draws"].includes(s.source_status)){
    throw new Error("監査JSONの安全性・形式を確認できません");
  }
  const d=s.latest_consistent_draw;
  if(d&&(d.status!=="two_source_entered_consistent"||!safeDigits(d.winning_number)||
       !Number.isInteger(d.round)||typeof d.draw_date!=="string")){
    throw new Error("照合結果の形式が不正です");
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
  if(g&&(!d||g.verification!=="two_source_manual_attestations_consistent"||
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
  const ageMinutes=(Date.now()-Date.parse(s.generated_at_jst))/60000;
  return {...s,ageMinutes,stale:ageMinutes>90||ageMinutes< -5};
}
