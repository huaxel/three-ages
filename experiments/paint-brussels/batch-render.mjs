import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {startServer} from './serve.mjs';
import {parseCatalog} from './scene-format.mjs';

const catalog=parseCatalog(await readFile(new URL('./batch-catalog.json',import.meta.url),'utf8'));
const output=fileURLToPath(new URL('../../local/paint-brussels/batch/renders/',import.meta.url));
for(const item of catalog.items) {
  const bytes=await readFile(new URL(`../../local/paint-brussels/batch/${item.file}`,import.meta.url));
  assert.equal(createHash('sha256').update(bytes).digest('hex'),item.sha256,'Local source checksum differs');
}
const server=await startServer();let browser;
try {
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
  const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  const base=`http://127.0.0.1:${server.address().port}`;
  await page.goto(base+'/batch.html');
  async function ready(target=page) {
    await target.waitForFunction(()=>['ready','error'].includes(window.batchStudy?.state));
    const state=await target.evaluate(()=>window.batchStudy);assert.equal(state.state,'ready',state.error);return state;
  }
  const initial=await ready();
  assert.deepEqual(initial.report.map(r=>r.id),catalog.items.map(i=>i.id));
  await page.waitForFunction(()=>[...document.querySelectorAll('.source-image')].every(img=>img.complete&&img.naturalWidth===500));
  async function pixels() {
    return page.evaluate(()=>Object.fromEntries([...document.querySelectorAll('.study-pair canvas')].map(canvas=>{
      const data=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
      let min=255,max=0;
      for(let i=0;i<data.length;i+=4) {min=Math.min(min,data[i]);max=Math.max(max,data[i]);if(data[i+3]!==255)throw new Error('Transparent painting');}
      if(max-min<60) throw new Error('Blank painting');
      return [canvas.id.slice(6),canvas.toDataURL('image/png')];
    })));
  }
  const original=await pixels(),hashes={};await mkdir(output,{recursive:true});
  for(const item of catalog.items) {
    const png=original[item.id],bytes=Buffer.from(png.split(',')[1],'base64');
    await writeFile(output+item.id+'.png',bytes);hashes[item.id]=createHash('sha256').update(bytes).digest('hex');
    const card=page.locator(`#${item.id}`);
    assert.equal(await card.getByRole('link',{name:'Save PNG'}).getAttribute('href'),png);
    assert.equal(await card.getByRole('link',{name:'Scene JSON'}).getAttribute('href'),`/scenes/${item.scene}`);
  }
  assert.equal(new Set(Object.values(hashes)).size,catalog.items.length);
  const sheet=await page.locator('#batch-download').getAttribute('href');assert.ok(sheet.startsWith('data:image/png;base64,'));
  await writeFile(output+'contact-sheet.png',Buffer.from(sheet.split(',')[1],'base64'));
  const size=await page.evaluate(async src=>{const img=new Image();img.src=src;await img.decode();return [img.naturalWidth,img.naturalHeight];},sheet);
  assert.deepEqual(size,[2200,1000]);
  await page.screenshot({path:output+'batch-desktop.png',fullPage:true});
  await page.getByRole('button',{name:'Repaint collection'}).click();await ready();assert.deepEqual(await pixels(),original);
  await page.locator('[name=seed]').fill('30');await page.getByRole('button',{name:'Repaint collection'}).click();await ready();
  const changed=await pixels();for(const id of Object.keys(original)) assert.notEqual(changed[id],original[id]);
  await page.locator('[name=seed]').fill('29');await page.getByRole('button',{name:'Repaint collection'}).click();await ready();assert.deepEqual(await pixels(),original);
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:output+'batch-mobile.png',fullPage:true});
  assert.ok(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth));
  for(const canvas of await page.locator('.study-pair canvas').all()) assert.ok(await canvas.evaluate(el=>{
    const a=el.getBoundingClientRect(),b=el.parentElement.getBoundingClientRect();return Math.abs(a.width-b.width)<1&&Math.abs(a.width-a.height)<1;
  }));
  await page.locator('.study-detail summary').first().click();assert.ok(await page.locator('.study-detail ul').first().isVisible());
  assert.deepEqual(errors,[]);
  const occlusion=await page.evaluate(async()=>{
    const {renderTreatment}=await import('/treatments.mjs');
    const base={version:1,id:'occlusion',source:'occlusion',title:'Occlusion fixture',method:'agent-visual-interpretation',omissions:[],view:[0,0,500,500],elements:[
      {type:'polygon',id:'first-mask',role:'context',points:[[100,200],[300,200],[300,300],[100,300]]},
      {type:'polygon',id:'second-mask',role:'context',points:[[200,150],[400,150],[400,350],[200,350]]}
    ]};
    function render(scene) {const c=document.createElement('canvas');c.width=c.height=1000;renderTreatment(c,'hybrid',{seed:29,scene});return c.getContext('2d');}
    const clean=render(base),ink=render({...base,elements:[{type:'line',id:'behind',role:'outline',width:3,points:[[50,250],[450,250]]},...base.elements]});
    const light=render({...base,elements:[{type:'line',id:'behind',role:'light',width:3,points:[[50,250],[450,250]]},...base.elements]});
    const pixel=(ctx,x)=>Array.from(ctx.getImageData(x*2,500,1,1).data);
    const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
    return {single:equal(pixel(clean,150),pixel(ink,150)),overlap:equal(pixel(clean,250),pixel(ink,250)),outside:!equal(pixel(clean,60),pixel(ink,60)),light:pixel(light,60)[1]>pixel(clean,60)[1]};
  });
  assert.deepEqual(occlusion,{single:true,overlap:true,outside:true,light:true});
  // A model response with invalid geometry must fail before any canvas is built.
  const invalid=await browser.newPage();
  await invalid.route('**/scenes/ackermans.json',async route=>{
    const scene=JSON.parse(await readFile(new URL('./scenes/ackermans.json',import.meta.url),'utf8'));
    scene.elements[0].points[0][0]=501;
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(scene)});
  });
  await invalid.goto(base+'/batch.html');await invalid.waitForFunction(()=>window.batchStudy?.state==='error');
  assert.equal(await invalid.locator('canvas').count(),0);
  assert.equal(await invalid.locator('#batch-download').getAttribute('href'),null);await invalid.close();
  const missing=await browser.newPage();
  await missing.route('**/local/paint-brussels/batch/162253721064.jpg',route=>route.fulfill({status:404,body:'Missing'}));
  await missing.goto(base+'/batch.html');await ready(missing);
  assert.ok(await missing.locator('.source-missing').first().isVisible());await missing.close();
  const report={seed:29,scenes:initial.report,hashes,checks:['pinned reference bytes','distinct nonblank paintings','source and PNG links','contact sheet','seed replay and restoration','mobile fitting','visible omissions','invalid scene fails before drawing','missing reference fallback','overlapping foreground masks hide earlier lines','compiled light strokes retain their ink role']};
  await writeFile(output+'render-checks.json',JSON.stringify(report,null,2)+'\n');console.log('Batch browser checks passed',report);
} finally {if(browser) await browser.close();await new Promise(resolve=>server.close(resolve));}
