import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {makeScene, selectedMarks, optionsFrom, pointOn, patch, PALETTES, SOURCE} from './scene.mjs';
import {startServer} from './serve.mjs';

test('scene has unique named, bounded marks and valid palette roles',()=>{
  const marks=makeScene();
  assert.equal(new Set(marks.map(m=>m.name)).size,marks.length);
  for(const m of marks) {
    assert.ok(['line','wash'].includes(m.kind));
    assert.ok([1,2,3].includes(m.stage));
    assert.ok(m.points.length >= (m.kind==='wash'?3:2));
    for(const [x,y] of m.points) assert.ok(Number.isFinite(x)&&Number.isFinite(y)&&x>=0&&x<=500&&y>=0&&y<=500);
    for(const palette of Object.values(PALETTES)) assert.match(palette[m.color],/^#[0-9a-f]{6}$/);
  }
});
test('passes preserve earlier decisions and add detail deterministically',()=>{
  const a=selectedMarks(1),b=selectedMarks(2),c=selectedMarks(3);
  assert.ok(a.length<b.length&&b.length<c.length);
  assert.deepEqual(b.slice(0,a.length),a);
  assert.deepEqual(c.slice(0,b.length),b);
  assert.deepEqual(makeScene(),makeScene());
  assert.throws(()=>selectedMarks(4),RangeError);
});
test('perspective patch interpolates the four corners',()=>{
  const q=[[1,2],[12,4],[10,20],[0,18]];
  assert.deepEqual(patch(q,0,0,1,1),q);
  assert.deepEqual(pointOn(q,.5,.5),[5.75,11]);
});
test('URL options are bounded and cannot select inherited properties',()=>{
  assert.deepEqual(optionsFrom('?palette=__proto__&stage=Infinity&seed=-1'),{palette:'earth',stage:3,seed:29});
  assert.deepEqual(optionsFrom('?palette=dusk&stage=1&seed=123'),{palette:'dusk',stage:1,seed:123});
  assert.equal(optionsFrom('?seed=9999999999999999999').seed,29);
});
test('vendored brush engine is byte-pinned',async()=>{
  const bytes=await readFile(new URL('./vendor/brush.js',import.meta.url));
  const notice=await readFile(new URL('./vendor/PROVENANCE.txt',import.meta.url),'utf8');
  assert.ok(notice.includes(createHash('sha256').update(bytes).digest('hex')));
  assert.match(SOURCE.sha256,/^[a-f0-9]{64}$/);
});
test('preview server exposes only the explicit study assets',async()=>{
  const server=await startServer();
  try {
    const base=`http://127.0.0.1:${server.address().port}`;
    const response=await fetch(base);
    assert.equal(response.status,200);
    assert.ok(response.headers.get('content-security-policy').includes("connect-src 'none'"));
    for(const target of ['/directions.html','/directions.css','/hybrid.css','/directions.mjs','/treatments.mjs']) {
      assert.equal((await fetch(base+target)).status,200);
    }
    const batch=await fetch(base+'/batch.html');
    assert.equal(batch.status,200);
    assert.ok(batch.headers.get('content-security-policy').includes("connect-src 'self'"));
    for(const target of ['/scene-format.mjs','/batch-catalog.json','/scenes/ackermans.json']) assert.equal((await fetch(base+target)).status,200);
    for(const target of ['/README.md','/local/other.json','/vendor/LICENSE.txt','/%2e%2e/README.md','/scenes/unknown.json','/local/paint-brussels/batch/post.jpg']) {
      assert.equal((await fetch(base+target)).status,404);
    }
  } finally {await new Promise(resolve=>server.close(resolve));}
});
