import {normalizeStatus} from "./dashboard.mjs?v=20261102-production-online-monitor";
const byId=id=>document.getElementById(id);
const set=(id,value)=>{const n=byId(id);if(n)n.textContent=value==null?"—":String(value)};
const create=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!=null)n.textContent=String(text);return n};
const japaneseTime=t=>new Intl.DateTimeFormat("ja-JP",{timeZone:"Asia/Tokyo",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}).format(new Date(t))+" JST";
const yen=n=>typeof n==="number"?n.toLocaleString("ja-JP")+"円":"未算定";
function render(data){
  set("draw-count",data.consistent_rounds);set("issue-count",data.issued_draws);set("graded-count",data.graded_issued_draws);
  const label=data.source_status==="conflict"?"ソース不一致":data.auto_verified_rounds?"銀行＋販売元照合":data.consistent_rounds?"手入力2系統一致":"抽せん結果未登録";
  set("status-pill",label);byId("status-pill").className="pill"+(data.source_status==="conflict"?" block":data.stale||!data.consistent_rounds?" warn":"");
  set("refresh-time","生成 "+japaneseTime(data.generated_at_jst)+(data.stale?"・監視更新遅延":""));
  const draw=data.latest_consistent_draw;
  const secondary=data.latest_unverified_draw;
  const visible=draw||secondary;
  set("draw-number",visible?visible.winning_number.split("").join(" "):"— — — —");
  set("draw-details",draw?
    `第${draw.round}回 ・ ${draw.draw_date} ・ ${draw.status==="auto_verified_two_publishers"?"みずほ銀行＋楽天公開結果が一致":"2つの手入力記録が一致"}`:
    secondary?`第${secondary.round}回 ・ ${secondary.draw_date} ・ 楽天公表の参考番号【みずほ銀行未照合・正式採点不可】`:
    "照合一致した抽せん情報はまだありません。");
  const issued=data.published_forecast,holder=byId("issued-numbers");holder.replaceChildren();
  set("issued-meta",issued?`第${issued.target_round}回 / ${issued.draw_date} / ${issued.mode} / 発行: ${japaneseTime(issued.issued_at_jst)}`:"事前発行した予測はありません。研究候補は公開済みとして扱いません。");
  if(issued)for(const [i,num] of issued.numbers.entries()){
    const card=create("div","ticket");card.append(create("small","",`予測 ${i+1}`),create("strong","",num));holder.append(card);
  }
  const graded=data.latest_graded_issued_forecast,grades=byId("grades");grades.replaceChildren();
  set("grade-meta",graded?`第${graded.round}回 ・ 当せん番号 ${graded.winning_number} ・ ${graded.tickets.length}口中 ${graded.winning_tickets}口一致 ・ ${graded.verification==="bank_primary_rakuten_publication_match"?"銀行と楽天の自動照合":"手動2ソース記録の一致"}`:"2ソース入力一致と抽せん前発行の両方を確認できる成績はまだありません。");
  if(graded)for(const t of graded.tickets){const c=create("div","grade");
    c.append(create("b","",t.number),create("small","","照合結果"),create("strong","",({straight:"ストレート",box:"ボックス",set_straight:"セット（ストレート）",set_box:"セット（ボックス）",miss:"不一致"})[t.result]));grades.append(c);
  }
  const research=data.historical_research||{};
  const proof=data.historical_accuracy_proof;
  const archive=data.historical_archive;
  set("archive-count",archive?.status==="secondary_public_mirrors_agree_not_officially_verified"?
    archive.record_count.toLocaleString("ja-JP")+"回":"未登録");
  set("archive-scope",archive?.status==="secondary_public_mirrors_agree_not_officially_verified"?
    "第"+archive.first_round+"回（"+archive.first_draw_date+"）〜第"+archive.last_round+
    "回（"+archive.last_draw_date+"）・2公開リポジトリで数字一致。みずほ銀行公式との全件照合は未実施。"+
    " 予測の正式採点・精度実証には使用しません。":
    "第1回からの全回履歴はまだ登録されていません。");
  const live=data.online_prequential_replay;
  const oneReady=live?.status==='historical_walk_forward_reconstruction_only'&&live?.tickets_per_draw===1;
  set("online-replay-count",oneReady?
      live.evaluated_draws.toLocaleString('ja-JP')+'回':'未検証');
  const box=live?.retrospective_box_finance;
  const straight=live?.retrospective_finance;
  const financeReady=oneReady&&
    box?.status==='historical_simulation_only_not_actual_purchase';
  const straightReady=oneReady&&
    straight?.status==='historical_simulation_only_not_actual_purchase';
  set("online-replay-hits",financeReady&&straightReady?
      'ストレート '+straight.historical_winning_draws+'回 / ボックス '+
      box.historical_winning_draws+'回（'+box.historical_winning_tickets+'口）':
      '未検証');
  set("online-replay-edge",oneReady?
      '平均log-score差 '+live.selected_mean_log_score_edge_vs_uniform+
      ' / Brier改善 '+live.selected_mean_brier_improvement_vs_uniform:'未検証');
  const chance=live?.research_statistical_audit;
  set("online-replay-chance",oneReady&&chance?.scope==='descriptive_historical_reconstruction_not_preregistered'?
      '公平・独立な抽せんで同数以上当たる確率 '+(chance.selected_hit_tail_probability_given_uniform_null*100).toFixed(2)+
      '% / 統計モデル採用 '+chance.nonuniform_model_selected_rounds+'回（事前登録なし・予測力未実証）':
      '未集計（将来予測力は未実証）');
  const next=live?.next_research_candidate;
  const safeNext=next&&oneReady;
  set("online-next-candidate",safeNext?
      '第'+next.target_round+'回研究候補 '+next.numbers.join(' / ')+
      ' （'+next.model+'、第'+next.data_cutoff_round+'回まで使用、未発行・銀行未照合）':
      '正式な事前発行予測ではありません。');
  set("latest-candidate-meta",safeNext?
      '第'+next.target_round+'回向け / 第'+next.data_cutoff_round+'回までの結果から算出 / '+
      next.model+' / 研究専用・事前発行なし・購入なし':
      '研究予測をまだ生成していません。');
  const forecastGrid=byId("latest-candidate-numbers");forecastGrid.replaceChildren();
  if(safeNext)next.numbers.forEach((num,i)=>{
    const card=create("div","ticket");
    const eligible=new Set(num).size>1;
    card.append(create("small","", "共通研究候補 "+(i+1)),
                create("strong","",num),
                create("small","",eligible?"ストレート可・ボックス可":"ストレート可・ボックス不可（4桁同一）"));
    forecastGrid.append(card);
  });
  const f=box;
  set("simulation-scope",financeReady?
    "第"+f.first_evaluated_round+"〜"+f.last_evaluated_round+"回 / "+
    f.evaluated_rounds.toLocaleString("ja-JP")+
    "回。過去の1番号をボックス1口申込と仮定（購入不可の4桁同一は除外・代替候補なし）。1口200円、実購入なし。":
    "ボックス配当と過去予測の照合が未完了のため、仮想収支を表示できません。");
  set("simulation-box-tickets",financeReady?
    f.simulated_purchased_tickets.toLocaleString("ja-JP")+"口":"未算定");
  set("simulation-ineligible",financeReady?
    f.excluded_ineligible_tickets.toLocaleString("ja-JP")+"口":"未算定");
  set("simulation-box-wins",financeReady?
    f.historical_winning_draws+"回 / "+f.historical_winning_tickets+"口":"未算定");
  set("simulation-spend",financeReady?yen(f.simulated_ticket_cost_yen):"未算定");
  set("simulation-income",financeReady?yen(f.simulated_payout_yen):"未算定");
  set("simulation-net",financeReady?(f.simulated_net_yen>0?"+":"")+yen(f.simulated_net_yen):"未算定");
  set("simulation-roi",financeReady&&f.simulated_roi_percent!=null?
    f.simulated_roi_percent.toLocaleString("ja-JP")+"%":"未算定");
  set("simulation-baseline",financeReady?yen(f.baseline_simulated_net_yen):"未算定");
  set("actual-profit","購入記録なし・実収支は確認できません");
  const hitList=byId("historical-wins");hitList.replaceChildren();
  set("historical-wins-meta",financeReady?
    "第2回からの後付けボックス再現：一致"+f.historical_winning_draws+
    "回 / "+f.historical_winning_tickets+"口。各回最大1口だけを計上。実購入・当せん実績ではありません。":
    "ボックス配当と予測履歴を照合中です。");
  if(financeReady){
    if(!f.winning_rounds.length)hitList.append(create("p","subtle","ボックス一致した予測はありません。"));
    for(const entry of f.winning_rounds.slice().reverse()){
      const row=create("div","historical-hit");
      row.append(
        create("span","hit-round","第"+entry.round+"回 ・ "+entry.draw_date+" ・ 当せん番号 "+entry.winning_number),
        create("b","hit-number",entry.matched_tickets.map(t=>t.predicted_number).join(" / ")),
        create("span","hit-payout",entry.winning_ticket_count+"口 × "+yen(entry.box_payout_yen_per_ticket)+
          " = "+yen(entry.hypothetical_box_payout_yen))
      );
      hitList.append(row);
    }
  }
  set("simulation-straight-scope",straightReady?
    "第"+straight.first_evaluated_round+"〜"+straight.last_evaluated_round+"回 / "+
    straight.evaluated_rounds.toLocaleString("ja-JP")+
    "回。毎回ストレート1口を買ったと仮定した別シナリオ。ボックスの支出は含めません。":
    "ストレート配当と過去予測の照合が未完了です。");
  set("simulation-straight-wins",straightReady?
    straight.historical_winning_draws+"回 / "+straight.historical_winning_draws+"口":"未算定");
  set("simulation-straight-spend",straightReady?yen(straight.simulated_ticket_cost_yen):"未算定");
  set("simulation-straight-income",straightReady?yen(straight.simulated_payout_yen):"未算定");
  set("simulation-straight-net",straightReady?
    (straight.simulated_net_yen>0?"+":"")+yen(straight.simulated_net_yen):"未算定");
  set("simulation-straight-roi",straightReady?
    straight.simulated_roi_percent.toLocaleString("ja-JP")+"%":"未算定");
  set("simulation-straight-baseline",straightReady?
    yen(straight.baseline_simulated_net_yen):"未算定");
  set("actual-straight-profit","購入記録なし・実収支は確認できません");
  const straightList=byId("historical-straight-wins");straightList.replaceChildren();
  set("historical-straight-wins-meta",straightReady?
    "第2回からの後付けストレート再現：一致"+straight.historical_winning_draws+
    "回。順序までの完全一致のみ。実購入・当せん実績ではありません。":
    "ストレート配当と予測履歴を照合中です。");
  if(straightReady){
    if(!straight.winning_rounds.length)straightList.append(create("p","subtle","ストレート一致した予測はありません。"));
    for(const entry of straight.winning_rounds.slice().reverse()){
      const row=create("div","historical-hit");
      row.append(
        create("span","hit-round","第"+entry.round+"回 ・ "+entry.draw_date),
        create("b","hit-number",entry.matched_prediction),
        create("span","hit-payout",yen(entry.straight_payout_yen))
      );
      straightList.append(row);
    }
  }
  set("backtest-count",proof.evaluated_draws+"回");
  set("backtest-hits",proof.status==="historical_exploratory_only"?proof.top5_model_hits+"回":"未検証");
  set("backtest-scope",proof.status==="historical_exploratory_only"?
    "楽天公開履歴（銀行未照合）での過去研究。log-score差: "+String(proof.mean_log_likelihood_edge_vs_uniform)+
    "。将来予測力は未実証。":"真の結果履歴が不足しているため、予測精度の実証はできません。");
  const automated=data.auto_learning;
  const modelLabels={
    uniform:'一様基準（未昇格）',
    positional_60_alpha10:'桁別Dirichlet（直近60回）',
    positional_250_alpha5:'桁別Dirichlet（直近250回）',
    positional_1000_alpha20:'桁別Dirichlet（直近1,000回）'
  };
  const learningStatuses={
    no_shadow_forecasts:'待機：抽せん前の比較予測なし',
    evidence_integrity_blocked:'停止：証拠の不整合',
    insufficient_true_prospective_draws:'将来検証を蓄積中',
    eligible_under_preregistered_uniform_null:'昇格条件の統計判定に適合',
    no_confirmed_advantage:'優位性が確認できません'
  };
  set("auto-learning-status",automated?learningStatuses[automated.status]:"未登録");
  set("auto-learning-champion",automated?modelLabels[automated.active_champion]:"未登録");
  set("auto-learning-bank-count",automated?automated.officially_verified_training_rounds+"回":"未確認");
  set("auto-learning-witnesses",automated?automated.pre_draw_github_witnesses+"件":"未確認");
  set("auto-learning-prospective",automated?
      automated.eligible_prospective_draws+" / "+automated.required_prospective_draws+"回":"未確認");
  set("auto-learning-promotion",automated?
      (data.automatic_model_promotion?"検証条件付きの自動昇格が有効":
       "未昇格・一様基準維持"+(automated.integrity_blocker?"（証拠不足で停止）":"")):"未登録");
  const ops=data.online_operations;
  const states={
    online_monitoring_active_secondary_research_only:"公式ルール監視正常・二次履歴研究運用中",
    manual_review_required:"公式ルール要確認（変更の疑い）",
    source_unavailable:"公開元取得不能・確認保留",
    stale:"定期監査の更新が遅延",
    not_verified:"初回監査待ち"
  };
  set("ops-state",ops?states[ops.state]:"監査データ未登録");
  set("ops-rules",ops?ops.rule_sources_consistent+"/"+ops.rule_sources_required+"件一致（必須文言）":"未検査");
  set("ops-last-rules",ops?.rule_checked_at_jst?japaneseTime(ops.rule_checked_at_jst):"確認できません");
  const statusMap={
    not_checked:"未検査",
    validated_no_new_draws:"二次公開元一致・新規なし",
    appended_secondary_history_not_officially_verified:"二次公開元一致・履歴追記",
    network_unavailable_old_archive_preserved:"取得失敗・旧履歴維持"
  };
  set("ops-source-status",ops?statusMap[ops.secondary_feed_status]:"確認できません");
  set("ops-last-feed",ops?.secondary_checked_at_jst?japaneseTime(ops.secondary_checked_at_jst):"確認できません");
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
