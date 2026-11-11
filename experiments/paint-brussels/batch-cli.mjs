import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {parseCatalog,parseSceneJSON,compileScene} from './scene-format.mjs';

try {
  const [action='validate',...files]=process.argv.slice(2);
  if(action!=='validate') throw new Error('Usage: node batch-cli.mjs validate [candidate.json ...]');
  const catalog=parseCatalog(await readFile(new URL('./batch-catalog.json',import.meta.url),'utf8'));
  const paths=files.length?files:catalog.items.map(item=>fileURLToPath(new URL(`./scenes/${item.scene}`,import.meta.url)));
  const report=[];
  for(const path of paths) {
    const data=await readFile(path,'utf8');
    const scene=parseSceneJSON(data);
    const item=catalog.items.find(item=>item.id===scene.source);
    if(!item||scene.id!==item.id) throw new Error(`${path}: scene identity does not match an approved source`);
    const marks=compileScene(scene);
    report.push({id:scene.id,elements:scene.elements.length,marks:marks.length,bytes:Buffer.byteLength(data),method:scene.method,omissions:scene.omissions.length});
  }
  console.log(JSON.stringify(report,null,2));
} catch(error) {
  console.error(`Scene validation failed: ${error.message}`);process.exitCode=1;
}
