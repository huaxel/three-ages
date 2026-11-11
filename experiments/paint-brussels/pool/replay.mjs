import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {renderProgram} from './render-program.mjs';
import {validatePool,POOL_ID} from './contract.mjs';
const root=fileURLToPath(new URL('../../../local/paint-brussels/pools/',import.meta.url));
const id=process.argv[2]??JSON.parse(await readFile(path.join(root,'current.json'),'utf8')).id;
if(!POOL_ID.test(id))throw Error('Invalid pool ID');
const dir=path.join(root,id),pool=validatePool(JSON.parse(await readFile(path.join(dir,'manifest.json'),'utf8'))),hash=b=>createHash('sha256').update(b).digest('hex');
for(const s of pool.sources)if(hash(await readFile(path.join(dir,'sources',s.id+'.jpg')))!==s.sha256)throw Error('Source bytes changed');
const checked=[];
for(const c of pool.candidates.filter(c=>c.status==='ready')){
 const folder=path.join(dir,'candidates',c.id,`r${c.revision}`),program=await readFile(path.join(folder,'program.js'),'utf8');
 if(hash(program)!==c.programSha256||hash(await readFile(path.join(folder,'render.png')))!==c.renderSha256)throw Error('Stored artifact bytes changed');
 let scene=null;if(c.renderKind==='structured-v1'){const bytes=await readFile(path.join(dir,'sources',c.sourceId+'.scene.json'));if(hash(bytes)!==c.structureSha256)throw Error('Stored geometry bytes changed');scene=JSON.parse(bytes);}
 const rendered=await renderProgram(program,{instrumentDir:path.join(dir,'instrument'),scene});
 if(rendered.metadata.renderSha256!==c.renderSha256)throw Error(`Replay changed: ${c.id}`);
 checked.push({id:c.id,revision:c.revision,programSha256:c.programSha256,renderSha256:c.renderSha256});console.log(c.id,'exact replay');
}
const file=path.join(root,`${id}-replay-${Date.now()}.json`);
await writeFile(file,JSON.stringify({poolId:id,at:new Date().toISOString(),outputTransport:'bounded-stdout; all host mounts read-only',additionalModelRequests:0,checked},null,2)+'\n',{flag:'wx'});
console.log('REPLAY CHECKED',checked.length,file);
