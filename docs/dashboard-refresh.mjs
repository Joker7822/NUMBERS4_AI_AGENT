// Fetch independent public snapshots concurrently. Revalidate HTTP cache entries;
// never present a failed response as a successfully validated snapshot.
export async function loadPublicSnapshots(fetcher=globalThis.fetch, {timeoutMs=12000, timeoutSignal=ms=>AbortSignal.timeout(ms)}={}){
  const load=async path=>{
    const response=await fetcher(path,{cache:"no-cache",headers:{Accept:"application/json"},signal:timeoutSignal(timeoutMs)});
    if(!response.ok)throw new Error("HTTP "+response.status);
    return response.json();
  };
  const [status, integrated]=await Promise.allSettled([
    load("./data/status.json"),load("./data/integrated-research.json")
  ]);
  if(status.status==="rejected")throw status.reason;
  return {status:status.value,integrated};
}

export function createRefreshGate(task){
  let active=null;
  return {
    run(){
      if(active)return active;
      active=Promise.resolve().then(task).finally(()=>{active=null});
      return active;
    },
    get busy(){return active!==null}
  };
}

export function shouldAutoRefresh({hidden,busy,lastAttempt,now,interval}){
  return !hidden&&!busy&&(now-lastAttempt>=interval||now<lastAttempt);
}

// Only use finance records after the existing full status validator succeeds.
export function recoveryPercent(finance,ready){
  if(!ready||!finance||!Number.isSafeInteger(finance.simulated_ticket_cost_yen)||
     finance.simulated_ticket_cost_yen<=0||!Number.isSafeInteger(finance.simulated_payout_yen)||
     finance.simulated_payout_yen<0)return null;
  return 100*finance.simulated_payout_yen/finance.simulated_ticket_cost_yen;
}
