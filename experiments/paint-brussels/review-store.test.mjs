import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,readdir,rm,symlink,unlink} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {createReviewStore,MAX_EVENT_BYTES} from './pool/review-store.mjs';
import {pairPlan,reference,canonicalVote} from './pool/contract.mjs';
import {startServer} from './serve.mjs';
const hash=n=>String(n).repeat(64),id='pool-1234567890123-abcdef12';
const fixture=()=>({version:1,id,status:'complete',sources:[{id:'one',title:'One',sha256:hash(1),post:'https://buildingsofbrussels.tumblr.com/post/123'}],candidates:[0,1].map(i=>({id:`one-${i}`,sourceId:'one',status:'ready',revision:1,title:'Painting',programSha256:hash(i+2),renderSha256:hash(i+4)}))});
function vote(pool,eventId='test-event'){const pair=pairPlan(pool)[0];return {version:1,id:eventId,at:'2026-11-11T00:00:00.000Z',poolId:pool.id,pairId:pair.id,sourceId:pair.sourceId,sourceSha256:pool.sources[0].sha256,a:reference(pair.a),b:reference(pair.b),preference:'a',fidelity:'b',note:'Synthetic storage test, not human feedback.'};}
async function setup(){const root=await mkdtemp(path.join(os.tmpdir(),'brussels-review-test-')),poolRoot=path.join(root,'pools'),reviewRoot=path.join(root,'ledger'),pool=fixture();await mkdir(path.join(poolRoot,id),{recursive:true});await writeFile(path.join(poolRoot,id,'manifest.json'),JSON.stringify(pool));return {root,poolRoot,reviewRoot,pool};}
test('idempotent canonical retries survive store restart; conflicting event IDs never overwrite',async()=>{
 const f=await setup();try{
  const store=createReviewStore({root:f.reviewRoot,poolRoot:f.poolRoot}),v=vote(f.pool,'../../not-a-path');
  const first=await store.append(v);assert.equal(first.created,true);
  const reordered=Object.fromEntries(Object.entries(v).reverse());const again=await store.append(reordered);assert.equal(again.created,false);assert.equal(again.sha256,first.sha256);assert.equal(again.receivedAt,first.receivedAt);
  await assert.rejects(()=>store.append({...v,note:'Different content'}),e=>e.status===409);
  const fresh=createReviewStore({root:f.reviewRoot,poolRoot:f.poolRoot}),rows=await fresh.list(id);assert.equal(rows.length,1);assert.equal(canonicalVote(rows[0].event),canonicalVote(v));
  const files=await readdir(path.join(f.reviewRoot,id));assert.equal(files.length,1);assert.match(files[0],/^[a-f0-9]{64}\.json$/);
  const raw=JSON.parse(await readFile(path.join(f.reviewRoot,id,files[0]),'utf8'));assert.equal(raw.sha256,createHash('sha256').update(canonicalVote(v)).digest('hex'));
 }finally{await rm(f.root,{recursive:true,force:true});}
});
test('concurrent appends conserve unique events and enforce the configured quota',async()=>{
 const f=await setup();try{
  const store=createReviewStore({root:f.reviewRoot,poolRoot:f.poolRoot,maxEvents:2}),a=vote(f.pool,'a'),b=vote(f.pool,'b'),c=vote(f.pool,'c');
  const results=await Promise.allSettled([store.append(a),store.append(a),store.append(b),store.append(c)]);
  assert.deepEqual(results.slice(0,3).map(r=>r.value.created),[true,false,true]);assert.equal(results[3].reason.status,507);
  assert.equal((await store.list(id)).length,2);assert.equal((await store.append(a)).created,false);
  await assert.rejects(()=>store.append({...vote(f.pool,'bad'),a:{...a.a,renderSha256:hash(9)}}),e=>e.status===400);
  await assert.rejects(()=>store.append({...vote(f.pool,'bad'),hidden:'not allowed'}),e=>e.status===400);
  assert.equal((await store.list(id)).length,2);
 }finally{await rm(f.root,{recursive:true,force:true});}
});
test('corrupt or symlinked receipt files fail closed without deleting stored data',async()=>{
 const f=await setup();try{
  const store=createReviewStore({root:f.reviewRoot,poolRoot:f.poolRoot}),v=vote(f.pool);await store.append(v);
  const file=path.join(f.reviewRoot,id,(await readdir(path.join(f.reviewRoot,id)))[0]);await writeFile(file,'broken JSON');
  await assert.rejects(()=>store.list(id),e=>e.status===500);assert.equal(await readFile(file,'utf8'),'broken JSON');
  const target=path.join(f.root,'not-a-receipt.txt');await writeFile(target,'synthetic private value');await unlink(file);await symlink(target,file);
  await assert.rejects(()=>store.list(id),e=>e.status===500);assert.equal(await readFile(target,'utf8'),'synthetic private value');
 }finally{await rm(f.root,{recursive:true,force:true});}
});
test('HTTP review API fences origins, tokens, content types and payloads; commits once',async()=>{
 const f=await setup();let server;
 try{
  server=await startServer({poolRoot:f.poolRoot,reviewRoot:f.reviewRoot});const base=`http://127.0.0.1:${server.address().port}`;
  const session=await fetch(base+'/api/review/session'),{token}=await session.json();assert.equal(session.headers.get('access-control-allow-origin'),null);
  const url=base+'/api/review/events',headers={'content-type':'application/json','x-review-token':token,origin:base},v=vote(f.pool);
  assert.equal((await fetch(url+'?pool='+id)).status,403);
  assert.equal((await fetch(base+'/api/review/session',{headers:{origin:'https://evil.example'}})).status,403);
  assert.equal((await fetch(base+'/api/review/session',{headers:{'sec-fetch-site':'cross-site'}})).status,403);
  const hostStatus=await new Promise((resolve,reject)=>{const r=http.get(base+'/api/review/session',{headers:{Host:'evil.example'}},res=>{res.resume();res.on('end',()=>resolve(res.statusCode));});r.on('error',reject);});assert.equal(hostStatus,403);
  const post=(body,extra={})=>fetch(url,{method:'POST',headers:{...headers,...extra},body:typeof body==='string'?body:JSON.stringify(body)});
  assert.equal((await post(v,{origin:'https://evil.example'})).status,403);
  assert.equal((await post(v,{'x-review-token':'x'})).status,403);
  assert.equal((await post(v,{'content-type':'text/plain'})).status,415);
  assert.equal((await post('not json')).status,400);
  assert.equal((await post(JSON.stringify({data:'x'.repeat(MAX_EVENT_BYTES)}))).status,413);
  assert.equal((await post({...v,note:'x'.repeat(2001)})).status,400);
  const saved=await post(v);assert.equal(saved.status,201);const receipt=await saved.json();assert.equal(receipt.event.id,v.id);
  assert.equal((await post(v)).status,200);assert.equal((await post({...v,note:'conflicting edit'})).status,409);
  const all=await fetch(url+'?pool='+id,{headers:{'x-review-token':token}});const result=await all.json();assert.equal(result.receipts.length,1);assert.equal(result.receipts[0].sha256,receipt.sha256);
  await new Promise(r=>server.close(r));server=null;
  server=await startServer({poolRoot:f.poolRoot,reviewRoot:f.reviewRoot});const base2=`http://127.0.0.1:${server.address().port}`,session2=await(await fetch(base2+'/api/review/session')).json();
  const restored=await(await fetch(base2+'/api/review/events?pool='+id,{headers:{'x-review-token':session2.token}})).json();assert.equal(restored.receipts.length,1);
 }finally{if(server)await new Promise(r=>server.close(r));await rm(f.root,{recursive:true,force:true});}
});
