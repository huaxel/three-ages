import {HASH,ID} from './contract.mjs';
export const OPS=['background','poly','path','line','ellipse','brush','hatch','grain','rand','push','pop','clip'];
export const MEDIA=['silkscreen','gouache','pastel','drybrush','wash','collage'];
const finite=a=>a.every(Number.isFinite),colour=c=>c===null||Array.isArray(c)&&c.length===4&&finite(c)&&c.slice(0,3).every(x=>x>=0&&x<=255)&&c[3]>=0&&c[3]<=1;
export function validateStructure(s){
 if(!s||Object.keys(s).some(k=>!['version','width','height','sourceSha256','sourceProgramSha256','palette','commands'].includes(k))||s.version!==1||s.width!==1000||s.height!==1000||!Array.isArray(s.commands)||s.commands.length<5||s.commands.length>30000||!HASH.test(s.sourceSha256)||!HASH.test(s.sourceProgramSha256)||!Array.isArray(s.palette)||s.palette.length<1||s.palette.length>24||!s.palette.every(c=>c!==null&&colour(c)))throw Error('Invalid frozen structure');
 if(new TextEncoder().encode(JSON.stringify(s)).length>4*1024*1024)throw Error('Structure exceeds budget');
 let depth=0;
 for(const c of s.commands){if(!c||Object.keys(c).some(k=>!['op','args','box','fill','stroke'].includes(k))||!OPS.includes(c.op)||!Array.isArray(c.args)||!Array.isArray(c.box)||c.box.length!==4||!finite(c.box)||!colour(c.fill)||!colour(c.stroke))throw Error('Invalid structural mark');
  const nums=[];function check(v,d=0){if(d>4)throw Error('Nested structural argument');if(typeof v==='number')nums.push(v);else if(typeof v==='string'){if(v.length>16000)throw Error('Structural string exceeds budget');}else if(Array.isArray(v)){if(v.length>2048)throw Error('Structural array exceeds budget');v.forEach(x=>check(x,d+1));}else if(v!==null)throw Error('Invalid structural argument');}check(c.args);if(!finite(nums))throw Error('Non-finite structural argument');
  const arity={background:1,poly:5,path:5,line:4,ellipse:8,brush:4,hatch:6,grain:3,rand:2,push:0,pop:0,clip:1};if(c.args.length!==arity[c.op]||c.box[0]>c.box[2]||c.box[1]>c.box[3])throw Error('Invalid structural signature');
  const ps=v=>Array.isArray(v)&&v.length>=2&&v.length<=2048&&v.every(p=>Array.isArray(p)&&p.length===2&&finite(p)),css=v=>v===null||typeof v==='string'&&v.length<=200,path=v=>typeof v==='string'&&v.length<=16000,a=c.args;
  let good=true;if(['poly','line','brush','hatch'].includes(c.op))good=ps(a[0]);if(c.op==='path')good=path(a[0]);if(c.op==='clip')good=path(a[0])||ps(a[0]);
  if(['poly','path'].includes(c.op))good=good&&css(a[1])&&css(a[2])&&finite(a.slice(3));else if(c.op==='ellipse')good=finite(a.slice(0,4))&&a[2]>=0&&a[3]>=0&&css(a[4])&&css(a[5])&&finite(a.slice(6));else if(['line','brush','hatch'].includes(c.op))good=good&&css(a[1])&&finite(a.slice(2))&&(c.op!=='hatch'||a[2]>=2);else if(c.op==='grain')good=css(a[0])&&finite(a.slice(1))&&a[2]>=0&&a[2]<=20000;else if(c.op==='background')good=css(a[0]);else if(c.op==='rand')good=finite(a);
  if(!good)throw Error('Invalid structural arguments');
  if(c.op==='push'&&++depth>64)throw Error('Excessive clip stack');if(c.op==='pop'&&--depth<0)throw Error('Unbalanced clip stack');
 }if(depth!==0)throw Error('Unbalanced clip stack');return s;
}
export function validateOperator(o){
 const keys=['version','id','title','intent','medium','matrix','bias','levels','outline','texture','paper','inks'];
 if(!o||Object.keys(o).some(k=>!keys.includes(k))||o.version!==1||!ID.test(o.id)||typeof o.title!=='string'||o.title.length>120||!o.title.trim()||!MEDIA.includes(o.medium))throw Error('Invalid painting operator');
 if(typeof o.intent!=='string'||o.intent.length>500)throw Error(`Operator intent must be <=500 characters (received ${o.intent?.length??'non-text'}); use one short sentence`);
 if(!Array.isArray(o.inks)||o.inks.length<2||o.inks.length>8||o.inks.some(c=>!/^#[a-fA-F0-9]{6}$/.test(c)))throw Error('Invalid ink palette');
 if(!Array.isArray(o.matrix)||o.matrix.length!==9||!finite(o.matrix)||o.matrix.some(x=>Math.abs(x)>2)||!Array.isArray(o.bias)||o.bias.length!==3||!finite(o.bias)||o.bias.some(x=>Math.abs(x)>100))throw Error('Invalid colour transform');
 if(!Number.isInteger(o.levels)||o.levels!==0&&(o.levels<2||o.levels>o.inks.length)||!Number.isFinite(o.outline)||o.outline<0||o.outline>2||!Number.isFinite(o.texture)||o.texture<0||o.texture>1||!/^#[a-fA-F0-9]{6}$/.test(o.paper))throw Error('Invalid material controls');return o;
}
export function validateKnobs(k){if(!k||Object.keys(k).some(x=>!['colour','texture'].includes(x))||!Number.isFinite(k.colour)||k.colour<.25||k.colour>1.5||!Number.isFinite(k.texture)||k.texture<.25||k.texture>1.5)throw Error('Invalid operator knobs');return k;}
