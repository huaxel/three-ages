// Trusted HOST-side supervisor. It only edits its own freshly created systemd scope.
import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
const [name,json]=process.argv.slice(2);
if(!/^brussels-paint-[a-f0-9-]{36}$/.test(name))throw Error('Invalid task-owned scope name');
const cg=readFileSync('/proc/self/cgroup','utf8').trim().split(':').at(-1);
if(!cg.endsWith(`/${name}.scope`))throw Error('Not inside the expected task-owned user scope');
const supervisor=`/sys/fs/cgroup${cg}/supervisor`;
mkdirSync(supervisor);writeFileSync(supervisor+'/cgroup.procs',String(process.pid));
// Moving this supervisor out leaves the delegated parent empty, as cgroup v2 requires.
const args=JSON.parse(json);
if(args[0]!=='run'||!args.includes('--network=none')||!args.includes('--read-only'))throw Error('Unexpected container policy');
for(let i=0;i<args.length;i++)if(args[i]==='-v'&&!args[i+1]?.endsWith(':ro'))throw Error('Writable host mounts are forbidden');
const result=spawnSync('podman',['--cgroup-manager=cgroupfs','run','--cgroup-parent',cg,...args.slice(1)],{stdio:'inherit'});
process.exitCode=result.status??1;
