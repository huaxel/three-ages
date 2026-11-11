// Generic mark-level convenience API, not building/window/facade templates.
// Serialized into the isolated browser; generated artists never run on the host.
export function createPaintingAPI(p,scene){
 const rgba=(c,alpha=1)=>!c||c.a===0?null:`rgba(${Math.round(c.r)},${Math.round(c.g)},${Math.round(c.b)},${c.a*alpha})`,colour=c=>c?Object.freeze({r:c[0],g:c[1],b:c[2],a:c[3]}):null;
 const entries=scene.commands.filter(c=>!['rand','grain','hatch','brush'].includes(c.op)).map(c=>{const a=c.args,k=c.op;return Object.freeze({kind:k,bounds:Object.freeze({x:c.box[0],y:c.box[1],w:c.box[2]-c.box[0],h:c.box[3]-c.box[1]}),fill:colour(c.fill),stroke:colour(c.stroke),opacity:k==='ellipse'?a[7]:['poly','path'].includes(k)?a[4]:k==='line'?a[3]:1,width:k==='ellipse'?a[6]:['poly','path'].includes(k)?a[3]:k==='line'?a[2]:1,points:['poly','line'].includes(k)?a[0]:null,svg:k==='path'?a[0]:null,ellipse:k==='ellipse'?Object.freeze({x:a[0],y:a[1],rx:a[2],ry:a[3]}):null,stateArgument:k==='clip'?a[0]:null});});
 function state(m){if(['push','pop'].includes(m.kind)){p[m.kind]();return true;}if(m.kind==='clip'){p.clip(m.stateArgument);return true;}return false;}
 function shape(m,fill=rgba(m.fill),stroke=rgba(m.stroke),width=m.width,opacity=m.opacity){
  if(m.kind==='poly')p.poly(m.points,fill,stroke,width,opacity);else if(m.kind==='path')p.path(m.svg,fill,stroke,width,opacity);else if(m.kind==='ellipse'){const e=m.ellipse;p.ellipse(e.x,e.y,e.rx,e.ry,fill,stroke,width,opacity);}else if(m.kind==='line')p.line(m.points,stroke,width,opacity);else if(m.kind==='background'&&fill)p.background(fill);
 }
 function clipped(m,draw){let geometry=m.kind==='poly'?m.points:m.kind==='path'?m.svg:null;if(m.kind==='ellipse'){const {x,y,rx,ry}=m.ellipse;if(rx===0||ry===0)return false;geometry=`M${x-rx} ${y} A${rx} ${ry} 0 1 0 ${x+rx} ${y} A${rx} ${ry} 0 1 0 ${x-rx} ${y}Z`;}if(!geometry)return false;p.push();try{p.clip(geometry);draw();}finally{p.pop();}return true;}
 return Object.freeze({entries:Object.freeze(entries),rgba,state,shape,clipped});
}
