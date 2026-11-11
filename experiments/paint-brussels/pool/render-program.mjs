import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomUUID,createHash} from 'node:crypto';
import {validateStructure} from './structure-contract.mjs';

const exec=promisify(execFile);
export const RENDER_IMAGE='fc1610b07935476ac20219b7911f6bbe47ac861523635845ba0bc7cc5f0277c4';
export async function renderProgram(program,{timeout=35000,instrumentDir=fileURLToPath(new URL('.',import.meta.url)),capture=false,scene=null}={}) {
  if(typeof program!=='string'||Buffer.byteLength(program)>65536)throw Error('Program exceeds 64 KiB');
  if(scene)validateStructure(scene);
  const work=await mkdtemp(path.join(os.tmpdir(),'brussels-paint-'));
  const name=`brussels-paint-${randomUUID()}`;
  const app=fileURLToPath(new URL('.',import.meta.url));
  const instrument=path.resolve(instrumentDir);
  const modules=fileURLToPath(new URL('../node_modules/',import.meta.url));
  try {
    await writeFile(path.join(work,'program.js'),program,{flag:'wx'});
    if(scene)await writeFile(path.join(work,'scene.json'),JSON.stringify(scene),{flag:'wx'});
    const args=['run','--name',name,'--rm','--pull=never','--http-proxy=false','--network=none','--read-only','--memory=1536m','--cpus=2','--pids-limit=256','--tmpfs','/tmp:rw,nosuid,size=512m','--cap-drop=all','--security-opt=no-new-privileges','--env','HOME=/tmp','--env','XDG_CONFIG_HOME=/tmp/config','--env','XDG_CACHE_HOME=/tmp/cache','-v',`${app}/container-render.mjs:/app/container-render.mjs:ro`,'-v',`${instrument}/paint-api.js:/app/paint-api.js:ro`,'-v',`${modules}:/node_modules:ro`,'-v',`${work}:/input:ro`,RENDER_IMAGE,'node','/app/container-render.mjs'];
    if(capture)args.splice(1,0,'--env','PAINT_CAPTURE=1','-v',`${app}/capture-api.js:/app/capture-api.js:ro`);
    if(scene)args.splice(1,0,'--env','PAINT_SCENE=1');
    let stdout,exitWarning=null;
    const launcher=fileURLToPath(new URL('./scope-launch.mjs',import.meta.url));
    const scoped=['--user','--scope','--quiet','--collect','--expand-environment=no',`--unit=${name}`,'-p','Delegate=yes','-p','MemoryMax=1536M','-p','TasksMax=256','-p','CPUQuota=200%',process.execPath,launcher,name,JSON.stringify(args)];
    try {({stdout}=await exec('systemd-run',scoped,{timeout,killSignal:'SIGKILL',maxBuffer:16*1024*1024}));}
    catch(error) {stdout=error.stdout??'';exitWarning=(error.stderr||error.message).slice(-1000);}
    let meta;try{meta=JSON.parse(stdout.trim().split('\n').at(-1));}catch{throw Error(`Renderer infrastructure failure: ${exitWarning??'No renderer result'}`);}
    if(!meta.ok)throw Error(`Painting program failed: ${meta.error}`);
    if(exitWarning)meta.infrastructureWarning=exitWarning;
    meta.resourceScope='delegated-user-scope';
    // Bounded stdout is the only output channel. No writable host mount, file,
    // symlink or FIFO from the renderer is ever opened on the host.
    const encoded=meta.png;delete meta.png;
    if(typeof encoded!=='string'||encoded.length>10_666_668)throw Error('Invalid render payload');
    const png=Buffer.from(encoded,'base64');
    if(png.length<24||png.length>8_000_000||png.toString('base64')!==encoded)throw Error('Invalid render payload');
    if(!png.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))||png.readUInt32BE(16)!==1000||png.readUInt32BE(20)!==1000)throw Error('Invalid PNG dimensions/header');
    return {png,metadata:{...meta,image:RENDER_IMAGE,programSha256:createHash('sha256').update(program).digest('hex'),renderSha256:createHash('sha256').update(png).digest('hex')}};
  } finally {
    await exec('podman',['rm','--force','--ignore',name],{timeout:10000}).catch(()=>{});
    await exec('systemctl',['--user','stop',`${name}.scope`],{timeout:10000}).catch(()=>{});
    let cleanupFailure=null;
    try {await exec('podman',['container','exists',name],{timeout:10000});cleanupFailure='Task-owned render container still exists after cleanup';}
    catch(error){if(error.code!==1)cleanupFailure=`Container cleanup verification failed: ${(error.stderr||error.message).slice(-500)}`;}
    await rm(work,{recursive:true,force:true});
    if(cleanupFailure)throw Error(cleanupFailure);
  }
}
