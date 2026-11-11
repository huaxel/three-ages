import {randomBytes,timingSafeEqual} from 'node:crypto';
import {ReviewError,MAX_EVENT_BYTES} from './review-store.mjs';

const headers={'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'",'X-Frame-Options':'DENY'};
function body(req){return new Promise((resolve,reject)=>{
 let chunks=[],size=0,done=false;const timer=setTimeout(()=>finish(new ReviewError(408,'Review upload timed out')),10000);timer.unref();
 const cleanup=()=>{clearTimeout(timer);req.off('data',data);req.off('end',end);req.off('error',error);req.off('aborted',aborted);};
 function finish(err,value){if(done)return;done=true;cleanup();err?reject(err):resolve(value);}
 const data=chunk=>{size+=chunk.length;if(size>MAX_EVENT_BYTES){chunks=[];finish(new ReviewError(413,'Choice exceeds the size limit'));req.resume();}else chunks.push(chunk);};
 const end=()=>{try{finish(null,JSON.parse(Buffer.concat(chunks).toString('utf8')));}catch{finish(new ReviewError(400,'Expected a JSON choice'));}};
 const error=()=>finish(new ReviewError(400,'Review upload failed')),aborted=()=>finish(new ReviewError(400,'Review upload interrupted'));
 req.on('data',data);req.on('end',end);req.on('error',error);req.on('aborted',aborted);
 });}
export function createReviewApi(store){
 const token=randomBytes(32).toString('hex');
 return async function reviewApi(req,res){
  const url=new URL(req.url,'http://localhost');if(!url.pathname.startsWith('/api/review/'))return false;
  const send=(status,value)=>{if(res.destroyed||res.writableEnded)return;res.writeHead(status,headers);res.end(JSON.stringify(value));};
  try{
   // Host checking is also required on bootstrap: CORS alone does not stop DNS rebinding.
   const ip=req.socket.localAddress?.replace(/^::ffff:/,''),port=req.socket.localPort;
   const local=`${ip?.includes(':')?`[${ip}]`:ip}:${port}`;
   const allowed=new Set([local]);if(['127.0.0.1','::1'].includes(ip))allowed.add(`localhost:${port}`);
   if(!allowed.has(req.headers.host))throw new ReviewError(403,'Review origin refused');
   const origin=`http://${req.headers.host}`;
   if(req.headers.origin&&req.headers.origin!==origin||req.headers['sec-fetch-site']&&!['same-origin','none'].includes(req.headers['sec-fetch-site']))throw new ReviewError(403,'Review origin refused');
   if(url.pathname==='/api/review/session'&&req.method==='GET'){send(200,{version:1,token});return true;}
   const supplied=req.headers['x-review-token'];
   if(typeof supplied!=='string'||! /^[a-f0-9]{64}$/.test(supplied)||!timingSafeEqual(Buffer.from(supplied),Buffer.from(token)))throw new ReviewError(403,'Review session expired; reconnect to retry');
   if(url.pathname!=='/api/review/events')throw new ReviewError(404,'Review endpoint not found');
   if(req.method==='GET'){const poolId=url.searchParams.get('pool'),receipts=await store.list(poolId);send(200,{version:1,poolId,receipts});return true;}
   if(req.method!=='POST')throw new ReviewError(405,'Method not allowed');
   if(req.headers.origin!==origin)throw new ReviewError(403,'A same-origin review request is required');
   if(!/^application\/json(?:\s*;\s*charset=utf-8)?$/i.test(req.headers['content-type']??''))throw new ReviewError(415,'Use application/json');
   if(req.headers['content-encoding'])throw new ReviewError(415,'Compressed review uploads are not accepted');
   const length=req.headers['content-length'];if(length&&(!/^\d+$/.test(length)||Number(length)>MAX_EVENT_BYTES))throw new ReviewError(413,'Choice exceeds the size limit');
   const result=await store.append(await body(req));send(result.created?201:200,result);
  }catch(error){if(res.destroyed||res.writableEnded)return true;const status=error instanceof ReviewError?error.status:503;
   if([408,413].includes(status)){res.setHeader('Connection','close');res.once('finish',()=>req.destroy());}
   send(status,{error:error instanceof ReviewError?error.message:'Review storage is temporarily unavailable; keep the local copy and retry'});
  }
  return true;
 };
}
