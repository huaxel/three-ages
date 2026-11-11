import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {startServer} from './serve.mjs';

const output=fileURLToPath(new URL('../../local/paint-brussels/directions/',import.meta.url));
const server=await startServer();
let browser;
try {
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
  const page=await browser.newPage({viewport:{width:1440,height:1100}});
  const failures=[];
  page.on('pageerror',e=>failures.push(e.message));
  page.on('console',m=>{if(m.type()==='error') failures.push(m.text());});
  await mkdir(output,{recursive:true});
  const base=`http://127.0.0.1:${server.address().port}`;
  await page.goto(`${base}/directions.html`);
  async function ready() {
    await page.waitForFunction(()=>['ready','error'].includes(window.directionStudy?.state));
    const state=await page.evaluate(()=>window.directionStudy);
    assert.equal(state.state,'ready',state.error);
    return state;
  }
  const state=await ready();
  assert.deepEqual(Object.keys(state.results),['graphic','opaque','drawing','print','hybrid']);
  async function readPixels() {
    return page.evaluate(()=>Object.fromEntries([...document.querySelectorAll('.art-button canvas')].map(canvas=>{
      const pixels=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
      let count=0,min=255,max=0;
      for(let i=0;i<pixels.length;i+=4) {min=Math.min(min,pixels[i]);max=Math.max(max,pixels[i]);if(pixels[i+3]===255)count++;}
      if(max-min<50||count!==canvas.width*canvas.height) throw new Error('Blank or transparent painting');
      return [canvas.id.replace('treatment-',''),canvas.toDataURL('image/png')];
    })));
  }
  const original=await readPixels();
  const hashes={};
  for(const [id,png] of Object.entries(original)) {
    const bytes=Buffer.from(png.split(',')[1],'base64');
    await writeFile(`${output}${id}.png`,bytes);
    hashes[id]=createHash('sha256').update(bytes).digest('hex');
    const link=page.locator(`#treatment-${id}`).locator('..').locator('..').getByRole('link',{name:'Save PNG'});
    assert.equal(await link.getAttribute('href'),png);
    assert.equal(await link.getAttribute('download'),`brussels-001-${id}-seed29.png`);
  }
  assert.equal(new Set(Object.values(hashes)).size,5);
  assert.ok(await page.locator('#treatment-hybrid').evaluate(canvas=>{
    // The main study must have a colored field, not merely a warmer paper tint.
    const pixels=canvas.getContext('2d').getImageData(320,80,320,200).data;
    let saturated=0;
    for(let i=0;i<pixels.length;i+=4) {
      if(Math.max(pixels[i],pixels[i+1],pixels[i+2])-Math.min(pixels[i],pixels[i+1],pixels[i+2])>70) saturated++;
    }
    return saturated/(pixels.length/4)>.95;
  }));
  const readRestrained=()=>page.locator('#restrained-preview').evaluate(canvas=>canvas.toDataURL('image/png'));
  const restrained=await readRestrained();
  assert.notEqual(restrained,original.hybrid);
  assert.equal(await page.locator('#restrained-download').getAttribute('href'),restrained);
  assert.ok(await page.locator('#restrained-preview').evaluate(canvas=>{
    const pixels=canvas.getContext('2d').getImageData(320,80,320,200).data;
    for(let i=0;i<pixels.length;i+=4) {
      if(Math.abs(pixels[i]-244)>25||Math.abs(pixels[i+1]-239)>25||Math.abs(pixels[i+2]-223)>25) return false;
    }
    return true;
  }));
  const restrainedBytes=Buffer.from(restrained.split(',')[1],'base64');
  await writeFile(`${output}hybrid-restrained.png`,restrainedBytes);
  const restrainedHash=createHash('sha256').update(restrainedBytes).digest('hex');
  assert.ok(await page.locator('#direction-reference').evaluate(el=>el.complete&&el.naturalWidth===500));
  const sheet=await page.locator('#sheet-download').getAttribute('href');
  assert.ok(sheet.startsWith('data:image/png;base64,'));
  await writeFile(`${output}contact-sheet.png`,Buffer.from(sheet.split(',')[1],'base64'));
  const comparison=await page.locator('#hybrid-comparison-download').getAttribute('href');
  assert.ok(comparison.startsWith('data:image/png;base64,'));
  await writeFile(`${output}hybrid-comparison.png`,Buffer.from(comparison.split(',')[1],'base64'));
  const comparisonSize=await page.evaluate(async src=>{
    const img=new Image();img.src=src;await img.decode();return [img.naturalWidth,img.naturalHeight];
  },comparison);
  assert.deepEqual(comparisonSize,[2200,1000]);
  await page.screenshot({path:`${output}gallery-desktop.png`,fullPage:true});
  await page.getByRole('button',{name:'Rebuild the sheet'}).click();await ready();
  assert.deepEqual(await readPixels(),original,'Same-seed rebuild differs');
  assert.equal(await readRestrained(),restrained,'Retained study does not replay');
  await page.locator('[name=seed]').fill('30');
  await page.getByRole('button',{name:'Rebuild the sheet'}).click();await ready();
  const changed=await readPixels();
  assert.equal(changed.graphic,original.graphic,'Flat graphic treatment should not introduce random texture');
  for(const id of ['opaque','drawing','print','hybrid']) assert.notEqual(changed[id],original[id],`${id} ignores its seed`);
  assert.notEqual(await readRestrained(),restrained,'Retained study ignores the active seed');
  assert.equal(new URL(page.url()).searchParams.get('seed'),'30');
  await page.locator('[name=seed]').fill('29');
  await page.getByRole('button',{name:'Rebuild the sheet'}).click();await ready();
  assert.deepEqual(await readPixels(),original,'Rebuild after other seeds did not restore the original');
  assert.equal(await readRestrained(),restrained,'Retained study did not restore its original seed');
  await page.getByRole('button',{name:'Look closer: An architectural print'}).click();
  await page.waitForFunction(()=>document.querySelector('#detail-dialog').open);
  assert.equal(await page.locator('#detail-image').getAttribute('src'),original.hybrid);
  await page.screenshot({path:`${output}detail-desktop.png`});
  await page.keyboard.press('Escape');
  assert.ok(!await page.locator('#detail-dialog').evaluate(el=>el.open));
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:`${output}gallery-mobile.png`,fullPage:true});
  assert.ok(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth));
  for(const canvas of await page.locator('.art-button canvas').all()) {
    assert.ok(await canvas.evaluate(el=>{
      const a=el.getBoundingClientRect(),b=el.parentElement.getBoundingClientRect();
      return Math.abs(a.width-b.width)<1&&Math.abs(a.width-a.height)<1;
    }));
  }
  await page.getByRole('button',{name:'Look closer: An architectural print'}).click();
  await page.waitForFunction(()=>document.querySelector('#detail-dialog').open);
  await page.screenshot({path:`${output}detail-mobile.png`});
  assert.ok(await page.locator('#detail-dialog').evaluate(el=>el.scrollWidth<=el.clientWidth));
  await page.getByRole('button',{name:'Close ×'}).click();
  await page.getByText('The quieter version — kept for comparison',{exact:true}).click();
  assert.ok(await page.locator('#restrained-preview').isVisible());
  assert.ok(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth));
  await page.screenshot({path:`${output}retained-mobile.png`,fullPage:true});
  assert.deepEqual(failures,[]);
  await writeFile(`${output}render-checks.json`,JSON.stringify({seed:29,hashes,restrainedHash,checks:['nonblank opaque output','distinct directions','same-seed replay','seed change and restoration','PNG links','original four contact sheet','3/5/4 comparison export','saturated full-color sky','retained restrained hybrid','source loaded','desktop/mobile layouts','detail dialog and Escape']},null,2)+'\n');
  console.log('Five-direction browser checks passed',hashes,'retained hybrid:',restrainedHash);
} finally {
  if(browser) await browser.close();
  await new Promise(resolve=>server.close(resolve));
}
