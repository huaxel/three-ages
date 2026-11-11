// Trusted browser instrument. Generic marks only: no building/window/facade templates.
(()=>{
  const canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d');
  let calls=0,state=29;
  const check=()=>{if(++calls>12000)throw Error('Drawing-call budget exceeded');};
  const finite=(...ns)=>{if(!ns.every(Number.isFinite))throw Error('Non-finite drawing coordinate');};
  const random=()=>{state=(state+0x6D2B79F5)|0;let n=Math.imul(state^(state>>>15),1|state);n^=n+Math.imul(n^(n>>>7),61|n);return((n^(n>>>14))>>>0)/4294967296;};
  const points=ps=>{if(!Array.isArray(ps)||ps.length<2||ps.length>2048)throw Error('Invalid point list');for(const p of ps){if(!Array.isArray(p)||p.length!==2)throw Error('Expected [x,y]');finite(...p);}};
  function shape(path,fill,stroke,width=1,alpha=1){finite(width,alpha);ctx.save();try{ctx.globalAlpha=Math.max(0,Math.min(1,alpha));if(fill){ctx.fillStyle=fill;ctx.fill(path);}if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=Math.max(.05,Math.min(100,width));ctx.stroke(path);}}finally{ctx.restore();}}
  function polyPath(ps){points(ps);const d=new Path2D();d.moveTo(...ps[0]);for(const p of ps.slice(1))d.lineTo(...p);d.closePath();return d;}
  const p=Object.freeze({
    background(color){check();ctx.fillStyle=color;ctx.fillRect(0,0,1000,1000);},
    poly(ps,fill,stroke=null,width=1,alpha=1){check();shape(polyPath(ps),fill,stroke,width,alpha);},
    path(d,fill,stroke=null,width=1,alpha=1){check();if(typeof d!=='string'||d.length>16000)throw Error('Invalid SVG path');shape(new Path2D(d),fill,stroke,width,alpha);},
    line(ps,color,width=1,alpha=1){check();points(ps);const d=new Path2D();d.moveTo(...ps[0]);for(const p of ps.slice(1))d.lineTo(...p);shape(d,null,color,width,alpha);},
    ellipse(x,y,rx,ry,fill,stroke=null,width=1,alpha=1){check();finite(x,y,rx,ry);if(rx<0||ry<0)throw Error('Negative radius');const d=new Path2D();d.ellipse(x,y,rx,ry,0,0,Math.PI*2);shape(d,fill,stroke,width,alpha);},
    brush(ps,color,width=12,alpha=.7){check();points(ps);finite(width,alpha);ctx.save();try{ctx.strokeStyle=color;ctx.lineCap='round';for(let bristle=0;bristle<12;bristle++){ctx.globalAlpha=Math.max(0,Math.min(1,alpha))*(.15+random()*.35);ctx.lineWidth=Math.max(.2,width/12);ctx.beginPath();const dx=(random()-.5)*width,dy=(random()-.5)*width;ctx.moveTo(ps[0][0]+dx,ps[0][1]+dy);for(const [x,y]of ps.slice(1))ctx.lineTo(x+dx+(random()-.5),y+dy+(random()-.5));ctx.stroke();}}finally{ctx.restore();}},
    hatch(ps,color,spacing=6,angle=-45,width=.6,alpha=.3){check();finite(spacing,angle,width,alpha);if(spacing<2)throw Error('Hatch spacing must be >=2');ctx.save();try{ctx.clip(polyPath(ps));ctx.translate(500,500);ctx.rotate(angle*Math.PI/180);ctx.strokeStyle=color;ctx.lineWidth=width;ctx.globalAlpha=Math.max(0,Math.min(1,alpha));for(let x=-1500;x<1500;x+=spacing){ctx.beginPath();ctx.moveTo(x,-1500);ctx.lineTo(x,1500);ctx.stroke();}}finally{ctx.restore();}},
    grain(color,alpha=.08,count=5000){check();finite(alpha,count);if(count<0||count>20000)throw Error('Grain budget exceeded');ctx.save();try{ctx.fillStyle=color;for(let i=0;i<count;i++){ctx.globalAlpha=random()*Math.max(0,Math.min(1,alpha));const s=.3+random()*1.4;ctx.fillRect(random()*1000,random()*1000,s,s);}}finally{ctx.restore();}},
    rand(min=0,max=1){finite(min,max);return min+random()*(max-min);},
    push(){check();ctx.save();},pop(){check();ctx.restore();},
    clip(d){check();ctx.clip(typeof d==='string'?new Path2D(d):polyPath(d));},
  });
  ctx.lineJoin='round';ctx.lineCap='round';
  Object.defineProperty(window,'painter',{value:p,writable:false});
  Object.defineProperty(window,'paintStats',{get:()=>({calls,width:canvas.width,height:canvas.height})});
})();
