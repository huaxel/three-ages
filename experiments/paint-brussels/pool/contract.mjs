export const ID=/^[a-z][a-z0-9-]{0,59}$/;
export const POOL_ID=/^pool-\d{13}-[a-f0-9]{8}$/;
export const HASH=/^[a-f0-9]{64}$/;
const validId=v=>typeof v==='string'&&v===v.trim()&&ID.test(v);
const text=(v,n)=>typeof v==='string'&&v.length>0&&v.length<=n;
export function parsePainting(textValue) {
  if(typeof textValue!=='string'||new TextEncoder().encode(textValue).length>100000)throw Error('Response exceeds budget');
  const value=JSON.parse(textValue.trim().replace(/^```(?:json)?\s*/,'').replace(/\s*```$/,''));
  if(!value||!text(value.title,120)||!text(value.intent,500)||!Array.isArray(value.simplifications)||value.simplifications.length>8||value.simplifications.some(s=>!text(s,500)))throw Error('Invalid painting description');
  if(!text(value.program,65536)||new TextEncoder().encode(value.program).length>65536||!/function\s+paint\s*\(\s*p\s*\)/.test(value.program))throw Error('Expected a bounded paint(p) program');
  return {title:value.title,intent:value.intent,simplifications:value.simplifications,program:value.program};
}
export function validatePool(pool) {
  if(pool?.version!==1||!POOL_ID.test(pool.id)||pool.status!=='complete'||!Array.isArray(pool.sources)||!Array.isArray(pool.candidates)||pool.sources.length<1||pool.sources.length>24||pool.candidates.length>144)throw Error('Invalid completed pool');
  if(pool.pairingVersion!==undefined&&![1,2].includes(pool.pairingVersion))throw Error('Unknown pairing version');
  if(pool.reviewMode!==undefined&&pool.reviewMode!=='shortlist')throw Error('Unknown review mode');
  const subjects=new Set();
  for(const s of pool.sources) {
    if(!validId(s.id)||subjects.has(s.id)||!text(s.title,160)||!HASH.test(s.sha256))throw Error('Invalid pool source');
    if(pool.reviewMode==='shortlist'&&pool.candidates.some(c=>c?.sourceId===s.id&&c.status==='ready'&&c.renderKind==='structured-v1')&&!HASH.test(s.structureSha256))throw Error('Missing frozen structure fingerprint');
    subjects.add(s.id);
    const u=new URL(s.post);if(u.protocol!=='https:'||u.hostname!=='buildingsofbrussels.tumblr.com'||u.username||u.password)throw Error('Invalid source credit');
  }
  const ids=new Set();
  for(const c of pool.candidates) {
    if(!validId(c.id)||ids.has(c.id)||!subjects.has(c.sourceId)||!['ready','failed'].includes(c.status))throw Error('Invalid pool candidate');ids.add(c.id);
    if(c.status==='ready'&&(![0,1].includes(c.revision)||!HASH.test(c.programSha256)||!HASH.test(c.renderSha256)||!text(c.title,120)))throw Error('Invalid candidate provenance');
  }
  if(pool.reviewMode==='shortlist')for(const c of pool.candidates.filter(c=>c.status==='ready')){if(!validId(c.styleId)||![0,1,2].includes(c.variant)||!['structured-v1','free-program-v1'].includes(c.renderKind)||!HASH.test(c.operatorSha256))throw Error('Invalid painting candidate provenance');if(c.renderKind==='structured-v1'&&(!HASH.test(c.structureSha256)||c.structureSha256!==pool.sources.find(s=>s.id===c.sourceId).structureSha256))throw Error('Invalid structured candidate provenance');if(c.renderKind==='free-program-v1'&&c.structureSha256!==undefined)throw Error('Free paintings must not claim a frozen structure dependency');}
  for(const c of pool.candidates.filter(c=>c.status==='ready'))if(c.personaId!==undefined&&(!validId(c.personaId)||!Number.isSafeInteger(c.personaStyleVersion)||c.personaStyleVersion<0||c.personaStyleVersion>10000||!HASH.test(c.proposalSha256)))throw Error('Invalid persona style provenance');
  return pool;
}
export function pairPlan(pool) {
  validatePool(pool);const bySource=pool.sources.map((s,sourceIndex)=>{
    const candidates=pool.candidates.filter(c=>c.sourceId===s.id&&c.status==='ready'),pairs=[];
    for(let i=0;i<candidates.length;i++)for(let j=i+1;j<candidates.length;j++) {
      if(candidates[i].renderSha256===candidates[j].renderSha256)continue;
      const a=candidates[i],b=candidates[j],flip=(i+j+(pool.pairingVersion===2?sourceIndex:0))%2===0;
      pairs.push({id:`${a.id}--${b.id}`,sourceId:s.id,a:flip?b:a,b:flip?a:b});
    }
    return pairs;
  });
  const result=[];for(let i=0;i<Math.max(0,...bySource.map(p=>p.length));i++)for(const pairs of bySource)if(pairs[i])result.push(pairs[i]);
  return result;
}
export function validateVote(vote,pool) {
  if(pool.reviewMode==='shortlist')throw Error('This pool requires a shortlist judgment');
  const fields=['version','id','at','poolId','pairId','sourceId','sourceSha256','a','b','preference','fidelity','note'];
  if(!vote||typeof vote!=='object'||Object.keys(vote).some(k=>!fields.includes(k)))throw Error('Unknown preference fields');
  const pair=pairPlan(pool).find(p=>p.id===vote?.pairId);
  const source=pool.sources.find(s=>s.id===pair?.sourceId);
  if(vote?.version!==1||!pair||vote.poolId!==pool.id||vote.sourceId!==pair.sourceId||vote.sourceSha256!==source.sha256||!text(vote.id,80)||!text(vote.at,40)||!Number.isFinite(Date.parse(vote.at))||typeof vote.note!=='string'||vote.note.length>2000)throw Error('Invalid preference record');
  if(!['a','b','tie','neither','skip'].includes(vote.preference)||!['a','b','similar','unsure'].includes(vote.fidelity))throw Error('Invalid preference choice');
  if(vote.preference==='skip'&&vote.fidelity!=='unsure')throw Error('Skipped comparisons cannot contain a fidelity vote');
  for(const side of ['a','b']) {
    const c=pair[side],r=vote[side];
    if(r&&Object.keys(r).some(k=>!['id','revision','programSha256','renderSha256'].includes(k)))throw Error('Unknown candidate reference fields');
    if(!r||r.id!==c.id||r.programSha256!==c.programSha256||r.renderSha256!==c.renderSha256||r.revision!==c.revision)throw Error('Preference points to a different program/render revision');
  }
  return vote;
}
export function reference(candidate) {return {id:candidate.id,revision:candidate.revision,programSha256:candidate.programSha256,renderSha256:candidate.renderSha256};}
// Call after validateVote: stable key order makes retries independent of JSON field order.
export function canonicalVote(v){return JSON.stringify({version:v.version,id:v.id,at:v.at,poolId:v.poolId,pairId:v.pairId,sourceId:v.sourceId,sourceSha256:v.sourceSha256,a:reference(v.a),b:reference(v.b),preference:v.preference,fidelity:v.fidelity,note:v.note});}
export function galleryCandidates(pool,sourceId){
 validatePool(pool);if(pool.reviewMode!=='shortlist')throw Error('Not a shortlist pool');
 const si=pool.sources.findIndex(s=>s.id===sourceId);if(si<0)throw Error('Unknown shortlist source');
 const ready=pool.candidates.filter(c=>c.sourceId===sourceId&&c.status==='ready'),styles=[...new Set(ready.map(c=>c.styleId))].sort();
 const shift=styles.length?(si*2)%styles.length:0,order=[...styles.slice(shift),...styles.slice(0,shift)];
 return order.flatMap(style=>ready.filter(c=>c.styleId===style).sort((a,b)=>a.variant-b.variant));
}
export function validateShortlist(e,pool){
 const fields=['version','kind','id','at','poolId','sourceId','sourceSha256','candidates','viewed','selected','decision','note'];
 if(!e||e.version!==2||e.kind!=='shortlist'||Object.keys(e).some(k=>!fields.includes(k))||pool.reviewMode!=='shortlist')throw Error('Invalid shortlist event');
 const source=pool.sources.find(s=>s.id===e.sourceId),candidates=galleryCandidates(pool,e.sourceId);
 if(!source||e.poolId!==pool.id||e.sourceSha256!==source.sha256||!text(e.id,80)||!text(e.at,40)||!Number.isFinite(Date.parse(e.at))||typeof e.note!=='string'||e.note.length>2000||!Array.isArray(e.candidates)||e.candidates.length!==candidates.length||e.candidates.length>24)throw Error('Invalid shortlist binding');
 for(let i=0;i<candidates.length;i++){const r=e.candidates[i],c=candidates[i];if(!r||Object.keys(r).some(k=>!['id','revision','programSha256','renderSha256'].includes(k))||r.id!==c.id||r.revision!==c.revision||r.programSha256!==c.programSha256||r.renderSha256!==c.renderSha256)throw Error('Shortlist references different candidate bytes');}
 if(!Array.isArray(e.selected)||e.selected.length>2||new Set(e.selected).size!==e.selected.length||!['keep','neither','skip'].includes(e.decision)||e.decision==='keep'&&e.selected.length<1||e.decision!=='keep'&&e.selected.length!==0)throw Error('Invalid shortlist choice');
 if(!Array.isArray(e.viewed)||e.viewed.length>candidates.length||new Set(e.viewed).size!==e.viewed.length||e.viewed.some(id=>!candidates.some(c=>c.id===id))||e.selected.some(id=>!e.viewed.includes(id))||e.decision==='neither'&&e.viewed.length===0)throw Error('Invalid shortlist exposure');
 const selected=e.selected.map(id=>candidates.find(c=>c.id===id));if(selected.some(c=>!c)||new Set(selected.map(c=>c.styleId)).size!==selected.length)throw Error('Shortlist must choose distinct available styles');return e;
}
export function validateReviewEvent(e,pool){if(e?.version===1)return validateVote(e,pool);return validateShortlist(e,pool);}
export function canonicalReviewEvent(e){if(e.version===1)return canonicalVote(e);return JSON.stringify({version:e.version,kind:e.kind,id:e.id,at:e.at,poolId:e.poolId,sourceId:e.sourceId,sourceSha256:e.sourceSha256,candidates:e.candidates.map(reference),viewed:[...e.viewed].sort(),selected:[...e.selected].sort(),decision:e.decision,note:e.note});}
