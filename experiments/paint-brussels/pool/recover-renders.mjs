import {readFile,writeFile,mkdir,cp,rename} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {createHash,randomUUID} from 'node:crypto';
import {renderProgram} from './render-program.mjs';
import {validatePool,POOL_ID} from './contract.mjs';
const parentId=process.argv[2];if(!POOL_ID.test(parentId??''))throw Error('Supply a completed pool ID');
const root=fileURLToPath(new URL('../../../local/paint-brussels/pools/',import.meta.url)),old=path.join(root,parentId);
const original=validatePool(JSON.parse(await readFile(path.join(old,'manifest.json'),'utf8')));
const id=`pool-${Date.now()}-${randomUUID().slice(0,8)}`,dir=path.join(root,id);await mkdir(dir);
for(const name of ['sources','instrument','candidates'])await cp(path.join(old,name),path.join(dir,name),{recursive:true,errorOnExist:true,force:false});
const pool={...original,id,parentPoolId:parentId,createdAt:new Date().toISOString(),status:'draft',candidates:[],recovery:'Unchanged programs rerendered under delegated user-scope limits; original failure records retained.',additionalModelRequests:0};
let visual=0;
for(const candidate of original.candidates) {
  const ready=[];
  for(const revision of [0,1]) {
    const folder=path.join(dir,'candidates',candidate.id,`r${revision}`);
    let record;try{record=JSON.parse(await readFile(path.join(folder,'record.json'),'utf8'));}catch(e){if(e.code==='ENOENT')continue;throw e;}
    let program;try{program=await readFile(path.join(folder,'program.js'),'utf8');}catch(e){if(e.code==='ENOENT')continue;throw e;}
    if(createHash('sha256').update(program).digest('hex')!==record.programSha256)throw Error('Program bytes changed');
    const recovery={at:new Date().toISOString(),originalStatus:record.status,originalError:record.error??null};
    try {
      const rendered=await renderProgram(program,{instrumentDir:path.join(dir,'instrument')});
      const replay=await renderProgram(program,{instrumentDir:path.join(dir,'instrument')});
      if(rendered.metadata.renderSha256!==replay.metadata.renderSha256)throw Error('Program replay is not deterministic');
      if(record.status==='ready'&&record.render.renderSha256!==rendered.metadata.renderSha256)throw Error('Previously successful render changed');
      await writeFile(path.join(folder,'render.png'),rendered.png);
      recovery.status='ready';recovery.render=rendered.metadata;ready.push({...record,revision,render:rendered.metadata});
      console.log(candidate.id,`r${revision}`,'recovered + replayed');
    } catch(error){recovery.status='failed';recovery.error=String(error.message);console.log(candidate.id,`r${revision}`,'failed:',recovery.error.slice(0,140));}
    await writeFile(path.join(folder,'render-recovery.json'),JSON.stringify(recovery,null,2)+'\n',{flag:'wx'});
  }
  const active=ready.at(-1);
  if(active?.revision===1&&active.feedbackRenderSha256)visual++;
  pool.candidates.push(active?{id:candidate.id,sourceId:candidate.sourceId,status:'ready',revision:active.revision,title:active.title,programSha256:active.programSha256,renderSha256:active.render.renderSha256,feedbackKind:active.feedbackRenderSha256?'visual':'text-or-infrastructure-repair'}:{id:candidate.id,sourceId:candidate.sourceId,status:'failed'});
  await writeFile(path.join(dir,'recovery-progress.json'),JSON.stringify({id,done:pool.candidates.length,total:original.candidates.length})+'\n');
}
pool.visualFeedbackCandidates=visual;pool.status='complete';pool.completedAt=new Date().toISOString();validatePool(pool);
await writeFile(path.join(dir,'manifest.json'),JSON.stringify(pool,null,2)+'\n',{flag:'wx'});
await writeFile(path.join(root,'current.tmp'),JSON.stringify({id})+'\n');await rename(path.join(root,'current.tmp'),path.join(root,'current.json'));
console.log('RECOVERED POOL',id,pool.candidates.filter(c=>c.status==='ready').length,'ready;',visual,'visual-feedback candidates; no new model requests');
