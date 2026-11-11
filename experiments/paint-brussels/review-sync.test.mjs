import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,rm,readdir,unlink} from 'node:fs/promises';
import os from 'node:os';import path from 'node:path';
import {createReviewSync} from './pool/review-sync.mjs';
import {createReviewStore} from './pool/review-store.mjs';
import {pairPlan,reference,canonicalVote} from './pool/contract.mjs';
import {startServer} from './serve.mjs';
const hash=n=>String(n).repeat(64),id='pool-1234567890123-abcdef12',otherId='pool-1234567890124-abcdef13';
function fixture(poolId=id){return {version:1,id:poolId,status:'complete',sources:[{id:'one',title:'One',sha256:hash(1),post:'https://buildingsofbrussels.tumblr.com/post/123'}],candidates:[0,1].map(i=>({id:`one-${i}`,sourceId:'one',status:'ready',revision:1,title:'Painting',programSha256:hash(i+2),renderSha256:hash(i+4)}))};}
function vote(pool,eventId='sync-event'){const pair=pairPlan(pool)[0];return {version:1,id:eventId,at:'2026-11-11T00:00:00.000Z',poolId:pool.id,pairId:pair.id,sourceId:pair.sourceId,sourceSha256:pool.sources[0].sha256,a:reference(pair.a),b:reference(pair.b),preference:'a',fidelity:'b',note:'Synthetic sync test.'};}
function memoryStorage(){const map=new Map();return {get length(){return map.size;},key:i=>[...map.keys()][i]??null,getItem:k=>map.get(k)??null,setItem:(k,v)=>map.set(k,String(v))};}
const key=e=>`brussels-painter-preferences-v1:${e.poolId}:event:${e.id}`;
async function setup(){const root=await mkdtemp(path.join(os.tmpdir(),'brussels-sync-test-')),poolRoot=path.join(root,'pools'),reviewRoot=path.join(root,'ledger'),pool=fixture(),other=fixture(otherId);for(const p of [pool,other]){await mkdir(path.join(poolRoot,p.id),{recursive:true});await writeFile(path.join(poolRoot,p.id,'manifest.json'),JSON.stringify(p));}const server=await startServer({poolRoot,reviewRoot}),base=`http://127.0.0.1:${server.address().port}`,store=createReviewStore({root:reviewRoot,poolRoot});return {root,pool,other,server,base,store,request:(url,options={})=>fetch(base+url,{...options,headers:{...options.headers,origin:base}})};}
async function close(f,sync){sync?.stop();await new Promise(r=>f.server.close(r));await rm(f.root,{recursive:true,force:true});}
test('offline queued choices retry once, including a lost acknowledgment, without duplicating server data',async()=>{
 const f=await setup();let sync,offline=true,lostAck=true;const storage=memoryStorage(),v=vote(f.pool);
 try{
  const request=async(url,options)=>{if(options?.method==='POST'){if(offline)throw Error('Simulated offline');const r=await f.request(url,options);if(lostAck){lostAck=false;await r.text();throw Error('Simulated lost acknowledgment after durable write');}return r;}return f.request(url,options);};
  sync=createReviewSync({pool:f.pool,storage,fetchImpl:request,retryMs:100000,pollMs:100000});await sync.start();sync.queue(v);await sync.flush();assert.equal(sync.state().pending,1);assert.equal((await f.store.list(id)).length,0);assert.equal(storage.getItem(key(v)),canonicalVote(v));
  offline=false;await sync.retry();assert.equal(sync.state().pending,1);assert.equal((await f.store.list(id)).length,1);
  await sync.retry();assert.equal(sync.state().pending,0);assert.equal(sync.state().online,true);assert.equal((await f.store.list(id)).length,1);
 }finally{await close(f,sync);}
});
test('earlier browser-only pools are automatically backfilled and new devices restore server history',async()=>{
 const f=await setup();let sync,otherSync;try{
  const storage=memoryStorage(),old=vote(f.other,'old-browser-event');storage.setItem(key(old),JSON.stringify(old));
  sync=createReviewSync({pool:f.pool,storage,fetchImpl:f.request,pollMs:100000});await sync.start();await sync.flush();assert.equal((await f.store.list(otherId)).length,1);assert.equal(sync.state().pending,0);sync.stop();
  let restored=[];otherSync=createReviewSync({pool:f.other,storage:memoryStorage(),fetchImpl:f.request,onRemote:e=>restored=e,pollMs:100000});await otherSync.start();await otherSync.flush();assert.equal(restored.length,1);assert.equal(restored[0].id,old.id);
 }finally{otherSync?.stop();await close(f,sync);}
});
test('missing localStorage is safe only after server acknowledgment; malformed old entries do not block valid choices',async()=>{
 const f=await setup();let sync;try{
  const storage=memoryStorage(),broken={poolId:otherId,id:'broken'};storage.setItem(key(broken),JSON.stringify(broken));const valid=vote(f.pool,'valid');
  sync=createReviewSync({pool:f.pool,storage,fetchImpl:f.request,pollMs:100000});await sync.start();sync.queue(valid);await sync.flush();assert.equal((await f.store.list(id)).length,1);assert.equal(sync.state().failed,1);assert.equal(sync.recovery().length,1);sync.stop();
  const refusing={length:0,key:()=>null,getItem:()=>null,setItem:()=>{throw Error('Quota');}};
  sync=createReviewSync({pool:f.pool,storage:refusing,fetchImpl:f.request,pollMs:100000});await sync.start();const e=vote(f.pool,'volatile');sync.queue(e);assert.equal(sync.state().unprotected,1);await sync.flush();assert.equal(sync.state().unprotected,0);assert.equal(sync.state().pending,0);
 }finally{await close(f,sync);}
});
test('same-ID conflicts preserve both browser and server contents rather than overwriting either',async()=>{
 const f=await setup();let sync;try{
  const remote=vote(f.pool,'conflict'),local={...remote,note:'A different local note'};await f.store.append(remote);const storage=memoryStorage();storage.setItem(key(local),JSON.stringify(local));
  sync=createReviewSync({pool:f.pool,storage,fetchImpl:f.request,pollMs:100000});await sync.start();await sync.flush();assert.ok(sync.state().failed>0);assert.equal((await f.store.list(id))[0].event.note,remote.note);assert.equal(JSON.parse(storage.getItem(key(local))).note,local.note);
 }finally{await close(f,sync);}
});
test('a missing server receipt is resent instead of hidden behind an old acknowledgment',async()=>{
 const f=await setup();let sync;try{
  sync=createReviewSync({pool:f.pool,storage:memoryStorage(),fetchImpl:f.request,pollMs:100000});await sync.start();sync.queue(vote(f.pool,'restore'));await sync.flush();assert.equal((await f.store.list(id)).length,1);
  const dir=path.join(f.root,'ledger',id);for(const name of await readdir(dir))if(name.endsWith('.json'))await unlink(path.join(dir,name));
  await sync.flush();assert.equal((await f.store.list(id)).length,1);assert.equal(sync.state().pending,0);
 }finally{await close(f,sync);}
});
