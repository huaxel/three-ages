import {patch, pointOn} from './scene.mjs';

export const MAX_SCENE_BYTES=32768;
export const MAX_MARKS=1200;
export const PAINT_ROLES=Object.freeze(['wall-warm','wall-cool','wall-light','stone','glass','context','dark','ochre','paper']);
const ID=/^[a-z][a-z0-9-]{0,39}$/;
const validID=value=>typeof value==='string'&&ID.test(value);
function fail(message) {throw new TypeError(message);}
function object(value,label) {
  if(!value||typeof value!=='object'||Array.isArray(value)) fail(`${label}: expected object`);
}
function keys(value,allowed,required,label) {
  object(value,label);
  for(const key of Object.keys(value)) if(!allowed.includes(key)) fail(`${label}: unknown field ${key}`);
  for(const key of required) if(!Object.hasOwn(value,key)) fail(`${label}: missing ${key}`);
}
function text(value,label,max=160) {
  if(typeof value!=='string'||!value.trim()||value.length>max) fail(`${label}: invalid text`);
}
function number(value,min,max,label) {
  if(!Number.isFinite(value)||value<min||value>max) fail(`${label}: number outside ${min}..${max}`);
}
function point(p,label) {
  if(!Array.isArray(p)||p.length!==2) fail(`${label}: expected [x,y]`);
  p.forEach(n=>number(n,0,500,label));
}
const cross=(a,b,c)=>(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
function on(a,b,p) {
  return Math.abs(cross(a,b,p))<1e-8&&p[0]>=Math.min(a[0],b[0])-1e-8&&p[0]<=Math.max(a[0],b[0])+1e-8&&p[1]>=Math.min(a[1],b[1])-1e-8&&p[1]<=Math.max(a[1],b[1])+1e-8;
}
function intersects(a,b,c,d) {
  const x=cross(a,b,c),y=cross(a,b,d),u=cross(c,d,a),v=cross(c,d,b);
  return (x*y<0&&u*v<0)||on(a,b,c)||on(a,b,d)||on(c,d,a)||on(c,d,b);
}
function polygon(points,label,{quad=false}={}) {
  if(!Array.isArray(points)||points.length<(quad?4:3)||points.length>(quad?4:64)) fail(`${label}: invalid vertex count`);
  points.forEach(p=>point(p,label));
  let area=0;
  for(let i=0;i<points.length;i++) {
    const a=points[i],b=points[(i+1)%points.length];
    if(Math.hypot(b[0]-a[0],b[1]-a[1])<1e-6) fail(`${label}: repeated adjacent vertex`);
    area+=a[0]*b[1]-b[0]*a[1];
    for(let j=i+1;j<points.length;j++) {
      if(j===i+1||(i===0&&j===points.length-1)) continue;
      if(intersects(a,b,points[j],points[(j+1)%points.length])) fail(`${label}: self-intersecting polygon`);
    }
  }
  if(Math.abs(area)<1e-4) fail(`${label}: degenerate polygon`);
  if(quad) {
    const turns=points.map((a,i)=>cross(a,points[(i+1)%4],points[(i+2)%4]));
    if(!turns.every(n=>n>1e-8)&&!turns.every(n=>n< -1e-8)) fail(`${label}: facade must be a convex quad`);
  }
}
function intervals(values,label) {
  if(!Array.isArray(values)||values.length<1||values.length>20) fail(`${label}: expected 1..20 intervals`);
  let previous=-1;
  for(const pair of values) {
    if(!Array.isArray(pair)||pair.length!==2) fail(`${label}: invalid interval`);
    pair.forEach(n=>number(n,0,1,label));
    if(pair[0]>=pair[1]||pair[0]<previous) fail(`${label}: intervals must be ordered and non-overlapping`);
    previous=pair[1];
  }
}
export function parseSceneJSON(value) {
  if(typeof value!=='string'||new TextEncoder().encode(value).length>MAX_SCENE_BYTES) fail('Scene exceeds byte limit');
  const scene=JSON.parse(value);validateScene(scene);return scene;
}
export function validateScene(scene) {
  keys(scene,['version','id','title','source','method','omissions','detailNotes','details','view','elements'],['version','id','title','source','method','omissions','view','elements'],'scene');
  if(scene.version!==1) fail('Unsupported scene version');
  if(!validID(scene.id)||!validID(scene.source)) fail('Invalid scene/source ID');
  text(scene.title,'title');
  if(scene.method!=='agent-visual-interpretation') fail('Unrecognized interpretation method');
  if(!Array.isArray(scene.omissions)||scene.omissions.length>8) fail('Expected up to eight omission notes');
  scene.omissions.forEach(note=>text(note,'omission',400));
  if(scene.detailNotes!==undefined) {
    if(!Array.isArray(scene.detailNotes)||scene.detailNotes.length>8) fail('Expected up to eight detail notes');
    scene.detailNotes.forEach(note=>text(note,'detail note',400));
  }
  if(!Array.isArray(scene.view)||scene.view.length!==4) fail('view: expected [x0,y0,x1,y1]');
  scene.view.forEach(n=>number(n,0,500,'view'));
  if(scene.view[0]>=scene.view[2]||scene.view[1]>=scene.view[3]) fail('Invalid view rectangle');
  if(!Array.isArray(scene.elements)||scene.elements.length<1||scene.elements.length>80) fail('Expected 1..80 scene elements');
  const groups=scene.details??[];
  if(!Array.isArray(groups)||groups.length>40) fail('Invalid detail groups');
  const baseIds=new Set(scene.elements.map(e=>e?.id)),anchors=new Set();
  for(const group of groups) {
    keys(group,['after','elements'],['after','elements'],'detail group');
    if(!validID(group.after)||!baseIds.has(group.after)||anchors.has(group.after)) fail('Detail anchors must be unique existing elements');
    anchors.add(group.after);
    if(!Array.isArray(group.elements)||!group.elements.length) fail('Empty detail group');
  }
  const elements=[...scene.elements,...groups.flatMap(group=>group.elements)];
  if(elements.length>80) fail('Base and detail elements exceed the 80-element budget');
  const ids=new Set(['sky']);
  for(const e of elements) {
    object(e,'element');
    if(!validID(e.id)||ids.has(e.id)) fail('Element IDs must be valid and unique');
    ids.add(e.id);
    if(e.type==='polygon') {
      keys(e,['type','id','role','points'],['type','id','role','points'],e.id);
      if(!PAINT_ROLES.includes(e.role)) fail(`${e.id}: invalid paint role`);
      polygon(e.points,e.id);
    } else if(e.type==='facade') {
      keys(e,['type','id','role','quad','rows','bays','band','mullions','detail'],['type','id','role','quad','rows','bays'],e.id);
      if(!['wall-warm','wall-cool','wall-light','ochre'].includes(e.role)) fail(`${e.id}: invalid wall role`);
      polygon(e.quad,e.id,{quad:true});intervals(e.rows,`${e.id} rows`);intervals(e.bays,`${e.id} bays`);
      number(e.band??0,0,.12,`${e.id} band`);
      if(![0,1,2].includes(e.mullions??0)) fail(`${e.id}: invalid mullion count`);
      if(e.detail!==undefined) {
        const d=e.detail;
        keys(d,['frame','mullions','transoms','arch','archedRows'],['frame','mullions','transoms'],`${e.id} detail`);
        number(d.frame,0,.15,'frame width');
        if(![0,1,2,3,4].includes(d.mullions)) fail('Invalid detailed mullion count');
        if(!Array.isArray(d.transoms)||d.transoms.length>4) fail('Expected up to four transoms');
        let previous=0;
        for(const value of d.transoms) {number(value,.05,.95,'transom');if(value<=previous) fail('Transoms must be ordered');previous=value;}
        number(d.arch??0,0,.45,'arch rise');
        if(d.archedRows!==undefined&&(!Array.isArray(d.archedRows)||new Set(d.archedRows).size!==d.archedRows.length||d.archedRows.some(row=>!Number.isInteger(row)||row<0||row>=e.rows.length))) fail('Invalid arched rows');
      }
      for(let i=0;i<e.rows.length;i++) {
        const bandEnd=e.rows[i][1]+(e.band??0);
        if(bandEnd>1+1e-9||i+1<e.rows.length&&bandEnd>e.rows[i+1][0]+1e-9) fail(`${e.id}: sill band overlaps next row or leaves facade`);
      }
    } else if(e.type==='line') {
      keys(e,['type','id','role','points','width'],['type','id','role','points'],e.id);
      if(!['outline','light','context'].includes(e.role)) fail(`${e.id}: invalid line role`);
      if(!Array.isArray(e.points)||e.points.length<2||e.points.length>64) fail(`${e.id}: invalid line`);
      e.points.forEach(p=>point(p,e.id));number(e.width??.6,.2,3,`${e.id} width`);
    } else fail(`${e.id}: unsupported primitive`);
  }
  return scene;
}
function archCurve(rise) {
  return Array.from({length:13},(_,i)=>{const angle=Math.PI-i*Math.PI/12;return [.5+.5*Math.cos(angle),rise*(1-Math.sin(angle))];});
}
function archTop(u,rise) {
  if(!rise) return 0;
  const arc=archCurve(rise);
  for(let i=1;i<arc.length;i++) if(u<=arc[i][0]) {
    const a=arc[i-1],b=arc[i];return a[1]+(b[1]-a[1])*(u-a[0])/(b[0]-a[0]);
  }
  return rise;
}
function archSpan(v,rise) {
  if(!rise||v>=rise) return [0,1];
  const arc=archCurve(rise),cuts=[];
  for(let i=1;i<arc.length;i++) {
    const a=arc[i-1],b=arc[i];
    if(v>=Math.min(a[1],b[1])&&v<=Math.max(a[1],b[1])&&a[1]!==b[1]) cuts.push(a[0]+(b[0]-a[0])*(v-a[1])/(b[1]-a[1]));
  }
  return [Math.min(...cuts),Math.max(...cuts)];
}
export function openingPoints(quad,rise=0) {
  polygon(quad,'opening',{quad:true});number(rise,0,.45,'arch rise');
  if(!rise) return quad.map(p=>[...p]);
  return [[0,1],...archCurve(rise),[1,1]].map(([u,v])=>pointOn(quad,u,v));
}
export function compileScene(scene,{detail='simple'}={}) {
  if(!['simple','rich'].includes(detail)) fail('Unknown detail pass');
  validateScene(scene);
  const marks=[];
  const add=mark=>{if(marks.length>=MAX_MARKS) fail('Compiled scene exceeds mark budget');marks.push({...mark,sceneMark:true});};
  const wash=(id,points,paintRole,occludes=false)=>add({kind:'wash',name:`${paintRole==='context'?'neighbour ':''}${id}`,points:points.map(p=>[...p]),paintRole,occludes});
  const line=(id,points,role='outline',weight=.6)=>add({kind:'line',name:`${role==='context'?'neighbour ':''}${id}`,points:points.map(p=>[...p]),color:role==='light'?'light':'ink',weight});
  const [x0,y0,x1,y1]=scene.view;
  wash('sky',[[x0,y0],[x1,y0],[x1,y1],[x0,y1]],'sky');
  const elements=scene.elements.flatMap(e=>[e,...(detail==='rich'?(scene.details??[]).find(group=>group.after===e.id)?.elements??[]:[])]);
  for(const e of elements) {
    if(e.type==='polygon') wash(e.id,e.points,e.role,true);
    if(e.type==='line') line(e.id,e.points,e.role,e.width??.6);
    if(e.type==='facade') {
      wash(e.id,e.quad,e.role,true);
      for(const [r,[v0,v1]] of e.rows.entries()) {
        if(e.band) wash(`${e.id} sill band ${r}`,patch(e.quad,0,v1,1,v1+e.band),'stone');
        for(const [b,[u0,u1]] of e.bays.entries()) {
          const d=detail==='rich'?e.detail:null;
          const arch=d&&(d.archedRows===undefined||d.archedRows.includes(r))?(d.arch??0):0;
          const opening=patch(e.quad,u0,v0,u1,v1);
          if(d?.frame) {
            const fu=(u1-u0)*d.frame,fv=(v1-v0)*d.frame;
            const outer=patch(e.quad,Math.max(0,u0-fu),Math.max(0,v0-fv),Math.min(1,u1+fu),Math.min(1,v1+fv));
            wash(`${e.id} frame ${r}.${b}`,openingPoints(outer,arch),'stone');
          }
          wash(`${e.id} window ${r}.${b}`,openingPoints(opening,arch),'glass');
          const mullions=d?d.mullions:(e.mullions??0);
          for(let n=1;n<=mullions;n++) {
            const u=n/(mullions+1),top=archTop(u,arch);
            const points=d?[pointOn(opening,u,top),pointOn(opening,u,1)]:[pointOn(e.quad,u0+(u1-u0)*n/(mullions+1),v0),pointOn(e.quad,u0+(u1-u0)*n/(mullions+1),v1)];
            line(`${e.id} mullion ${r}.${b}.${n}`,points,'light',d ? .45 : .65);
          }
          for(const [n,v] of (d?.transoms??[]).entries()) {
            const [start,end]=archSpan(v,arch);
            line(`${e.id} transom ${r}.${b}.${n}`,[pointOn(opening,start,v),pointOn(opening,end,v)],'light',.5);
          }
        }
      }
    }
  }
  return marks;
}

export function parseCatalog(value) {
  if(typeof value!=='string'||new TextEncoder().encode(value).length>32768) fail('Catalog exceeds byte limit');
  const catalog=JSON.parse(value);
  keys(catalog,['version','items'],['version','items'],'catalog');
  if(catalog.version!==1||!Array.isArray(catalog.items)||catalog.items.length<1||catalog.items.length>24) fail('Invalid pilot catalog');
  const ids=new Set(),files=new Set();
  for(const item of catalog.items) {
    keys(item,['id','title','place','post','image','sha256','file','scene'],['id','title','place','post','image','sha256','file','scene'],'catalog item');
    if(!validID(item.id)||ids.has(item.id)) fail('Invalid or duplicate catalog ID');ids.add(item.id);
    text(item.title,'catalog title');text(item.place,'place');
    if(typeof item.file!=='string'||!/^\d{9,16}\.jpg$/.test(item.file)||files.has(item.file)) fail('Invalid or duplicate source filename');files.add(item.file);
    if(item.scene!==`${item.id}.json`||typeof item.sha256!=='string'||!/^[a-f0-9]{64}$/.test(item.sha256)) fail('Invalid scene path or source hash');
    for(const [field,host] of [['post','buildingsofbrussels.tumblr.com'],['image','64.media.tumblr.com']]) {
      let url;try{url=new URL(item[field]);}catch{fail(`Invalid ${field} URL`);}
      if(url.protocol!=='https:'||url.hostname!==host||url.username||url.password||url.port) fail(`Unapproved ${field} URL`);
    }
  }
  return catalog;
}
