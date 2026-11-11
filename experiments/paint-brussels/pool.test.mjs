import test from 'node:test';
import assert from 'node:assert/strict';
import {parsePainting,validatePool,pairPlan,validateVote,reference} from './pool/contract.mjs';
import {validatePlan,planTasks} from './pool/task-plan.mjs';
import {poolAsset} from './pool/serve-assets.mjs';
import {mkdtemp,writeFile,mkdir,rm,readFile} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
const hash=n=>String(n).repeat(64);
function fixture(){return {version:1,id:'pool-1234567890123-abcdef12',status:'complete',sources:[{id:'one',title:'One',sha256:hash(1),post:'https://buildingsofbrussels.tumblr.com/post/123'},{id:'two',title:'Two',sha256:hash(2),post:'https://buildingsofbrussels.tumblr.com/post/456'}],candidates:Array.from({length:6},(_,i)=>({id:`c-${i}`,sourceId:i<3?'one':'two',status:'ready',revision:1,title:`Painting ${i}`,programSha256:hash(i+1),renderSha256:hash(i+2)}))};}
function vote(pool){const pair=pairPlan(pool)[0];return {version:1,id:'event-1',at:'2026-11-11T00:00:00.000Z',poolId:pool.id,pairId:pair.id,sourceId:pair.sourceId,sourceSha256:pool.sources.find(s=>s.id===pair.sourceId).sha256,a:reference(pair.a),b:reference(pair.b),preference:'a',fidelity:'b',note:'More interesting; less faithful.'};}
test('program envelopes contain executable artifacts, not scene-schema parameters',()=>{
 const program='function paint(p) { p.background("red"); }';
 assert.equal(parsePainting(JSON.stringify({title:'Study',intent:'Paint',simplifications:[],program})).program,program);
 for(const value of [{title:'Study',intent:'Paint',simplifications:[],program:'{"facade":1}'},{title:'Study',intent:'Paint',simplifications:[],program:'x'.repeat(65537)}])assert.throws(()=>parsePainting(JSON.stringify(value)));
 assert.throws(()=>parsePainting('x'.repeat(100001)));
});
test('pairs never cross photographs and interleave subjects without duplicate renders',()=>{
 const pool=validatePool(fixture()),pairs=pairPlan(pool);assert.equal(pairs.length,6);
 assert.notEqual(pairs[0].sourceId,pairs[1].sourceId);
 for(const pair of pairs){assert.equal(pair.a.sourceId,pair.b.sourceId);assert.notEqual(pair.a.renderSha256,pair.b.renderSha256);}
 pool.candidates[1].renderSha256=pool.candidates[0].renderSha256;
 assert.equal(pairPlan(pool).length,5);
});
test('taste and fidelity remain independent and bound to exact source/program/render bytes',()=>{
 const pool=fixture(),event=vote(pool);assert.equal(validateVote(event,pool),event);
 for(const mutate of [v=>v.version=2,v=>v.hidden='untracked data',v=>v.a.hidden='untracked data',v=>v.preference='skip',v=>v.sourceId='two',v=>v.sourceSha256=hash(9),v=>v.a.renderSha256=hash(9),v=>v.b.programSha256=hash(9),v=>v.a.revision=0,v=>v.preference='great',v=>v.fidelity='accurate',v=>v.note='x'.repeat(2001)]){const changed=structuredClone(event);mutate(changed);assert.throws(()=>validateVote(changed,pool));}
 event.preference='skip';event.fidelity='unsure';validateVote(event,pool);
});
test('pool IDs and source credits cannot become arbitrary artifact paths',()=>{
 for(const mutate of [p=>p.id='../credentials',p=>p.sources[0].id=null,p=>p.candidates[0].id='../program',p=>p.sources[0].post='https://evil.example/',p=>p.candidates.push(structuredClone(p.candidates[0]))]){const pool=fixture();mutate(pool);assert.throws(()=>validatePool(pool));}
});
function generatedPlan(n,m){return {version:1,subjects:Array.from({length:n},(_,i)=>({id:`s-${i}`,title:`Building ${i}`,sha256:i.toString(16).padStart(64,'0'),post:`https://buildingsofbrussels.tumblr.com/post/${100+i}`,image:`https://64.media.tumblr.com/image-${i}.jpg`})),briefs:Array.from({length:m},(_,i)=>`Direction ${i}`)};}
test('all bounded subject/brief cardinalities conserve task membership and the request ceiling',()=>{
 for(let n=1;n<=18;n++)for(let m=1;m<=6;m++){
  const plan=generatedPlan(n,m),before=structuredClone(plan);
  if(n*m>18){assert.throws(()=>validatePlan(plan),/pilot budget/);continue;}
  const tasks=planTasks(plan);assert.equal(tasks.length,n*m);assert.ok(tasks.length*2<=36);assert.equal(new Set(tasks.map(t=>t.id)).size,tasks.length);
  for(const source of plan.subjects){const subset=tasks.filter(t=>t.source.id===source.id);assert.equal(subset.length,m);assert.deepEqual(subset.map(t=>t.index),Array.from({length:m},(_,i)=>i));}
  assert.deepEqual(plan,before);assert.deepEqual(planTasks(JSON.parse(JSON.stringify(plan))),tasks);
 }
 for(const invalid of [generatedPlan(0,1),generatedPlan(1,0)])assert.throws(()=>validatePlan(invalid),/pilot budget/);
 const repeated=generatedPlan(2,2);repeated.subjects[1].sha256=repeated.subjects[0].sha256;assert.throws(()=>validatePlan(repeated),/Repeated source photograph/);
 for(const mutate of [p=>p.subjects[0].id='../escape',p=>p.subjects[0].image='https://evil.example/image.jpg',p=>p.subjects[0].post='https://evil.example/post/1',p=>p.subjects.push(p.subjects[0]),p=>p.briefs[0]='',p=>p.experiment={kind:'other'}]){const p=generatedPlan(1,2);mutate(p);assert.throws(()=>validatePlan(p),/Invalid plan source|Unapproved source URL|Invalid candidate brief|Invalid transfer provenance/);}
});
test('paired-trial positions balance by source while legacy vote references remain unchanged',()=>{
 const legacy=fixture(),event=vote(legacy);validateVote(event,legacy);
 for(let n=1;n<=9;n++){
  const p=generatedPlan(n,2),pool={version:1,id:legacy.id,status:'complete',pairingVersion:2,sources:p.subjects,candidates:planTasks(p).map((t,i)=>({id:t.id,sourceId:t.source.id,status:'ready',revision:1,title:'Study',programSha256:hash(1),renderSha256:i.toString(16).padStart(64,'0')}))};
  const pairs=pairPlan(pool);assert.equal(pairs.length,n);assert.equal(pairs.filter(p=>p.a.id.endsWith('-01')).length,Math.ceil(n/2));assert.equal(pairs.filter(p=>p.b.id.endsWith('-01')).length,Math.floor(n/2));
 }
 legacy.pairingVersion=1;validateVote(event,legacy);legacy.pairingVersion=3;assert.throws(()=>validatePool(legacy));
});
test('a new current pointer does not invalidate historical metadata or artifact routes',async()=>{
 const rootDir=await mkdtemp(path.join(os.tmpdir(),'painting-route-test-'));
 try{
  const old=fixture(),next={...fixture(),id:'pool-1234567890124-abcdef13'};
  for(const p of [old,next]){await mkdir(path.join(rootDir,p.id));await writeFile(path.join(rootDir,p.id,'manifest.json'),JSON.stringify(p));}
  await writeFile(path.join(rootDir,'current.json'),JSON.stringify({id:next.id}));
  const current=await poolAsset('/pool/current.json',{rootDir}),historical=await poolAsset(`/pool/${old.id}.json`,{rootDir});assert.ok(current[0].includes(next.id));assert.ok(historical[0].includes(old.id));
  const prefix=`/pool-data/${old.id}/candidates/c-0/r1/`;
  const png=await poolAsset(prefix+'render.png',{rootDir});assert.equal(png[3],old.candidates[0].renderSha256);
  const code=await poolAsset(prefix+'program.js',{rootDir});assert.ok(code[1].startsWith('text/plain'));assert.equal(code[2],'attachment');
  assert.equal(await poolAsset(prefix+'record.json',{rootDir}),null);assert.equal(await poolAsset('/pool/../../credentials.json',{rootDir}),null);assert.equal(await poolAsset('/pool-data/../../credentials',{rootDir}),null);
 }finally{await rm(rootDir,{recursive:true,force:true});}
});
test('the portfolio rounds keep the working baseline and do not reuse source posts or image bytes',async()=>{
 const plans=await Promise.all(['plan.json','transfer-plan.json','round-three-plan.json'].map(async name=>validatePlan(JSON.parse(await readFile(new URL('./pool/'+name,import.meta.url),'utf8')))));
 const seenPosts=new Set(['https://buildingsofbrussels.tumblr.com/post/162278233614']),seenHashes=new Set();
 for(const plan of plans){assert.equal(plan.briefs[0],plans[0].briefs[0]);for(const s of plan.subjects){assert.ok(!seenPosts.has(s.post));assert.ok(!seenHashes.has(s.sha256));seenPosts.add(s.post);seenHashes.add(s.sha256);}}
 assert.equal(planTasks(plans[2]).length,16);assert.equal(plans[2].experiment.humanPairs,8);assert.equal(plans[2].experiment.sourceEvents,10);assert.notEqual(plans[2].briefs[1],plans[1].briefs[1]);
});
