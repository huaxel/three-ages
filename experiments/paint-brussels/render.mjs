import {chromium} from 'playwright';
import {mkdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {startServer} from './serve.mjs';

const output=fileURLToPath(new URL('../../local/paint-brussels/',import.meta.url));
const server=await startServer();
let browser;
try {
  browser=await chromium.launch({headless:true,
    ...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),
    args:['--enable-unsafe-swiftshader','--use-angle=swiftshader']});
  const page=await browser.newPage({viewport:{width:1440,height:1200}});
  const failures=[];
  page.on('pageerror',e=>failures.push(e.message));
  page.on('console',m=>{if(m.type()==='error') failures.push(m.text());});
  const base=`http://127.0.0.1:${server.address().port}`;
  await mkdir(output,{recursive:true});
  await page.goto(base);
  async function ready() {
    await page.waitForFunction(()=>['ready','error'].includes(window.paintStudy?.state),{},{timeout:180000});
    const state=await page.evaluate(()=>window.paintStudy);
    if(state.state!=='ready') throw new Error(state.error);
    if(!state.png.startsWith('data:image/png;base64,')) throw new Error('No PNG produced');
    return state;
  }
  async function save(name) {
    const state=await ready();
    const bytes=Buffer.from(state.png.split(',')[1],'base64');
    await writeFile(`${output}${name}.png`,bytes);
    return {marks:state.marks,sha256:createHash('sha256').update(bytes).digest('hex'),options:state.options};
  }
  const results={full:await save('painting')};
  if(!await page.locator('#reference').evaluate(el=>el.complete&&el.naturalWidth===500)) throw new Error('Pinned reference not loaded');
  async function fittedCanvas() {
    const fit=await page.locator('#paint-canvas').evaluate(el=>{
      const a=el.getBoundingClientRect(),b=el.parentElement.getBoundingClientRect();
      return Math.abs(a.width-b.width)<1 && Math.abs(a.height-b.height)<1;
    });
    if(!fit) throw new Error('Painting canvas is clipped instead of fitted');
  }
  await fittedCanvas();
  await page.screenshot({path:`${output}studio-desktop.png`,fullPage:true});
  // Same engine instance, same seed: verify replay after a second paint.
  await page.getByRole('button',{name:'Paint again'}).click();
  results.replay=await save('replay');
  if(results.full.sha256!==results.replay.sha256) throw new Error('Same-seed repaint differs');
  await page.locator('[name=stage]').selectOption('1');
  await page.getByRole('button',{name:'Paint again'}).click();
  results.masses=await save('masses');
  await page.locator('[name=stage]').selectOption('2');
  await page.getByRole('button',{name:'Paint again'}).click();
  results.rhythm=await save('rhythm');
  await page.locator('[name=stage]').selectOption('3');
  await page.locator('[name=palette]').selectOption('dusk');
  await page.getByRole('button',{name:'Paint again'}).click();
  results.dusk=await save('dusk');
  if(new Set([results.full.sha256,results.masses.sha256,results.rhythm.sha256,results.dusk.sha256]).size!==4) throw new Error('Painting controls did not change the image');
  await page.setViewportSize({width:390,height:844});
  await fittedCanvas();
  await page.screenshot({path:`${output}studio-mobile.png`,fullPage:true});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw new Error('Mobile page overflows');
  if(failures.length) throw new Error(failures.join('\n'));
  await writeFile(`${output}render-checks.json`,JSON.stringify(results,null,2)+'\n');
  console.log(JSON.stringify(results,null,2));
} finally {
  if(browser) await browser.close();
  await new Promise(resolve=>server.close(resolve));
}
