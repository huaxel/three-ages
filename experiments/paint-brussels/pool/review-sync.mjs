import {validatePool,validateReviewEvent,canonicalReviewEvent,POOL_ID} from './contract.mjs';
const keyOf=e=>`${e.poolId}\0${e.id}`;
const localKey=e=>`${e.version===2?"brussels-shortlist-v2":"brussels-painter-preferences-v1"}:${e.poolId}:event:${e.id}`;
const errorWith=(message,status)=>Object.assign(new Error(message),{status});
export function createReviewSync({pool,storage=null,fetchImpl=globalThis.fetch,onRemote=()=>{},onState=()=>{},retryMs=2000,pollMs=20000}={}){
 validatePool(pool);const storedKeys=new Map(),photoKey=e=>`brussels-persona-photo-v2:${e.poolId}:event:${e.id}`,keyFor=e=>storedKeys.get(keyOf(e))??(e.version===2&&e.poolId===pool.id&&pool.experiment?.geometryPolicy==='independent-photo-interpretation'?photoKey(e):localKey(e));const all=new Map(),foreign=new Map(),acked=new Map(),errors=new Map(),bad=new Map(),volatile=new Set(),pools=new Map([[pool.id,Promise.resolve(pool)]]);
 let token=null,sessionJob=null,active=false,timer=null,job=null,rerun=false,online=false,backupAvailable=!!storage,lastError='',scanFailure='',backoff=retryMs;
 function snapshot(){let pending=foreign.size,unprotected=0;for(const [k,e]of all)if(acked.get(k)!==canonicalReviewEvent(e)){pending++;if(volatile.has(k))unprotected++;}return {online,pending,failed:errors.size+bad.size+(scanFailure?1:0),unprotected,backupAvailable,error:lastError,currentSaved:[...acked.keys()].filter(k=>k.startsWith(pool.id+'\0')).length,busy:!!job};}
 const emit=()=>onState(snapshot());
 function remember(event,{persist=false}={}){
  const key=keyOf(event),canonical=canonicalReviewEvent(event),old=all.get(key);
  if(old&&canonicalReviewEvent(old)!==canonical){errors.set(key,'Conflicting copies of one choice were preserved');return false;}
  all.set(key,JSON.parse(canonical));
  if(persist){try{if(!storage)throw Error('Browser backup unavailable');const previous=storage.getItem(keyFor(event));if(previous!==null&&canonicalReviewEvent(JSON.parse(previous))!==canonical)throw Error('Existing browser choice differs');if(previous===null)storage.setItem(keyFor(event),canonical);volatile.delete(key);}catch{backupAvailable=false;if(acked.get(key)!==canonical)volatile.add(key);}}
  return true;
 }
 function scan(){
  bad.clear();scanFailure='';if(!storage){backupAvailable=false;return;}
  try{const keys=Array.from({length:storage.length},(_,i)=>storage.key(i)).filter(k=>/^(?:brussels-painter-preferences-v1|brussels-shortlist-v2|brussels-persona-photo-v2):pool-\d{13}-[a-f0-9]{8}:event:/.test(k??''));if(keys.length>10000)throw Error('Browser review budget exceeded');
   for(const key of keys){let raw;try{raw=storage.getItem(key);if(!raw||raw.length>12000)throw Error('Invalid stored size');const e=JSON.parse(raw);if(!POOL_ID.test(e.poolId)||!(key===localKey(e)||e.version===2&&key===photoKey(e)))throw Error('Wrong storage key');storedKeys.set(keyOf(e),key);if(e.poolId===pool.id){validateReviewEvent(e,pool);if(!remember(e))bad.set(key,{key,raw});}else if(!all.has(keyOf(e)))foreign.set(keyOf(e),e);}catch{bad.set(key,{key,raw});}}
  }catch{backupAvailable=false;scanFailure='Browser backup could not be read; its original entries were not changed';lastError=scanFailure;}
 }
 async function request(url,options={}){const response=await fetchImpl(url,{...options,signal:AbortSignal.timeout(5000),cache:'no-store'});let result;try{result=await response.json();}catch{throw errorWith('Invalid server response',response.status);}if(!response.ok)throw errorWith(result.error??'Review request failed',response.status);return result;}
 async function session(){if(!sessionJob)sessionJob=request('/api/review/session').then(r=>{if(r.version!==1||! /^[a-f0-9]{64}$/.test(r.token))throw Error('Invalid review session');token=r.token;}).finally(()=>sessionJob=null);return sessionJob;}
 async function api(url,options={},renew=true){if(!token)await session();try{return await request(url,{...options,headers:{...options.headers,'X-Review-Token':token}});}catch(e){if(e.status===403&&renew){token=null;await session();return api(url,options,false);}throw e;}}
 async function manifest(id){if(typeof id!=='string'||id!==id.trim()||!POOL_ID.test(id))throw errorWith('Invalid saved pool ID',400);if(!pools.has(id)){const promise=request(`/pool/${id}.json`).then(validatePool).then(p=>{if(p.id!==id)throw Error('Wrong pool identity');return p;}).catch(e=>{pools.delete(id);throw e;});pools.set(id,promise);}return pools.get(id);}
 function receipt(r,p){if(r?.version!==1||typeof r.receivedAt!=='string'||!Number.isFinite(Date.parse(r.receivedAt))||! /^[a-f0-9]{64}$/.test(r.sha256??''))throw Error('Invalid saved receipt');validateReviewEvent(r.event,p);return r.event;}
 async function pull(){const result=await api(`/api/review/events?pool=${pool.id}`);if(result.version!==1||result.poolId!==pool.id||!Array.isArray(result.receipts)||result.receipts.length>5000)throw Error('Invalid review history');
  const events=result.receipts.map(r=>receipt(r,pool)),accepted=[];
  for(const key of acked.keys())if(key.startsWith(pool.id+'\0'))acked.delete(key);
  for(const e of events){const key=keyOf(e);if(remember(e)){acked.set(key,canonicalReviewEvent(e));errors.delete(key);volatile.delete(key);remember(e,{persist:true});accepted.push(e);}}
  for(const [key,e]of all)if(e.poolId===pool.id&&!acked.has(key)){try{if(!storage)throw Error('No backup');const raw=storage.getItem(keyFor(e));if(raw===null)throw Error('No backup');const backup=JSON.parse(raw);validateReviewEvent(backup,pool);if(canonicalReviewEvent(backup)!==canonicalReviewEvent(e))throw Error('Different backup');volatile.delete(key);}catch{volatile.add(key);}}
  onRemote(accepted);online=true;
 }
 function schedule(ms){if(!active)return;clearTimeout(timer);timer=setTimeout(()=>{timer=null;void flush();},ms);}
 async function pass(){
  scan();await pull();
  for(const [key,e]of foreign){if(errors.has(key))continue;try{const p=await manifest(e.poolId);try{validateReviewEvent(e,p);}catch{throw errorWith('Saved choice does not match its original pool',400);}remember(e);foreign.delete(key);}catch(error){if([400,404].includes(error.status)){errors.set(key,error.message);continue;}throw error;}}
  for(const [key,e]of all){if(acked.get(key)===canonicalReviewEvent(e)||errors.has(key))continue;
   try{const p=await manifest(e.poolId);try{validateReviewEvent(e,p);}catch{throw errorWith('Saved choice does not match its original pool',400);}const saved=await api('/api/review/events',{method:'POST',headers:{'Content-Type':'application/json'},body:canonicalReviewEvent(e)}),echo=receipt(saved,p);
    if(keyOf(echo)!==key||canonicalReviewEvent(echo)!==canonicalReviewEvent(e))throw Error('Server receipt does not match the submitted choice');
    acked.set(key,canonicalReviewEvent(e));volatile.delete(key);errors.delete(key);emit();
   }catch(error){if([400,404,409,413,415,507].includes(error.status)||error.message?.startsWith('Invalid preference')||error.message?.startsWith('Preference points')){errors.set(key,error.message);lastError='Some choices need attention; no existing copy was overwritten';emit();continue;}throw error;}
  }
  online=true;lastError=errors.size||bad.size||scanFailure?'Some saved choices could not sync; their original copies are preserved':'';backoff=retryMs;
 }
 async function flush(){if(!active)return;if(job){rerun=true;return job.catch(()=>{});}clearTimeout(timer);job=pass();emit();
  try{await job;}catch{online=false;lastError='Server unreachable — choices remain queued for retry';backoff=Math.min(Math.max(retryMs,backoff*2),30000);}
  finally{job=null;emit();if(rerun){rerun=false;schedule(0);}else schedule(online?pollMs:backoff);}
 }
 scan();emit();
 return {
  localEvents:()=>[...all.values()].filter(e=>e.poolId===pool.id),state:snapshot,recovery:()=>[...(scanFailure?[{error:scanFailure}]:[]),...bad.values(),...[...foreign].filter(([key])=>errors.has(key)).map(([,e])=>({key:keyFor(e),raw:JSON.stringify(e)}))],
  async start(){active=true;try{await pull();}catch{online=false;lastError='Server unreachable — choices will queue here until it returns';}emit();schedule(0);},
  queue(value){validateReviewEvent(value,pool);const e=JSON.parse(canonicalReviewEvent(value));if(!remember(e,{persist:true}))throw Error('Conflicting event ID');emit();schedule(0);},
  scan(){scan();emit();schedule(0);},
  async retry(){errors.clear();token=null;lastError='';await flush();},
  stop(){active=false;clearTimeout(timer);},flush,
 };
}
