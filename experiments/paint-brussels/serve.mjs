import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {parseCatalog} from './scene-format.mjs';
import {poolAsset} from './pool/serve-assets.mjs';
import {createReviewStore,DEFAULT_POOLS,DEFAULT_REVIEWS} from './pool/review-store.mjs';
import {createReviewApi} from './pool/review-api.mjs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const base=fileURLToPath(new URL('.',import.meta.url));
const assets=new Map([
  ['/', ['index.html','text/html; charset=utf-8']],
  ['/index.html',['index.html','text/html; charset=utf-8']],
  ['/directions.html',['directions.html','text/html; charset=utf-8']],
  ['/directions.css',['directions.css','text/css']],
  ['/hybrid.css',['hybrid.css','text/css']],
  ['/directions.mjs',['directions.mjs','text/javascript']],
  ['/treatments.mjs',['treatments.mjs','text/javascript']],
  ['/style.css',['style.css','text/css']],
  ['/studio.mjs',['studio.mjs','text/javascript']],
  ['/scene.mjs',['scene.mjs','text/javascript']],
  ['/scene-format.mjs',['scene-format.mjs','text/javascript']],
  ['/explore.html',['pool/explore.html','text/html; charset=utf-8']],
  ['/explore.css',['pool/explore.css','text/css']],
  ['/explore.mjs',['pool/explore.mjs','text/javascript']],
  ['/taste.html',['pool/taste.html','text/html; charset=utf-8']],
  ['/taste.css',['pool/taste.css','text/css']],
  ['/taste.mjs',['pool/taste.mjs','text/javascript']],
  ['/pool-contract.mjs',['pool/contract.mjs','text/javascript']],
  ['/pool/contract.mjs',['pool/contract.mjs','text/javascript']],
  ['/pool/review-sync.mjs',['pool/review-sync.mjs','text/javascript']],
  ['/batch.html',['batch.html','text/html; charset=utf-8']],
  ['/batch.css',['batch.css','text/css']],
  ['/batch.mjs',['batch.mjs','text/javascript']],
  ['/sheet-layout.mjs',['sheet-layout.mjs','text/javascript']],
  ['/batch-catalog.json',['batch-catalog.json','application/json']],
  ['/vendor/brush.js',['vendor/brush.js','text/javascript']],
  ['/local/paint-brussels/source.jpg',['../../local/paint-brussels/source.jpg','image/jpeg']],
]);
const catalog=parseCatalog(readFileSync(new URL('./batch-catalog.json',import.meta.url),'utf8'));
for(const item of catalog.items) {
  assets.set(`/scenes/${item.scene}`,[`scenes/${item.scene}`,'application/json']);
  assets.set(`/local/paint-brussels/batch/${item.file}`,[`../../local/paint-brussels/batch/${item.file}`,'image/jpeg']);
}
export async function startServer({port=0, host='127.0.0.1',reviewRoot=DEFAULT_REVIEWS,poolRoot=DEFAULT_POOLS}={}) {
  const reviewApi=createReviewApi(createReviewStore({root:reviewRoot,poolRoot}));
  const server=http.createServer(async(req,res)=>{
    try {
      if(await reviewApi(req,res))return;
      if(!['GET','HEAD'].includes(req.method)){res.writeHead(404);res.end('Not found');return;}
      const pathname=new URL(req.url,'http://localhost').pathname;
      const entry=assets.get(pathname)??await poolAsset(pathname,{rootDir:poolRoot});
      if(!entry){res.writeHead(404);res.end('Not found');return;}
      const content=await readFile(path.join(base,entry[0]));
      if(entry[3]&&createHash('sha256').update(content).digest('hex')!==entry[3])throw Error('Pool artifact fingerprint mismatch');
      const connections=['batch.html','pool/taste.html','pool/explore.html'].includes(entry[0])?"'self'":"'none'";
      if(entry[2])res.setHeader('Content-Disposition',entry[2]);
      res.writeHead(200,{'Content-Type':entry[1], 'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff',
        'Content-Security-Policy':`default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self'; connect-src ${connections}; object-src 'none'; base-uri 'none'; frame-ancestors 'none'`});
      res.end(req.method==='HEAD'?undefined:content);
    } catch(error) {
      res.writeHead(error.code==='ENOENT'?404:500);res.end('Asset unavailable');
    }
  });
  server.requestTimeout=15000;server.headersTimeout=10000;
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(port,host,resolve);});
  return server;
}
if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  const server=await startServer({port:Number(process.env.PORT??8765),host:process.env.HOST??'127.0.0.1'});
  console.log(`Painting study: http://${server.address().address}:${server.address().port}/`);
}
