// Runs INSIDE the isolated container, not on the credential-bearing model client.
import {chromium} from '/node_modules/playwright/index.mjs';
import {readFile} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import {networkInterfaces} from 'node:os';
import {createHash} from 'node:crypto';

let browser;
try {
  if(existsSync('/home/juan/.pi/agent/auth.json')) throw Error('Unexpected host credential mount');
  if(Object.keys(process.env).some(k=>/TOKEN|SECRET|API_KEY|AUTHORIZATION/i.test(k)))throw Error('Unexpected credential environment');
  if(Object.keys(networkInterfaces()).some(k=>k!=='lo'))throw Error('Unexpected network interface');
  const limits={memory:(await readFile('/sys/fs/cgroup/memory.max','utf8')).trim(),pids:(await readFile('/sys/fs/cgroup/pids.max','utf8')).trim(),cpu:(await readFile('/sys/fs/cgroup/cpu.max','utf8')).trim()};
  if(limits.memory!=='1610612736'||limits.pids!=='256'||limits.cpu!=='200000 100000') throw Error('Container resource limits not active');
  browser=await chromium.launch({headless:true,executablePath:'/ms-playwright/chromium-1217/chrome-linux64/chrome',args:['--js-flags=--max-old-space-size=128','--disable-dev-shm-usage']});
  const page=await browser.newPage({viewport:{width:1000,height:1000}});
  await page.setContent('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'unsafe-inline\'; connect-src \'none\'; img-src data:"><canvas id="painting" width="1000" height="1000"></canvas>');
  const canvas=await page.$('#painting');
  await canvas.evaluate(c=>{const x=c.getContext('2d');x.fillStyle='#f4efdf';x.fillRect(0,0,1000,1000);});
  await page.addScriptTag({path:'/app/paint-api.js'});
  const capturing=process.env.PAINT_CAPTURE==='1';
  if(capturing)await page.addScriptTag({path:'/app/capture-api.js'});
  if(process.env.PAINT_SCENE==='1'){
    const bytes=await readFile('/input/scene.json','utf8');if(Buffer.byteLength(bytes)>4*1024*1024)throw Error('Scene input exceeds budget');
    await page.evaluate(({scene,sha})=>{Object.defineProperty(window,'frozenScene',{value:scene,writable:false});Object.defineProperty(window,'frozenSceneSha256',{value:sha,writable:false});},{scene:JSON.parse(bytes),sha:createHash('sha256').update(bytes).digest('hex')});
  }
  await page.addScriptTag({path:'/input/program.js'});
  await page.evaluate(capture=>{if(typeof paint!=='function')throw Error('Missing paint(p) function');const result=paint(capture?capturePainter():painter);if(result&&typeof result.then==='function')throw Error('paint(p) must be synchronous');},capturing);
  const capture=capturing?await page.evaluate(()=>{const marks=readCapture();if(JSON.stringify(marks).length>4*1024*1024)throw Error('Capture output exceeds budget');return marks;}):null;
  const result=await canvas.evaluate(c=>{
    if(c.width!==1000||c.height!==1000)throw Error('Canvas size changed');
    const d=c.getContext('2d').getImageData(0,0,1000,1000).data;
    let min=255,max=0,opaque=0;
    for(let i=0;i<d.length;i+=4){min=Math.min(min,d[i],d[i+1],d[i+2]);max=Math.max(max,d[i],d[i+1],d[i+2]);if(d[i+3]===255)opaque++;}
    if(max-min<35||opaque!==1000000)throw Error('Blank or transparent output');
    return {png:c.toDataURL('image/png'),stats:window.paintStats};
  });
  if(result.stats.calls<5) throw Error('Painting did not use the instrument meaningfully');
  const png=Buffer.from(result.png.split(',')[1],'base64');if(png.length>8_000_000)throw Error('Output exceeds image budget');
  console.log(JSON.stringify({ok:true,...(capture?{capture}:{}),png:png.toString('base64'),stats:result.stats,browser:browser.version(),limits,network:'none',referencePixelsMounted:false}));
} catch(error) {console.log(JSON.stringify({ok:false,error:String(error.message).slice(-2400)}));process.exitCode=1;}
finally {if(browser)await browser.close();}
