import {createHash} from 'node:crypto';
import {validateStructure,validateOperator,validateKnobs} from './structure-contract.mjs';
export const structureHash=s=>createHash('sha256').update(JSON.stringify(validateStructure(s))).digest('hex');
export function identityProgram(scene){return `function paint(p){if(window.frozenSceneSha256!==${JSON.stringify(structureHash(scene))})throw Error('Wrong structure bytes');for(const c of window.frozenScene.commands)p[c.op](...c.args);}`;}
// Trusted implementation: local-model output is declarative data, never host-side JS.
function renderMaterial(p,scene,o,knobs){
 const clamp=v=>Math.max(0,Math.min(255,Math.round(v))),rgb=h=>[1,3,5].map(i=>parseInt(h.slice(i,i+2),16)),hex=c=>'#'+c.map(v=>clamp(v).toString(16).padStart(2,'0')).join('');
 const inks=o.inks.map(rgb),paper=rgb(o.paper),t=Math.min(1,o.texture*knobs.texture);let strokes=0;
 function colour(c,shift=0){if(!c||c[3]===0)return null;const encode=rgb=>c[3]<1?`rgba(${rgb.map(clamp).join(',')},${c[3]})`:hex(rgb);const out=c.slice(0,3).map((v,i)=>{const mapped=o.matrix[i*3]*c[0]+o.matrix[i*3+1]*c[1]+o.matrix[i*3+2]*c[2]+o.bias[i];return clamp(v+(mapped-v)*knobs.colour+shift);});if(o.levels){let best=inks[0],d=Infinity;for(const ink of inks.slice(0,o.levels)){const e=ink.reduce((n,v,i)=>n+(v-out[i])**2,0);if(e<d){d=e;best=ink;}}return encode(best);}return encode(out);}
 function shape(c,fill,stroke,width,alpha){const a=c.args;if(c.op==='poly')p.poly(a[0],fill,stroke,width,alpha);else if(c.op==='path')p.path(a[0],fill,stroke,width,alpha);else if(c.op==='ellipse')p.ellipse(a[0],a[1],a[2],a[3],fill,stroke,width,alpha);}
 function texture(c,base){
  const b=c.box.map((v,i)=>Math.max(0,Math.min(1000,v))),w=b[2]-b[0],h=b[3]-b[1];if(!base||w*h<1000||t<.01||strokes>=700)return;
  const count=Math.min(12,Math.max(1,Math.ceil(w*h/18000*t*5))),geometry=c.op==='path'?c.args[0]:c.op==='poly'?c.args[0]:null;if(!geometry)return;
  p.push();p.clip(geometry);
  for(let i=0;i<count&&strokes<700;i++,strokes++){
   const y=b[1]+p.rand()*h,x=b[0]+p.rand()*w,shade=colour(c.fill,p.rand(-30,30));
   if(o.medium==='collage'){const dx=p.rand(.15,.65)*w,dy=p.rand(.1,.6)*h;p.poly([[x,y],[x+dx,y+p.rand(-5,5)],[x+dx,y+dy],[x,y+dy]],shade,null,1,.18+t*.2);}
   else if(o.medium==='silkscreen'){p.line([[b[0],y],[b[2],y]],colour(c.fill,-24),p.rand(.3,1.2),.10);}
   else if(o.medium==='pastel'){p.brush([[x,y],[Math.min(b[2],x+p.rand(8,45)),y+p.rand(-10,10)]],shade,p.rand(3,12),.5);}
   else if(o.medium==='wash'){p.brush([[b[0]-10,y],[b[2]+10,y+p.rand(-15,15)]],shade,Math.min(85,h*.35),.12+t*.15);}
   else if(o.medium==='gouache'){p.brush([[b[0],y],[b[2],y+p.rand(-8,8)]],shade,Math.min(65,h*.22),.65);p.line([[b[0],y],[b[2],y]],colour(c.fill,25),1.2,.15);}
   else{p.brush([[b[0]-5,y],[b[2]+5,y+p.rand(-20,20)]],shade,Math.min(65,h*.3),.6);}
  }
  p.pop();
 }
 p.background(o.paper);
 for(let index=0;index<scene.commands.length;index++){
  const c=scene.commands[index],a=c.args;
  if(['push','pop','clip'].includes(c.op)){p[c.op](...a);continue;}
  if(['rand','grain','hatch'].includes(c.op))continue;
  const fill=colour(c.fill),stroke=colour(c.stroke),alpha=c.op==='ellipse'?a[7]:['poly','path'].includes(c.op)?a[4]:1;
  const opacity=o.medium==='wash'?.48:o.medium==='pastel'?.76:o.medium==='drybrush'?.55:1;
  if(c.op==='background'){p.background(fill??o.paper);continue;}
  if(['poly','path','ellipse'].includes(c.op)){
   const originalWidth=c.op==='ellipse'?a[6]:a[3],ink=o.outline>.01&&!(o.medium==='wash'&&index%3)?stroke:null;
   shape(c,fill,ink,originalWidth*o.outline,alpha*opacity);texture(c,fill);
  }else if(c.op==='line'){
   const strength=o.medium==='pastel'?.5:o.medium==='wash'?.45:o.medium==='drybrush'?.55:1;
   if(o.outline>.02)p.line(a[0],stroke,a[2]*Math.max(.2,o.outline),a[3]*strength);
  }else if(c.op==='brush')p.brush(a[0],stroke,a[2]*(o.medium==='pastel'?.6:1),a[3]*(o.medium==='wash'?.4:.8));
 }
 if(t>.01){p.grain(o.medium==='pastel'?o.paper:'#182b26',t*(o.medium==='pastel'?.14:.06),Math.floor(12000*t));}
}
export function operatorProgram(scene,operator,knobs){validateStructure(scene);validateOperator(operator);validateKnobs(knobs);return `function paint(p){if(window.frozenSceneSha256!==${JSON.stringify(structureHash(scene))})throw Error('Wrong structure bytes');const run=${renderMaterial.toString()};run(p,window.frozenScene,${JSON.stringify(operator)},${JSON.stringify(knobs)});}`;}
