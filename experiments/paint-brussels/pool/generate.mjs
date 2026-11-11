import {readFile,writeFile,mkdir,copyFile,rename,access} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {createHash,randomUUID} from 'node:crypto';
import {modelClient} from './model-client.mjs';
import {renderProgram,RENDER_IMAGE} from './render-program.mjs';
import {parsePainting,validatePool,POOL_ID} from './contract.mjs';
import {validatePlan,planTasks} from './task-plan.mjs';

const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const root=fileURLToPath(new URL('../../../local/paint-brussels/pools/',import.meta.url));
const args=process.argv.slice(2),arg=name=>args.includes(name)?args[args.indexOf(name)+1]:null;
for(let i=0;i<args.length;i+=2)if(!['--plan','--limit','--resume','--brief','--revision-goal','--history','--activate'].includes(args[i])||!args[i+1]||args[i+1].startsWith('--')||args.indexOf(args[i])!==i)throw Error('Expected unique supported generation options with values');
const plan=validatePlan(JSON.parse(await readFile(arg('--plan')??new URL('./plan.json',import.meta.url),'utf8')));
const brief=await readFile(arg('--brief')??new URL('./painting-brief.txt',import.meta.url),'utf8'),revisionGoal=arg('--revision-goal')?await readFile(arg('--revision-goal'),'utf8'):null,history=arg('--history')?JSON.parse(await readFile(arg('--history'),'utf8')):{};const historySha256=Object.keys(history).length?hash(JSON.stringify(history)):null;if(arg('--activate')&&!['true','false'].includes(arg('--activate')))throw Error('Expected --activate true or false');
const allTasks=planTasks(plan),requestBudget=allTasks.length*2;
const limit=Number(arg('--limit')??allTasks.length),resume=arg('--resume');
if(!Number.isInteger(limit)||limit<1||limit>allTasks.length||resume&&!POOL_ID.test(resume))throw Error('Invalid candidate limit or resume pool ID');
const id=resume??`pool-${Date.now()}-${randomUUID().slice(0,8)}`,dir=path.join(root,id);
await mkdir(root,{recursive:true});
let state;
if(resume) {
  try {await access(path.join(dir,'manifest.json'));throw Error('Completed pools are immutable; start a new run');}
  catch(error){if(error.code!=='ENOENT')throw error;}
  state=JSON.parse(await readFile(path.join(dir,'draft.json'),'utf8'));
  if(state.briefSha256!==hash(brief)||state.planSha256!==hash(JSON.stringify(plan))||(state.revisionGoalSha256??null)!==(revisionGoal?hash(revisionGoal):null)||(state.historySha256??null)!==historySha256)throw Error('Resume requires the same brief and source plan');
} else {
  await mkdir(dir);await mkdir(path.join(dir,'sources'));await mkdir(path.join(dir,'candidates'));await mkdir(path.join(dir,'instrument'));
  for(const name of ['paint-api.js','container-render.mjs'])await copyFile(new URL(name,import.meta.url),path.join(dir,'instrument',name));
  const sources=[];
  for(const source of plan.subjects) {
    const bytes=await readFile(new URL(`../../../local/paint-brussels/batch/detail-references/${source.id}.jpg`,import.meta.url));
    if(hash(bytes)!==source.sha256)throw Error(`Source bytes changed: ${source.id}`);
    await writeFile(path.join(dir,'sources',source.id+'.jpg'),bytes,{flag:'wx'});sources.push(source);
  }
  await writeFile(path.join(dir,'source-plan.json'),JSON.stringify(plan,null,2)+'\n',{flag:'wx'});
  state={version:1,id,status:'draft',activateOnComplete:arg('--activate')!=='false',revisionGoalSha256:revisionGoal?hash(revisionGoal):null,historySha256,...(plan.experiment?.kind==='persona-organic-v1'?{reviewMode:'shortlist'}:{}),pairingVersion:plan.experiment?2:1,...(plan.experiment?{experiment:plan.experiment}:{}),createdAt:new Date().toISOString(),sources,candidates:[],requests:0,briefSha256:hash(brief),planSha256:hash(JSON.stringify(plan)),instrumentSha256:hash(await readFile(path.join(dir,'instrument/paint-api.js'))),rendererImage:RENDER_IMAGE};
}
const activate=arg('--activate')===null?state.activateOnComplete!==false:arg('--activate')==='true';state.activateOnComplete=activate;
let saveQueue=Promise.resolve();
const save=()=>{saveQueue=saveQueue.then(async()=>{await writeFile(path.join(dir,'draft.tmp'),JSON.stringify(state,null,2)+'\n');await rename(path.join(dir,'draft.tmp'),path.join(dir,'draft.json'));});return saveQueue;};
await save();console.log('POOL',id);
const client=await modelClient();
if(state.model&&(state.model.id!==client.model||state.model.provider!==client.provider))throw Error('Resume must use the original generator model');
state.model={provider:client.provider,id:client.model};await save();
const tasks=allTasks.slice(0,limit);
async function candidate(task) {
  if(state.candidates.some(c=>c.id===task.id))return;
  const candidateDir=path.join(dir,'candidates',task.id);await mkdir(candidateDir,{recursive:true});
  const source=await readFile(path.join(dir,'sources',task.source.id+'.jpg'));
  const base=`${brief}\n\nSUBJECT: ${task.source.title}.\nARTISTIC DIRECTION: ${task.direction}\nThis is an independent candidate; invent your own composition and painting program. Do not merely vary a seed or palette of a shared facade template.`;
  const past=history[task.id];let historyImage=null;if(past){if(past.sourceSha256!==task.source.sha256)throw Error('Prior work belongs to a different source');const bytes=await readFile(past.imagePath);if(hash(bytes)!==past.renderSha256)throw Error('Prior work image bytes changed');historyImage={bytes,mimeType:'image/png'};}
  const revisions=[];let previous=null,feedback=null;
  for(let revision=0;revision<2;revision++) {
    const revisionDir=path.join(candidateDir,`r${revision}`);await mkdir(revisionDir,{recursive:true});
    const prompt=revision===0?base+(historyImage?'\nImage2 is an earlier working painting, not an approved favourite. Use it as evidence of what to evolve, not as a tracing template. Earlier observation: '+past.note:''):`${base}\n\nREVISION PASS. Image 1 is the original. ${previous?.png?'Image 2 is your previous render. '+(revisionGoal??'Inspect it against the original: retain the colour atmosphere, but correct lost architectural character, oversimplified forms and generic/noisy detail. Revise the actual painting program, not the instrument. Describe what you changed in intent.'):'The previous attempt failed; repair it.'}\nPrevious response:\n${feedback?.text??''}\nRenderer feedback: ${feedback?.error??'Rendered successfully; visual quality has not been scored.'}`;
    const images=[{bytes:source,mimeType:'image/jpeg'},...(revision===0&&historyImage?[historyImage]:previous?.png?[{bytes:previous.png,mimeType:'image/png'}]:[])];
    const record={revision,requestedAt:new Date().toISOString(),prompt,sourceSha256:task.source.sha256,feedbackRenderSha256:previous?.metadata?.renderSha256??null,priorWorkRenderSha256:revision===0&&historyImage?past.renderSha256:null,priorWorkSourceSha256:revision===0&&historyImage?(past.referenceSourceSha256??past.sourceSha256):null,model:state.model};
    if(state.requests>=requestBudget)throw Error('Pilot request budget exhausted');state.requests++;await save();
    console.log(task.id,`r${revision}`,`request ${state.requests}/${requestBudget}`);
    try {
      const response=await client.complete(prompt,images);
      await writeFile(path.join(revisionDir,'response.txt'),response.text,{flag:'wx'});
      record.usage={input:response.usage.input,output:response.usage.output,total:response.usage.totalTokens};
      const painting=parsePainting(response.text);
      await writeFile(path.join(revisionDir,'program.js'),painting.program,{flag:'wx'});
      record.title=painting.title;record.intent=painting.intent;record.simplifications=painting.simplifications;record.programSha256=hash(painting.program);
      const rendered=await renderProgram(painting.program,{instrumentDir:path.join(dir,'instrument')});
      const replay=await renderProgram(painting.program,{instrumentDir:path.join(dir,'instrument')});
      if(replay.metadata.renderSha256!==rendered.metadata.renderSha256)throw Error('Program render is not deterministic');
      await writeFile(path.join(revisionDir,'render.png'),rendered.png,{flag:'wx'});
      record.status='ready';record.render=rendered.metadata;previous=rendered;
      feedback={text:response.text};
      console.log(task.id,`r${revision}`,'rendered',rendered.metadata.stats.calls,'calls');
    } catch(error) {
      record.status='failed';record.error=String(error.message).slice(0,1200);
      feedback={text:await readFile(path.join(revisionDir,'response.txt'),'utf8').catch(()=>''),error:record.error};
      console.log(task.id,`r${revision}`,'failed:',record.error.slice(0,160));
    }
    record.finishedAt=new Date().toISOString();await writeFile(path.join(revisionDir,'record.json'),JSON.stringify(record,null,2)+'\n',{flag:'wx'});revisions.push(record);
  }
  const active=[...revisions].reverse().find(r=>r.status==='ready');
  const persona=plan.experiment?.kind==='persona-organic-v1'?plan.experiment.personas[task.index]:null;const result=active?{...(persona?{styleId:persona.id,variant:0,renderKind:'free-program-v1',operatorSha256:active.programSha256,personaId:persona.id,personaStyleVersion:persona.styleVersion,proposalSha256:persona.proposalSha256,role:'proposal'}:{}),id:task.id,sourceId:task.source.id,status:'ready',revision:active.revision,title:active.title,feedbackKind:active.feedbackRenderSha256?'visual':active.revision===0?'initial-only':'text-repair',programSha256:active.programSha256,renderSha256:active.render.renderSha256}:{id:task.id,sourceId:task.source.id,status:'failed'};
  state.candidates.push(result);await save();
}
try {
  // Bounded parallelism: four generation/render jobs, each with its own isolated container.
  let next=0;await Promise.all(Array.from({length:4},async()=>{while(next<tasks.length){const task=tasks[next++];await candidate(task);}}));
  await saveQueue;
  if(state.candidates.length===allTasks.length) {
    state.visualFeedbackCandidates=state.candidates.filter(c=>c.feedbackKind==='visual').length;
    state.candidates.sort((a,b)=>a.id.localeCompare(b.id));state.status='complete';state.completedAt=new Date().toISOString();
    validatePool(state);await writeFile(path.join(dir,'manifest.json'),JSON.stringify(state,null,2)+'\n',{flag:'wx'});
    if(activate){const pointerTemp=path.join(root,`${id}-current.tmp`);await writeFile(pointerTemp,JSON.stringify({id})+'\n');await rename(pointerTemp,path.join(root,'current.json'));}else console.log('VERIFIED POOL NOT ACTIVATED');
    console.log('COMPLETE',id,state.candidates.filter(c=>c.status==='ready').length,'ready');
  } else console.log('PARTIAL',id,state.candidates.length,'candidates; resume with --resume',id,`--limit ${allTasks.length} (supply the same --plan if non-default)`);
} finally {await client.close();}
