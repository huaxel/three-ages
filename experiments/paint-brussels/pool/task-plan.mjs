import {ID,HASH,POOL_ID} from './contract.mjs';
export function validatePlan(plan){
 if(plan?.version!==1||!Array.isArray(plan.subjects)||!Array.isArray(plan.briefs)||plan.subjects.length<1||plan.briefs.length<1||plan.briefs.length>6||plan.subjects.length*plan.briefs.length>18)throw Error('Plan exceeds the 18-candidate/36-request pilot budget');
 const seen=new Set(),photos=new Set(),posts=new Set();
 for(const s of plan.subjects){
  if(typeof s.id!=='string'||s.id!==s.id.trim()||!ID.test(s.id)||s.id.length>55||seen.has(s.id)||typeof s.title!=='string'||!s.title.trim()||s.title.length>160||!HASH.test(s.sha256))throw Error('Invalid plan source');seen.add(s.id);
  if(photos.has(s.sha256)||posts.has(s.post))throw Error('Repeated source photograph');photos.add(s.sha256);posts.add(s.post);
  for(const [field,host] of [['post','buildingsofbrussels.tumblr.com'],['image','64.media.tumblr.com']]){const u=new URL(s[field]);if(u.protocol!=='https:'||u.hostname!==host||u.username||u.password||u.port)throw Error('Unapproved source URL');}
 }
 if(plan.briefs.some(b=>typeof b!=='string'||!b.trim()||b.length>3000))throw Error('Invalid candidate brief');
 if(plan.experiment){const e=plan.experiment;if(e.kind==='persona-organic-v1'){if(!POOL_ID.test(e.parentPoolId)||!Array.isArray(e.personas)||e.personas.length!==plan.briefs.length||new Set(e.personas.map(p=>p.id)).size!==e.personas.length||e.geometryPolicy!=='independent-photo-interpretation'||e.personas.some(p=>typeof p.id!=='string'||!ID.test(p.id)||!Number.isSafeInteger(p.styleVersion)||p.styleVersion<0||p.styleVersion>10000||!HASH.test(p.proposalSha256)||!HASH.test(p.charterHash)))throw Error('Invalid persona plan provenance');}else if(e.kind!=='preference-transfer-v1'||plan.briefs.length!==2||!POOL_ID.test(e.parentPoolId)||!HASH.test(e.preferencesSha256)||!Number.isInteger(e.humanPairs)||e.humanPairs<1)throw Error('Invalid transfer provenance');}
 return plan;
}
export function planTasks(plan){validatePlan(plan);return plan.subjects.flatMap(source=>plan.briefs.map((direction,index)=>({source,direction,index,id:`${source.id}-${String(index+1).padStart(2,'0')}`})));}
