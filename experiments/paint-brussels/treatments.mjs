import {selectedMarks} from './scene.mjs';
import {compileScene} from './scene-format.mjs';

// These are authored rendering experiments, not learned styles or paint physics.
export const TREATMENTS = Object.freeze([
  {id:'graphic', number:'01', title:'The graphic city', subtitle:'Silhouette · flat colour · restraint',
    description:'Hard-edged colour planes. No paper grain, bleed or brush texture. The building reads as a sign, not a simulated painting.',
    palette:{paper:'#f5e9ce',sky:'#9fbfc0',cloud:'#9fbfc0',brick:'#bc523a',shade:'#803b35',plaster:'#f5dfac',glass:'#223d49',light:'#fff0c9',ink:'#233b43',context:'#769a9d'}},
  {id:'opaque', number:'02', title:'Built in paint', subtitle:'Opaque marks · broken edges · colour temperature',
    description:'Short, directional brush marks build up solid planes. Warm brick against cool shadow; details emerge from paint rather than an ink outline.',
    palette:{paper:'#e9dcc4',sky:'#99adb9',cloud:'#d8b8a4',brick:'#b36c4f',shade:'#786e89',plaster:'#dcccac',glass:'#536d7e',light:'#f6e5c1',ink:'#6c5c59',context:'#8f9296'}},
  {id:'drawing', number:'03', title:'Measured light', subtitle:'Line · negative space · selective colour',
    description:'The windows and cornices carry the image. Most of the sky and neighboring street disappear; a few coloured planes anchor the drawing.',
    palette:{paper:'#f5f1e7',sky:'#d1d3cd',cloud:'#ece3d2',brick:'#c28568',shade:'#777e7c',plaster:'#ece1c9',glass:'#718790',light:'#f8f3e8',ink:'#3d514f',context:'#b4aaa0'}},
  {id:'print', number:'04', title:'City in fragments', subtitle:'Cut shapes · overprint · registration slips',
    description:'An invented print/collage language: cut paper, a small ink palette, offset impressions and halftone. Texture comes from the printing system, not a watercolor filter.',
    palette:{paper:'#e9dfbd',sky:'#d0ab56',cloud:'#e2c674',brick:'#b55441',shade:'#294d5a',plaster:'#eddbad',glass:'#21434c',light:'#f5e7c6',ink:'#23434c',context:'#768876'}},
  {id:'hybrid', number:'05', title:'An architectural print', subtitle:'03 × 04 · precise line, imperfect ink',
    description:'An ochre sky, vermilion brick and blue-green shadow bathe the whole image in colour. Cream bands catch the light; precise architectural lines sit over rough, slightly misregistered ink. The neighboring street recedes in cooler colour rather than disappearing into blank paper.',
    palette:{paper:'#f3e5bb',sky:'#d4a347',cloud:'#efc878',brick:'#bc583e',shade:'#34636b',plaster:'#eed9a8',glass:'#294e59',light:'#fae9bb',ink:'#284750',context:'#6c8781'}},
]);

// Retain the first, quieter hybrid as an active before/after comparison.
const RESTRAINED_PALETTE=Object.freeze({paper:'#f4efdf',sky:'#c6a254',cloud:'#e5d6b4',brick:'#af624c',shade:'#3b6068',plaster:'#ede1c5',glass:'#345460',light:'#f4efdf',ink:'#304b52',context:'#b1a58e'});
const HYBRID_COLOURS=['full','restrained'];

export function randomFor(seed) {
  if(!Number.isSafeInteger(seed)||seed<0||seed>999999) throw new RangeError('seed must be an integer from 0 to 999999');
  let n=seed>>>0;
  return ()=>{n=(n+0x6D2B79F5)|0;let t=Math.imul(n^(n>>>15),1|n);t^=t+Math.imul(t^(t>>>7),61|t);return ((t^(t>>>14))>>>0)/4294967296;};
}
export function directionOptions(search='') {
  const value=Number(new URLSearchParams(search).get('seed')??29);
  return {seed:Number.isSafeInteger(value)&&value>=0&&value<=999999?value:29};
}
export function recipeFor(id) {
  const recipe=TREATMENTS.find(t=>t.id===id);
  if(!recipe) throw new RangeError(`Unknown treatment: ${id}`);
  return recipe;
}
function path(ctx,points,close=true) {
  ctx.beginPath();ctx.moveTo(...points[0]);
  for(const p of points.slice(1)) ctx.lineTo(...p);
  if(close) ctx.closePath();
}
function fill(ctx,points,color,alpha=1) {
  ctx.globalAlpha=alpha;ctx.fillStyle=color;path(ctx,points);ctx.fill();ctx.globalAlpha=1;
}
function outline(ctx,points,color,width=1,close=true) {
  ctx.strokeStyle=color;ctx.lineWidth=width;path(ctx,points,close);ctx.stroke();
}
function bounds(points) {
  const xs=points.map(p=>p[0]),ys=points.map(p=>p[1]);
  return [Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)];
}
function grain(ctx,rng,count,dark,alpha=.1) {
  ctx.fillStyle=dark;
  for(let i=0;i<count;i++) {
    ctx.globalAlpha=rng()*alpha;
    const size=.15+rng()*.65;
    ctx.fillRect(rng()*500,rng()*500,size,size*(.5+rng()));
  }
  ctx.globalAlpha=1;
}
function hatch(ctx,points,color,spacing=4,alpha=.2) {
  ctx.save();path(ctx,points);ctx.clip();
  const [x0,y0,x1,y1]=bounds(points);
  ctx.globalAlpha=alpha;
  for(let x=x0-(y1-y0);x<x1;x+=spacing) outline(ctx,[[x,y1],[x+y1-y0,y0]],color,.5,false);
  ctx.restore();
}
function clipped(ctx,points,draw) {
  ctx.save();path(ctx,points);ctx.clip();draw();ctx.restore();
}
function graphic(ctx,marks,p) {
  for(const m of marks) {
    if(m.kind==='line') {
      if(m.name.includes('neighbour')||m.name.includes('sill shadow')||m.name==='corner shoulder') continue;
      outline(ctx,m.points,p[m.color],m.name.includes('mullion')?1.1:.65,false);
      continue;
    }
    if(['warm light','sky movement','left plane cool shadow'].includes(m.name)) continue;
    fill(ctx,m.points,p[m.color]);
  }
}
function opaque(ctx,marks,p,rng) {
  for(const m of marks) {
    if(m.name==='warm light'||m.name==='sky movement') continue;
    if(m.kind==='line') {
      if(m.name.includes('neighbour')||m.name.includes('sill shadow')) continue;
      ctx.globalAlpha=.7;
      outline(ctx,m.points,p[m.color],m.name.includes('mullion')?1.1:.85,false);
      ctx.globalAlpha=1;
      continue;
    }
    const isSky=m.name==='sky';
    const alpha=m.name.includes('shadow') ? .52 : 1;
    fill(ctx,m.points,p[m.color],alpha);
    clipped(ctx,m.points,()=>{
      const [x0,y0,x1,y1]=bounds(m.points);
      const area=(x1-x0)*(y1-y0);
      const count=Math.min(isSky?450:1300,Math.max(12,Math.floor(area/55)));
      for(let i=0;i<count;i++) {
        const x=x0+rng()*(x1-x0),y=y0+rng()*(y1-y0);
        const width=isSky?8+rng()*20:2+rng()*5;
        const length=isSky?10+rng()*30:4+rng()*16;
        ctx.strokeStyle=isSky ? (rng()<.65?p.light:p.cloud) : (rng()<.5?p.light:p.shade);
        ctx.globalAlpha=isSky ? .025+rng()*.06 : .055+rng()*.1;
        ctx.lineWidth=width;ctx.lineCap='butt';
        const dx=m.name.startsWith('left')?-length*.25:m.name.startsWith('right')?length*.3:length*.08;
        path(ctx,[[x,y],[x+length,y+dx]],false);ctx.stroke();
        // Fine separated bristles leave breaks inside each broad mark.
        ctx.globalAlpha=isSky?.04:.12;ctx.lineWidth=.35;
        path(ctx,[[x,y-width*.3],[x+length*.8,y+dx-width*.3]],false);ctx.stroke();
      }
    });
  }
  grain(ctx,rng,11000,p.ink,.12);
}
function drawing(ctx,marks,p,rng) {
  for(const m of marks) {
    if(m.kind==='line') {
      const neighbor=m.name.includes('neighbour');
      ctx.globalAlpha=neighbor?.3:.8;
      outline(ctx,m.points,p.ink,neighbor?.4:m.name.includes('mullion')?.55:.7,false);
      ctx.globalAlpha=1;
      continue;
    }
    if(['sky','warm light','sky movement'].includes(m.name)) continue;
    const window=m.name.includes('window');
    const background=m.name.includes('neighbour')||m.name==='right streetscape';
    const selected=['left brick plane','rounded corner brick plane','roof coping','central cream pilaster'].includes(m.name);
    if(selected||window||background) fill(ctx,m.points,p[m.color],background?.09:window?.22:.3);
    ctx.globalAlpha=background?.2:.75;
    outline(ctx,m.points,p.ink,window?.45:.65);ctx.globalAlpha=1;
    if(m.name==='left brick plane') hatch(ctx,m.points,p.ink,5,.12);
    if(window) {
      hatch(ctx,m.points,p.ink,2.4,.38);
      // A second faint contour gives the drawing a searching, rather than CAD, line.
      outline(ctx,m.points.map(([x,y])=>[x+(rng()-.5)*.65,y+(rng()-.5)*.65]),p.ink,.2);
    }
  }
  grain(ctx,rng,3500,p.ink,.08);
}
function torn(points,rng) {
  const result=[];
  for(let i=0;i<points.length;i++) {
    const a=points[i],b=points[(i+1)%points.length];
    const distance=Math.hypot(b[0]-a[0],b[1]-a[1]);
    const steps=Math.max(1,Math.floor(distance/5));
    result.push(a);
    for(let j=1;j<steps;j++) {
      const t=j/steps;
      result.push([a[0]+(b[0]-a[0])*t+(rng()-.5)*1.2,a[1]+(b[1]-a[1])*t+(rng()-.5)*1.2]);
    }
  }
  return result;
}
function print(ctx,marks,p,rng) {
  for(const m of marks) {
    if(m.kind==='line') {
      if(m.name.includes('neighbour')) continue;
      outline(ctx,m.points,p.ink,m.name.includes('mullion')?.7:1.05,false);
      continue;
    }
    if(m.name==='sky movement'||m.name==='warm light') continue;
    if(m.name==='left plane cool shadow') {hatch(ctx,m.points,p.ink,2.1,.3);continue;}
    const points=torn(m.points,rng);
    const window=m.name.includes('window');
    if(!window&&m.name!=='sky') fill(ctx,points.map(([x,y])=>[x+1.3,y+1.7]),p.shade,.22);
    fill(ctx,points,p[m.color],window?.95:1);
    clipped(ctx,points,()=>{
      const [x0,y0,x1,y1]=bounds(m.points);
      // Small missing ink flecks: paper shows through, rather than water bleeding out.
      ctx.fillStyle=p.paper;
      for(let i=0;i<(x1-x0)*(y1-y0)/28;i++) {
        ctx.globalAlpha=.12+rng()*.2;
        ctx.fillRect(x0+rng()*(x1-x0),y0+rng()*(y1-y0),.3+rng()*.9,.3+rng()*1.6);
      }
      if(m.name==='sky'||m.name==='right brick plane') {
        ctx.fillStyle=p.ink;ctx.globalAlpha=m.name==='sky'?.1:.22;
        for(let y=y0;y<y1;y+=4) for(let x=x0;x<x1;x+=4) {
          ctx.beginPath();ctx.arc(x+((Math.floor(y/4)%2)*2),y,.48,0,Math.PI*2);ctx.fill();
        }
      }
    });
    if(window) {
      // The second ink plate deliberately sits slightly out of register.
      outline(ctx,m.points.map(([x,y])=>[x+1.2,y-.7]),p.brick,.65);
    }
  }
  grain(ctx,rng,13000,p.ink,.16);
}

// The data-driven batch uses semantic roles, never per-building rendering code.
const SCENE_INKS=Object.freeze({
  sky:{color:'sky',opacity:1,texture:true},
  'wall-warm':{color:'brick',opacity:1,texture:true},
  'wall-cool':{color:'shade',opacity:1,texture:true},
  'wall-light':{color:'plaster',opacity:1,texture:true},
  stone:{color:'plaster',opacity:1,texture:false},
  glass:{color:'glass',opacity:.92,texture:true},
  context:{color:'context',opacity:.85,texture:true},
  dark:{color:'ink',opacity:.95,texture:true},
  ochre:{color:'sky',opacity:1,texture:true},
  paper:{color:'light',opacity:1,texture:false},
});

// Returning an ink decision rather than changing geometry keeps line and colour separate.
export function hybridPlate(mark,colour='full') {
  if(!HYBRID_COLOURS.includes(colour)) throw new RangeError('Unknown hybrid colour treatment');
  if(mark.kind!=='wash') return null;
  if(mark.paintRole!==undefined) {
    if(colour!=='full'||!Object.hasOwn(SCENE_INKS,mark.paintRole)) throw new RangeError('Unsupported scene paint role or colour mode');
    return {...SCENE_INKS[mark.paintRole]};
  }
  if(colour==='full') {
    if(mark.name==='sky') return {color:'sky',opacity:1,texture:true};
    if(mark.name==='warm light') return {color:'cloud',opacity:.13,texture:false};
    if(['left brick plane','rounded corner brick plane'].includes(mark.name)) return {color:'brick',opacity:1,texture:true};
    if(mark.name==='right brick plane') return {color:'shade',opacity:1,texture:true};
    if(mark.name==='left plane cool shadow') return {color:'shade',opacity:.24,texture:true};
    if(mark.name==='roof shadow') return {color:'ink',opacity:.65,texture:false};
    if(mark.name==='roof coping'||mark.name.includes('sill band')||mark.name==='ground-floor plinth') return {color:'plaster',opacity:1,texture:false};
    if(mark.name==='central cream pilaster') return {color:'light',opacity:1,texture:false};
    if(mark.name.includes('window')) return {color:'glass',opacity:.92,texture:true};
    if(mark.name.includes('neighbour')||mark.name==='right streetscape') return {color:'context',opacity:.72,texture:true};
    return null;
  }
  if(mark.name==='left brick plane') return {color:'brick',opacity:.76,texture:true};
  if(mark.name==='rounded corner brick plane') return {color:'brick',opacity:.27,texture:true};
  if(mark.name==='roof coping') return {color:'sky',opacity:.44,texture:true};
  if(mark.name.includes('sill band') && !mark.name.startsWith('right')) return {color:'paper',opacity:1,texture:false};
  if(mark.name==='central cream pilaster') return {color:'paper',opacity:1,texture:false};
  if(mark.name.includes('window')) {
    const row=Number(mark.name.match(/window (\d+)/)?.[1]);
    const corner=mark.name.startsWith('corner');
    const accent=(corner && [1,3,5].includes(row)) || (mark.name.startsWith('left') && [3,5].includes(row));
    return {color:'glass',opacity:accent?.65:.08,texture:accent};
  }
  return null;
}
function hybridLine(ctx,m,p,rng) {
  const background=m.name.includes('neighbour')||m.name==='right streetscape';
  if(m.kind==='line') {
    if(background&&rng()<.35) return;
    ctx.globalAlpha=background?.22:.82;
    const ink=m.sceneMark&&m.color==='light'?p.light:p.ink;
    const width=m.sceneMark?m.weight:(background?.4:m.name.includes('mullion')?.6:.65);
    outline(ctx,m.points,ink,width,false);ctx.globalAlpha=1;return;
  }
  if(['sky','warm light','sky movement','left plane cool shadow','neighbour shadow','roof shadow'].includes(m.name)) return;
  ctx.globalAlpha=background?.18:.72;
  outline(ctx,m.points,p.ink,m.name.includes('window')?.45:.65,!background);ctx.globalAlpha=1;
  if(m.name.includes('window')) hatch(ctx,m.points,p.ink,2.6,m.name.startsWith('right')?.24:.16);
}
function hybrid(ctx,marks,p,rng,colour='full') {
  // Colour is a separate impression, laid down before the architectural drawing.
  for(const m of marks) {
    const plate=hybridPlate(m,colour);
    if(!plate) continue;
    if(!plate.texture) {fill(ctx,m.points,p[plate.color],plate.opacity);continue;}
    const cut=torn(m.points,rng);
    const offset=cut.map(([x,y])=>[x+1.1,y-.65]);
    fill(ctx,offset,p[plate.color],plate.opacity);
    clipped(ctx,offset,()=>{
      const [x0,y0,x1,y1]=bounds(offset);
      ctx.fillStyle=p.paper;
      for(let i=0;i<(x1-x0)*(y1-y0)/20;i++) {
        ctx.globalAlpha=.14+rng()*.28;
        ctx.fillRect(x0+rng()*(x1-x0),y0+rng()*(y1-y0),.2+rng()*.65,.4+rng()*1.2);
      }
    });
    if(m.name==='left brick plane') hatch(ctx,m.points,p.ink,4,.12);
  }
  // Lines retain source geometry. Later top-level scene masses occlude earlier lines.
  // Clip each hole separately: overlapping foreground silhouettes must not cancel out.
  for(const [index,m] of marks.entries()) {
    if(!m.sceneMark) {hybridLine(ctx,m,p,rng);continue;}
    ctx.save();
    try {
      for(const later of marks.slice(index+1)) {
        if(!later.occludes) continue;
        ctx.beginPath();ctx.rect(-1,-1,502,502);ctx.moveTo(...later.points[0]);
        for(const point of later.points.slice(1)) ctx.lineTo(...point);
        ctx.closePath();ctx.clip('evenodd');
      }
      hybridLine(ctx,m,p,rng);
    } finally {ctx.restore();}
  }
  // Fine paper tooth sits across the composition, independent of the ink plates.
  grain(ctx,rng,4200,p.ink,.08);
}

export function renderTreatment(canvas,id,{seed=29,colour='full',scene=null}={}) {
  const recipe=recipeFor(id);
  if(scene!==null&&(id!=='hybrid'||colour!=='full')) throw new RangeError('Compiled scenes use the full-color hybrid instrument');
  if(!HYBRID_COLOURS.includes(colour)) throw new RangeError('Unknown hybrid colour treatment');
  const palette=id==='hybrid'&&colour==='restrained'?RESTRAINED_PALETTE:recipe.palette;
  const rng=randomFor(seed);
  const marks=scene===null?selectedMarks(3):compileScene(scene);
  const ctx=canvas.getContext('2d');
  if(!ctx) throw new Error('A 2D canvas is required');
  if(canvas.width!==canvas.height||canvas.width<1) throw new RangeError('The study requires a square canvas');
  ctx.save();
  try {
    // Reset even if the same target is reused; no accumulation of transforms or marks.
    ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';
    ctx.clearRect(0,0,canvas.width,canvas.height);
    ctx.scale(canvas.width/500,canvas.height/500);
    ctx.fillStyle=palette.paper;ctx.fillRect(0,0,500,500);
    ctx.lineJoin='round';ctx.lineCap='round';
    ({graphic,opaque,drawing,print,hybrid})[id](ctx,marks,palette,rng,colour);
  } finally {ctx.restore();}
  return {id,seed,marks:marks.length};
}
