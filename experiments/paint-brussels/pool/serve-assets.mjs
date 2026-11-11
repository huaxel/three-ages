import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {validatePool,POOL_ID,HASH} from './contract.mjs';

const root=fileURLToPath(new URL('../../../local/paint-brussels/pools/',import.meta.url));
const base=fileURLToPath(new URL('../',import.meta.url));
export async function poolAsset(url,{rootDir=root}={}) {
  const metadata=url.match(/^\/pool\/(pool-\d{13}-[a-f0-9]{8})\.json$/);
  const artifact=url.match(/^\/pool-data\/(pool-\d{13}-[a-f0-9]{8})\//);
  const current=url==='/pool/current.json';if(!current&&!metadata&&!artifact)return null;
  let id=metadata?.[1]??artifact?.[1];
  if(current){let pointer;try{pointer=JSON.parse(await readFile(path.join(rootDir,'current.json'),'utf8'));}catch(e){if(e.code==='ENOENT')return null;throw e;}id=pointer.id;}
  if(typeof id!=='string'||!POOL_ID.test(id))throw Error('Invalid pool pointer');
  const dir=path.join(rootDir,id),manifest=path.join(dir,'manifest.json');
  const pool=validatePool(JSON.parse(await readFile(manifest,'utf8')));
  if(pool.id!==id)throw Error('Pool identity mismatch');
  if(current||metadata)return [path.relative(base,manifest),'application/json'];
  const paths=new Map();
  for(const s of pool.sources){paths.set(`/pool-data/${pool.id}/sources/${s.id}.jpg`,[path.join(dir,'sources',s.id+'.jpg'),'image/jpeg',undefined,s.sha256]);if(pool.reviewMode==='shortlist'&&HASH.test(s.structureSha256??''))paths.set(`/pool-data/${pool.id}/sources/${s.id}.scene.json`,[path.join(dir,'sources',s.id+'.scene.json'),'application/json','attachment',s.structureSha256]);}
  for(const c of pool.candidates.filter(c=>c.status==='ready')) {
    const prefix=`/pool-data/${pool.id}/candidates/${c.id}/r${c.revision}`;
    paths.set(prefix+'/render.png',[path.join(dir,'candidates',c.id,`r${c.revision}`,'render.png'),'image/png',undefined,c.renderSha256]);
    // Raw program code is download-only plain text, not executable script content.
    paths.set(prefix+'/program.js',[path.join(dir,'candidates',c.id,`r${c.revision}`,'program.js'),'text/plain; charset=utf-8','attachment',c.programSha256]);
  }
  const entry=paths.get(url);return entry?[path.relative(base,entry[0]),entry[1],entry[2],entry[3]]:null;
}
