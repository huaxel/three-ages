import test from 'node:test';
import assert from 'node:assert/strict';
import {TREATMENTS, randomFor, recipeFor, directionOptions, renderTreatment, hybridPlate} from './treatments.mjs';
import {makeScene} from './scene.mjs';

test('five named treatments cover the same scene colour roles',()=>{
  assert.deepEqual(TREATMENTS.map(t=>t.id),['graphic','opaque','drawing','print','hybrid']);
  for(const recipe of TREATMENTS) {
    assert.equal(recipeFor(recipe.id),recipe);
    for(const role of ['paper',...new Set(makeScene().map(m=>m.color))]) {
      assert.match(recipe.palette[role],/^#[0-9a-f]{6}$/);
    }
  }
  assert.throws(()=>recipeFor('__proto__'),RangeError);
});
test('seeded mark variation is replayable, bounded, and not constant',()=>{
  for(const seed of [0,29,999999]) {
    const a=randomFor(seed),b=randomFor(seed);
    const values=Array.from({length:100},()=>a());
    assert.deepEqual(values,Array.from({length:100},()=>b()));
    assert.ok(values.every(v=>v>=0&&v<1));
    assert.ok(new Set(values).size>95);
  }
  assert.notDeepEqual(Array.from({length:10},randomFor(29)),Array.from({length:10},randomFor(30)));
  for(const seed of [-1,1.5,Infinity,1000000]) assert.throws(()=>randomFor(seed),RangeError);
});
test('direction URL options accept only bounded integer seeds',()=>{
  assert.deepEqual(directionOptions(),{seed:29});
  assert.deepEqual(directionOptions('?seed=0'),{seed:0});
  for(const v of ['NaN','Infinity','-1','1.2','1000000']) assert.deepEqual(directionOptions(`?seed=${v}`),{seed:29});
});
test('restrained hybrid leaves sky and neighbors unprinted and preserves geometry',()=>{
  const marks=makeScene(),before=JSON.stringify(marks);
  for(const mark of marks) {
    const plate=hybridPlate(mark,'restrained');
    if(mark.kind==='line'||mark.name.includes('neighbour')||mark.name==='right streetscape'||['sky','warm light','sky movement','right brick plane'].includes(mark.name)) assert.equal(plate,null);
    if(plate) {
      assert.ok(plate.opacity>0&&plate.opacity<=1);
      assert.ok(Object.hasOwn(recipeFor('hybrid').palette,plate.color));
    }
  }
  assert.equal(JSON.stringify(marks),before);
  const find=name=>marks.find(m=>m.name===name);
  assert.equal(hybridPlate(find('left brick plane'),'restrained').texture,true);
  assert.deepEqual(hybridPlate(find('central cream pilaster'),'restrained'),{color:'paper',opacity:1,texture:false});
  assert.ok(hybridPlate(find('corner window 3.1'),'restrained').opacity>hybridPlate(find('corner window 2.1'),'restrained').opacity);
});
test('full hybrid uses saturated sky, warm faces and cool shadows without moving geometry',()=>{
  const marks=makeScene(),before=JSON.stringify(marks);
  const find=name=>marks.find(m=>m.name===name);
  assert.deepEqual(hybridPlate(find('sky')),{color:'sky',opacity:1,texture:true});
  assert.equal(hybridPlate(find('rounded corner brick plane')).color,'brick');
  assert.equal(hybridPlate(find('right brick plane')).color,'shade');
  assert.equal(hybridPlate(find('right sill band 1')).color,'plaster');
  for(const mark of marks) {
    const plate=hybridPlate(mark);
    if(mark.kind==='line') assert.equal(plate,null);
    if(plate) {
      assert.ok(plate.opacity>0&&plate.opacity<=1);
      assert.ok(Object.hasOwn(recipeFor('hybrid').palette,plate.color));
    }
  }
  assert.equal(JSON.stringify(marks),before);
  assert.throws(()=>hybridPlate(find('sky'),'invalid'),RangeError);
});
test('invalid rendering requests fail before touching the canvas',()=>{
  const canvas={getContext(){throw new Error('should not touch canvas');}};
  assert.throws(()=>renderTreatment(canvas,'bad'),RangeError);
  assert.throws(()=>renderTreatment(canvas,'graphic',{seed:-1}),RangeError);
  assert.throws(()=>renderTreatment(canvas,'hybrid',{colour:'invalid'}),RangeError);
});
