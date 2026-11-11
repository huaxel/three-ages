import {mkdir,open,link,unlink,readdir} from 'node:fs/promises';
import {constants} from 'node:fs';
import {createHash,randomUUID} from 'node:crypto';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {validatePool,validateReviewEvent,canonicalReviewEvent,POOL_ID} from './contract.mjs';

export const DEFAULT_POOLS=fileURLToPath(new URL('../../../local/paint-brussels/pools/',import.meta.url));
export const DEFAULT_REVIEWS=fileURLToPath(new URL('../../../local/paint-brussels/reviews/',import.meta.url));
export const MAX_EVENT_BYTES=16384;
export class ReviewError extends Error{constructor(status,message){super(message);this.status=status;}}
const digest=value=>createHash('sha256').update(value).digest('hex');
const checkedId=id=>{if(typeof id!=='string'||id!==id.trim()||!POOL_ID.test(id))throw new ReviewError(400,'Invalid pool ID');return id;};
async function syncDir(dir){const h=await open(dir,constants.O_RDONLY|constants.O_DIRECTORY);try{await h.sync();}finally{await h.close();}}
async function boundedFile(file,max){
 const h=await open(file,constants.O_RDONLY|constants.O_NOFOLLOW|constants.O_NONBLOCK);
 try{const stat=await h.stat();if(!stat.isFile()||stat.size>max)throw new Error('Invalid ledger file');const b=Buffer.alloc(max+1);let size=0;while(size<b.length){const {bytesRead}=await h.read(b,size,b.length-size,size);if(!bytesRead)break;size+=bytesRead;}if(size>max)throw new Error('Ledger file too large');return b.subarray(0,size).toString('utf8');}finally{await h.close();}
}
export function createReviewStore({root=DEFAULT_REVIEWS,poolRoot=DEFAULT_POOLS,maxEvents=5000,maxBytes=16*1024*1024}={}){
 root=path.resolve(root);poolRoot=path.resolve(poolRoot);let queue=Promise.resolve(),waiting=0;
 const poolCache=new Map();
 async function pool(id){checkedId(id);if(!poolCache.has(id)){let value;try{value=validatePool(JSON.parse(await boundedFile(path.join(poolRoot,id,'manifest.json'),2*1024*1024)));}catch(e){if(e.code==='ENOENT')throw new ReviewError(404,'Completed pool not found');throw new ReviewError(500,'Pool metadata could not be validated');}if(value.id!==id)throw new ReviewError(500,'Pool identity mismatch');poolCache.set(id,value);}return poolCache.get(id);}
 function serial(fn){if(waiting>=32)return Promise.reject(new ReviewError(429,'Review queue is busy; retry shortly'));waiting++;const job=queue.then(fn);queue=job.catch(()=>{});return job.finally(()=>waiting--);}
 async function entries(id){
  const dir=path.join(root,checkedId(id));let names;try{names=await readdir(dir);}catch(e){if(e.code==='ENOENT')return [];throw e;}
  const files=names.filter(n=>n.endsWith('.json'));if(files.length>maxEvents||files.some(n=>! /^[a-f0-9]{64}\.json$/.test(n)))throw new Error('Invalid ledger directory');
  const p=await pool(id),result=[];let bytes=0;
  for(const name of files){const text=await boundedFile(path.join(dir,name),MAX_EVENT_BYTES+1024);bytes+=Buffer.byteLength(text);if(bytes>maxBytes)throw new Error('Ledger exceeds budget');const r=JSON.parse(text);validateReviewEvent(r.event,p);const canonical=canonicalReviewEvent(r.event);if(r.version!==1||r.sha256!==digest(canonical)||name!==digest(r.event.id)+'.json'||r.event.poolId!==id||typeof r.receivedAt!=='string'||!Number.isFinite(Date.parse(r.receivedAt)))throw new Error('Invalid stored receipt');result.push(r);}
  Object.defineProperty(result,'byteLength',{value:bytes});return result.sort((a,b)=>a.receivedAt.localeCompare(b.receivedAt)||a.event.id.localeCompare(b.event.id));
 }
 return {
  root,pool,
  async list(id){return serial(async()=>{await pool(id);try{return await entries(id);}catch(e){if(e instanceof ReviewError)throw e;throw new ReviewError(500,'Stored reviews need attention; existing files were preserved');}});},
  async append(value){return serial(async()=>{
   const id=checkedId(value?.poolId),p=await pool(id);let canonical;
   try{validateReviewEvent(value,p);canonical=canonicalReviewEvent(value);}catch{throw new ReviewError(400,'Choice does not match this pool or its exact image/program revisions');}
   if(Buffer.byteLength(canonical)>MAX_EVENT_BYTES)throw new ReviewError(413,'Choice exceeds the size limit');
   const event=JSON.parse(canonical),dir=path.join(root,id),file=path.join(dir,digest(event.id)+'.json');
   await mkdir(root,{recursive:true,mode:0o700});await syncDir(path.dirname(root));await mkdir(dir,{recursive:true,mode:0o700});await syncDir(root);
   async function existing(){let text;try{text=await boundedFile(file,MAX_EVENT_BYTES+1024);}catch(e){if(e.code==='ENOENT')return null;throw e;}const receipt=JSON.parse(text);validateReviewEvent(receipt.event,p);if(receipt.version!==1||receipt.event.poolId!==id||typeof receipt.receivedAt!=='string'||!Number.isFinite(Date.parse(receipt.receivedAt))||receipt.sha256!==digest(canonicalReviewEvent(receipt.event)))throw new Error('Invalid existing receipt');if(canonicalReviewEvent(receipt.event)!==canonical)throw new ReviewError(409,'This event ID already has different content; neither copy was overwritten');const h=await open(file,constants.O_RDONLY|constants.O_NOFOLLOW);try{await h.sync();}finally{await h.close();}await syncDir(dir);return {...receipt,created:false};}
   const found=await existing();if(found)return found;
   const rows=await entries(id),receipt={version:1,event,receivedAt:new Date().toISOString(),sha256:digest(canonical)},text=JSON.stringify(receipt)+'\n';
   const used=rows.byteLength??0;
   if(rows.length>=maxEvents||used+Buffer.byteLength(text)>maxBytes)throw new ReviewError(507,'The review ledger is full; existing choices were preserved');
   const temp=path.join(dir,`.${randomUUID()}.tmp`);let handle;
   try{handle=await open(temp,'wx',0o600);await handle.writeFile(text);await handle.sync();await handle.close();handle=null;
    try{await link(temp,file);}catch(e){if(e.code==='EEXIST'){const found=await existing();if(found)return found;}throw e;}
    await syncDir(dir);return {...receipt,created:true};
   }finally{if(handle)await handle.close();await unlink(temp).catch(e=>{if(e.code!=='ENOENT')throw e;});}
  });}
 };
}
