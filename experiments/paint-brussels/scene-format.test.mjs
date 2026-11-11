import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {parseSceneJSON,validateScene,compileScene,parseCatalog,MAX_SCENE_BYTES,MAX_MARKS} from './scene-format.mjs';
import {hybridPlate,randomFor} from './treatments.mjs';
import {sheetLayout} from './sheet-layout.mjs';

const catalog=parseCatalog(await readFile(new URL('./batch-catalog.json',import.meta.url),'utf8'));
function fixture() {
  return {version:1,id:'test',source:'test',title:'Fixture',method:'agent-visual-interpretation',omissions:[],view:[0,0,500,500],elements:[
    {type:'facade',id:'front',role:'wall-warm',quad:[[50,50],[450,50],[450,450],[50,450]],rows:[[.1,.3],[.5,.7]],bays:[[.1,.3],[.5,.8]],band:.04,mullions:1}
  ]};
}
test('all three approved scenes compile to bounded, named marks without mutating their source',async()=>{
  assert.equal(catalog.items.length,3);
  for(const item of catalog.items) {
    const scene=parseSceneJSON(await readFile(new URL(`./scenes/${item.scene}`,import.meta.url),'utf8'));
    assert.equal(scene.id,item.id);assert.equal(scene.source,item.id);
    const before=JSON.stringify(scene),marks=compileScene(scene);
    assert.ok(marks.length>10&&marks.length<=MAX_MARKS);
    assert.equal(new Set(marks.map(m=>m.name)).size,marks.length);
    for(const mark of marks) {
      for(const p of mark.points) for(const coordinate of p) assert.ok(Number.isFinite(coordinate)&&coordinate>=0&&coordinate<=500);
      if(mark.kind==='wash') assert.ok(hybridPlate(mark));
    }
    marks[0].points[0][0]=499;
    assert.equal(JSON.stringify(scene),before);
  }
});
test('100 generated facade grids conserve opening counts and stay inside their facade bounds',()=>{
  const rng=randomFor(491);
  for(let trial=0;trial<100;trial++) {
    const scene=fixture(),e=scene.elements[0];
    const x=5+rng()*90,y=5+rng()*90,w=40+rng()*(450-x),h=40+rng()*(450-y),tilt=rng()*8;
    const rows=1+Math.floor(rng()*5),bays=1+Math.floor(rng()*6),mullions=Math.floor(rng()*3);
    e.quad=[[x,y],[x+w,y+tilt],[x+w-tilt,y+h],[x+tilt,y+h-tilt]];
    e.rows=Array.from({length:rows},(_,i)=>[(i+.15)/rows,(i+.65)/rows]);
    e.bays=Array.from({length:bays},(_,i)=>[(i+.1)/bays,(i+.85)/bays]);
    e.band=.08/rows;e.mullions=mullions;
    const before=JSON.stringify(scene),marks=compileScene(parseSceneJSON(before));
    assert.equal(marks.filter(m=>m.paintRole==='glass').length,rows*bays,`trial ${trial}`);
    assert.equal(marks.filter(m=>m.kind==='line').length,rows*bays*mullions);
    for(const mark of marks.filter(m=>m.paintRole==='glass')) {
      for(const [px,py] of mark.points) assert.ok(px>=x&&px<=x+w&&py>=y&&py<=y+h);
      const area=mark.points.reduce((a,p,i)=>{const q=mark.points[(i+1)%4];return a+p[0]*q[1]-q[0]*p[1];},0);
      assert.ok(area>0);
    }
    assert.equal(JSON.stringify(scene),before);
  }
});
test('malformed, executable-looking and out-of-domain scenes fail closed',()=>{
  for(const mutate of [
    s=>{s.id=null;},s=>{s.source=42;},s=>{s.elements[0].id='sky';},
    s=>{s.code='fetch(secret)';},s=>{s.elements[0].type='javascript';},
    s=>{s.elements[0].quad[0][0]=501;},s=>{s.elements[0].quad[0][0]=NaN;},
    s=>{s.elements[0].quad=[[10,10],[100,100],[10,100],[100,10]];},
    s=>{s.elements[0].quad=[[10,10],[100,10],[30,30],[10,100]];},
    s=>{s.elements.push(structuredClone(s.elements[0]));},
    s=>{s.elements[0].rows=[[.5,.8],[.2,.4]];},
    s=>{s.elements[0].band=.12;s.elements[0].rows=[[.1,.5],[.55,.8]];},
  ]) {const scene=fixture();mutate(scene);assert.throws(()=>validateScene(scene),TypeError);}
  assert.throws(()=>parseSceneJSON(' '.repeat(MAX_SCENE_BYTES+1)),/byte limit/);
  assert.throws(()=>parseSceneJSON('🧱'.repeat(9000)),/byte limit/);
  assert.throws(()=>parseSceneJSON('{"version":NaN}'),SyntaxError);
});
test('compilation refuses a valid but excessive grid before painting',()=>{
  const scene=fixture(),e=scene.elements[0];
  e.rows=e.bays=Array.from({length:20},(_,i)=>[i/20,(i+.5)/20]);e.mullions=2;e.band=0;
  validateScene(scene);
  assert.throws(()=>compileScene(scene),/mark budget/);
});
test('catalog rejects path traversal, source reassignment and unknown fields',()=>{
  for(const mutate of [
    c=>{c.items[0].id=null;},c=>{c.items[0].file='../source.jpg';},
    c=>{c.items[0].scene='../scene.json';},c=>{c.items[0].image='https://evil.example/picture.jpg';},
    c=>{c.items[0].image='https://64.media.tumblr.com.evil.example/picture.jpg';},
    c=>{c.items[0].image='https://user:password@64.media.tumblr.com/photo.jpg';},
    c=>{c.items[0].post='http://buildingsofbrussels.tumblr.com/post/1';},
    c=>{c.items.push(structuredClone(c.items[0]));},c=>{c.items[0].script='run';},
  ]) {const next=structuredClone(catalog);mutate(next);assert.throws(()=>parseCatalog(JSON.stringify(next)),TypeError);}
});
test('all allowed collection sizes fit every tile and label above the footer',()=>{
  for(let count=1;count<=24;count++) {
    const layout=sheetLayout(count);assert.equal(layout.tiles.length,count);
    for(const [i,tile] of layout.tiles.entries()) {
      assert.ok(tile.x>=60&&tile.x+tile.size<=layout.width-60);
      assert.ok(tile.y>=155&&tile.y+735<layout.height-50);
      for(const other of layout.tiles.slice(i+1)) assert.ok(tile.x+tile.size<other.x||other.x+other.size<tile.x||tile.y+tile.size<other.y||other.y+other.size<tile.y);
    }
  }
  for(const count of [0,25,1.5,Infinity]) assert.throws(()=>sheetLayout(count),RangeError);
});
