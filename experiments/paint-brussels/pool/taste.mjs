import {validatePool,pairPlan,validateVote,canonicalVote,reference,POOL_ID} from './pool/contract.mjs';
import {createReviewSync} from './pool/review-sync.mjs';
const $=id=>document.getElementById(id),rail=$('art-rail');
let pool,pairs=[],records=[],index=0,pairReady=false,generation=0,phase='taste',pick=null,draftNote='',sync,heldSource=false,toastTimer,readyTimer,lastState={pending:0,failed:0,unprotected:0,online:false},previousIndex=0,imageError='';
const drafts=new Map(),labels={a:'A',b:'B',tie:'both',neither:'neither'};
const latest=pair=>records.filter(r=>r.pairId===pair?.id).at(-1);
function merge(events){for(const e of events)if(!records.some(r=>r.id===e.id))records.push(e);records.sort((a,b)=>a.at.localeCompare(b.at)||a.id.localeCompare(b.id));updateProgress();}
function updateProgress(){if(!pool)return;const visited=new Set(records.map(r=>r.pairId)).size;$('progress').textContent=`${Math.min(index+1,pairs.length)} / ${pairs.length} · ${visited} reviewed`;$('progress-fill').style.width=`${visited/pairs.length*100}%`;const bar=document.querySelector('[role=progressbar]');bar.setAttribute('aria-valuemax',String(pairs.length));bar.setAttribute('aria-valuenow',String(visited));}
function updateStatus(state){lastState=state;let text,kind;
 if(state.failed){text=`${state.failed} need attention`;kind='attention';}
 else if(state.pending){text=state.online?'Saving…':`${state.pending} queued`;kind=state.online?'saving':'offline';}
 else if(state.online){text=state.currentSaved?'Saved to server':'Autosave on';kind='saved';}
 else{text='Offline · local backup';kind='offline';}
 $('sync-label').textContent=text;$('sync-status').dataset.state=kind;
 $('sync-detail').textContent=state.failed?'Some entries could not be reconciled. Original browser and server copies are preserved. Retry or download a recovery copy; nothing has been overwritten.':state.pending?`${state.pending} choice${state.pending===1?'':'s'} waiting for the server. ${state.unprotected?'Browser backup is unavailable: keep this tab open until saving succeeds.':'Your browser keeps a backup and retries automatically when the connection returns.'}`:state.online?'Your choices have reached this private server. You can close this tab or continue on another device connected to the same server.':'The server is not reachable yet. Choices can still queue here; saving retries automatically.';
 $('notice').hidden=!(imageError||state.unprotected||state.failed);$('notice').textContent=imageError|| (state.unprotected?'Keep this tab open: some choices have neither a browser backup nor a server receipt.':state.failed?'Some saved entries need attention. Open the saving indicator for details.':'');
 $('recovery').hidden=!sync?.recovery().length;
 $('finished-save').textContent=state.pending||state.failed?$('sync-detail').textContent:state.online?'Everything is saved on the server. Nothing to export.':'Your browser backup will sync when the server returns.';
 $('finished-retry').hidden=!(state.pending||state.failed||!state.online);
 if(window.tasteStudy)window.tasteStudy.sync=state;
}
function setEnabled(){for(const b of document.querySelectorAll('[data-preference],[data-fidelity],#skip,#continue'))b.disabled=!pairReady;$('source-open').disabled=!pairReady;}
function setPhase(next){phase=next;const fidelity=phase==='fidelity';$('taste-choices').hidden=fidelity;$('fidelity-choices').hidden=!fidelity;$('change-taste').hidden=!fidelity;
 $('step-label').textContent=fidelity?`02 / YOU WOULD KEEP ${labels[pick]?.toUpperCase()}`:'01 / THE FEELING';
 $('question').textContent=fidelity?'Which keeps the building’s character?':'Which would you keep?';
 $('choice-hint').textContent=fidelity?'One more tap to save. Unsure is welcome.':'Two taps. No right answer.';
 for(const figure of document.querySelectorAll('figure[data-side]'))figure.dataset.picked=String(fidelity&&figure.dataset.side===pick);
 if(window.tasteStudy)window.tasteStudy.phase=phase;
}
function rememberDraft(){if(pairs[index])drafts.set(pairs[index].id,{pick,note:draftNote,phase});}
function setView(side,{smooth=true}={}){const node=document.querySelector(`figure[data-side=${side}]`);if(matchMedia('(max-width:700px)').matches)rail.scrollTo({left:Math.max(0,node.offsetLeft-rail.offsetLeft-(rail.clientWidth-node.clientWidth)/2),behavior:smooth&&!matchMedia('(prefers-reduced-motion:reduce)').matches?'smooth':'auto'});for(const s of ['a','b'])$(`view-${s}`).setAttribute('aria-pressed',String(s===side));}
rail.addEventListener('scroll',()=>{if(!matchMedia('(max-width:700px)').matches)return;const center=rail.getBoundingClientRect().left+rail.clientWidth/2;let nearest='a',distance=Infinity;for(const node of rail.querySelectorAll('figure')){const r=node.getBoundingClientRect(),d=Math.abs(r.left+r.width/2-center);if(d<distance){distance=d;nearest=node.dataset.side;}}for(const s of ['a','b'])$(`view-${s}`).setAttribute('aria-pressed',String(s===nearest));},{passive:true});
function zoom(src,title,{source=false}={}){if(!pairReady)return;$('zoom-image').src=src;$('zoom-image').alt=title;$('zoom-title').textContent=title;$('source-credit').hidden=!source;if(!$('zoom').open)$('zoom').showModal();}
function show(){
 imageError='';pairReady=false;const current=++generation;clearTimeout(readyTimer);setEnabled();$('toast').hidden=true;
 window.tasteStudy={...window.tasteStudy,index,pairId:pairs[index]?.id??null,sourceId:pairs[index]?.sourceId??null,pairReady:false};
 const done=index>=pairs.length;$('review').hidden=done;$('finished').hidden=!done;$('loading').hidden=true;
 const query=new URLSearchParams(location.search);query.set('pool',pool.id);query.set('pair',done?'done':String(index+1));history.replaceState(null,'',`${location.pathname}?${query}`);
 if(done){$('finished-count').textContent=`${new Set(records.map(r=>r.pairId)).size} of ${pairs.length} comparisons reviewed. Thank you for looking closely.`;updateStatus(lastState);window.tasteStudy.phase='finished';return;}
 const pair=pairs[index],source=pool.sources.find(s=>s.id===pair.sourceId),prior=latest(pair),draft=drafts.get(pair.id);
 pick=draft?.pick??null;draftNote=draft?.note??prior?.note??'';$('note').value=draftNote;$('note-open').textContent=draftNote?'● Note':'＋ Note';
 $('previous-choice').hidden=!prior;$('previous-choice').textContent=prior?`Previously: ${prior.preference==='skip'?'passed':labels[prior.preference]}. Editing keeps the earlier decision too.`:'';
 $('continue').hidden=!prior;$('previous').disabled=index===0;$('source-title').textContent=source.title;$('source').src=`/pool-data/${pool.id}/sources/${source.id}.jpg`;$('source').alt=source.title;$('source-credit').href=source.post;
 for(const side of ['a','b']){const c=pair[side],base=`/pool-data/${pool.id}/candidates/${c.id}/r${c.revision}`;$(`painting-${side}`).src=base+'/render.png';$(`code-${side}`).href=base+'/program.js';}
 setPhase(draft?.phase==='fidelity'&&pick?'fidelity':'taste');updateProgress();setView('a',{smooth:false});
 // Readiness and a brief transition guard prevent stale-pixel and double-tap votes.
 Promise.all(['source','painting-a','painting-b'].map(id=>$(id).decode())).then(()=>{if(current!==generation)return;readyTimer=setTimeout(()=>{if(current!==generation)return;pairReady=true;setEnabled();window.tasteStudy.pairReady=true;},140);}).catch(()=>{if(current===generation){$('notice').hidden=false;imageError='An image could not load. Reload before choosing; no judgment has been recorded.';updateStatus(lastState);}});
 for(const next of pairs.slice(index+1,index+3))for(const side of ['a','b']){const c=next[side],img=new Image();img.src=`/pool-data/${pool.id}/candidates/${c.id}/r${c.revision}/render.png`;}
}
function chooseTaste(value){if(!pairReady||phase!=='taste'||document.querySelector('dialog[open]'))return;pick=value;setPhase('fidelity');rememberDraft();}
function advance(){for(let step=1;step<=pairs.length;step++){const next=(index+step)%pairs.length;if(!latest(pairs[next])){index=next;show();return;}}index=pairs.length;show();}
function record(preference,fidelity){if(!pairReady)return;const pair=pairs[index],source=pool.sources.find(s=>s.id===pair.sourceId),id=Array.from(crypto.getRandomValues(new Uint8Array(16)),v=>v.toString(16).padStart(2,'0')).join('');
 const event=validateVote({version:1,id,at:new Date().toISOString(),poolId:pool.id,pairId:pair.id,sourceId:source.id,sourceSha256:source.sha256,a:reference(pair.a),b:reference(pair.b),preference,fidelity,note:draftNote},pool);
 sync.queue(event);merge([event]);drafts.delete(pair.id);previousIndex=index;advance();
 $('toast').querySelector('span').textContent=lastState.pending?'Choice queued':'Choice saved';$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,3200);
}
function chooseFidelity(value){if(!pairReady||phase!=='fidelity'||!pick||document.querySelector('dialog[open]'))return;record(pick,value);}
for(const b of document.querySelectorAll('[data-preference]'))b.onclick=()=>chooseTaste(b.dataset.preference);
for(const b of document.querySelectorAll('[data-fidelity]'))b.onclick=()=>chooseFidelity(b.dataset.fidelity);
$('change-taste').onclick=()=>{pick=null;setPhase('taste');rememberDraft();};
$('source-open').onclick=()=>zoom($('source').src,$('source-title').textContent,{source:true});
for(const side of ['a','b']){$(`inspect-${side}`).onclick=()=>zoom($(`painting-${side}`).src,`Painting ${side.toUpperCase()}`);$(`view-${side}`).onclick=()=>setView(side);}
$('close-zoom').onclick=()=>$('zoom').close();$('about-open').onclick=()=>{$('details').showModal();};$('sync-status').onclick=()=>{$('details').showModal();};$('close-details').onclick=()=>$('details').close();
$('note-open').onclick=()=>{$('notes').showModal();$('note').focus();};$('note').oninput=()=>{draftNote=$('note').value;$('note-open').textContent=draftNote?'● Note':'＋ Note';rememberDraft();};$('close-note').onclick=()=>$('notes').close();
$('previous').onclick=()=>{if(index<=0)return;rememberDraft();index--;show();};$('toast-edit').onclick=()=>{rememberDraft();index=previousIndex;show();};$('skip').onclick=()=>record('skip','unsure');
$('continue').onclick=()=>{rememberDraft();index++;show();};$('restart').onclick=()=>{index=0;show();};
$('retry-sync').onclick=()=>void sync?.retry();$('finished-retry').onclick=()=>void sync?.retry();$('loading-retry').onclick=()=>location.reload();
function download(text,name,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
$('export').onclick=()=>{if(!pool)return;download(records.map(r=>canonicalVote(r)).join('\n')+(records.length?'\n':''),`${pool.id}-preferences.jsonl`,'application/x-ndjson');};
$('recovery').onclick=()=>download(JSON.stringify(sync.recovery(),null,2),`${pool.id}-stored-recovery.json`,'application/json');
window.addEventListener('beforeunload',e=>{if(lastState.unprotected){e.preventDefault();e.returnValue='';}});
window.addEventListener('online',()=>void sync?.retry());window.addEventListener('storage',()=>sync?.scan());document.addEventListener('visibilitychange',()=>{if(!document.hidden)void sync?.flush();});
window.addEventListener('keydown',event=>{
 if(event.ctrlKey||event.metaKey||event.altKey||event.repeat||event.target.closest('input,textarea,select,[contenteditable=true]'))return;
 if(event.code==='Space'&&!event.target.closest('button,a,summary')&&!document.querySelector('dialog[open]')){event.preventDefault();if(pairReady){heldSource=true;zoom($('source').src,$('source-title').textContent,{source:true});}return;}
 if(document.querySelector('dialog[open]')||index>=pairs.length)return;
 if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();setView(event.key==='ArrowLeft'?'a':'b');return;}
 const key=event.key.toLowerCase(),value=phase==='taste'?({'1':'a',a:'a','2':'b',b:'b',t:'tie',n:'neither'}[key]):({'1':'a',a:'a','2':'b',b:'b',s:'similar',u:'unsure'}[key]);
 if(value){event.preventDefault();phase==='taste'?chooseTaste(value):chooseFidelity(value);}
});
window.addEventListener('keyup',event=>{if(event.code==='Space'&&heldSource){heldSource=false;if($('zoom').open)$('zoom').close();}});
window.addEventListener('blur',()=>{if(heldSource){heldSource=false;if($('zoom').open)$('zoom').close();}});
async function init(){try{
 const requestedPool=new URLSearchParams(location.search).get('pool');if(requestedPool&&!POOL_ID.test(requestedPool))throw Error('Invalid pool link');
 const response=await fetch(requestedPool?`/pool/${requestedPool}.json`:'/pool/current.json');if(!response.ok)throw Error('The paintings are not available yet. Try again shortly.');pool=validatePool(await response.json());if(requestedPool&&pool.id!==requestedPool)throw Error('Wrong pool identity');if(pool.reviewMode==='shortlist'){location.replace(`explore.html?pool=${pool.id}`);return;}pairs=pairPlan(pool);if(!pairs.length)throw Error('No distinct same-source paintings are available to compare.');
 window.tasteStudy={state:'loading',poolId:pool.id,pairs:pairs.length};
 let storage;try{storage=localStorage;}catch{storage=null;}
 sync=createReviewSync({pool,storage,onRemote:merge,onState:updateStatus});merge(sync.localEvents());$('loading-message').textContent='Restoring your place…';await sync.start();merge(sync.localEvents());
 const requested=Number(new URLSearchParams(location.search).get('pair'));index=Number.isInteger(requested)&&requested>=1&&requested<=pairs.length?requested-1:pairs.findIndex(p=>!latest(p));if(index<0)index=pairs.length;
 $('pool-label').textContent=pool.id;$('pool-status').textContent=`${pool.candidates.filter(c=>c.status==='ready').length} candidates · ${pool.sources.length} photographs · ${pairs.length} same-source comparisons. Conditions are hidden; historical attempts are preserved.`;
 const count=pool.candidates.filter(c=>c.status==='ready').length;$('generation-info').textContent=`${pool.visualFeedbackCandidates??'Some'} of ${count} finals are successful visual-feedback revisions. Other finals retain earlier or text-repair attempts. No policy training has happened.`;
 $('other-round').hidden=false;const other=pool.experiment?.parentPoolId;$('other-round').href=other&&POOL_ID.test(other)?`taste.html?pool=${other}`:'taste.html';$('other-round').textContent=other?'Earlier round':'Latest round';
 window.tasteStudy={state:'ready',poolId:pool.id,pairs:pairs.length,sync:lastState};show();updateStatus(sync.state());
}catch(error){$('loading-message').textContent=error.message;$('loading-retry').hidden=false;window.tasteStudy={state:'error',error:String(error)};}}
void init();
