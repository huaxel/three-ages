// Trusted capture wrapper. The model-authored source program still runs only inside the container.
(()=>{
 const commands=[],colourCanvas=document.createElement('canvas');colourCanvas.width=colourCanvas.height=1;const cc=colourCanvas.getContext('2d');
 const defaults={poly:[null,null,null,1,1],path:[null,null,null,1,1],line:[null,null,1,1],ellipse:[0,0,0,0,null,null,1,1],brush:[null,null,12,.7],hatch:[null,null,6,-45,.6,.3],grain:[null,.08,5000],rand:[0,1],background:[null],clip:[null],push:[],pop:[]};
 const rgba=c=>{if(c==null)return null;if(typeof c!=='string'||!CSS.supports('color',c))throw Error('Capture requires CSS colour strings');cc.clearRect(0,0,1,1);cc.fillStyle=c;cc.fillRect(0,0,1,1);const d=cc.getImageData(0,0,1,1).data;return [d[0],d[1],d[2],d[3]/255];};
 const bounds=ps=>{const xs=ps.map(p=>p[0]),ys=ps.map(p=>p[1]);return [Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)];};
 const pathBox=d=>{const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'),p=document.createElementNS(svg.namespaceURI,'path');p.setAttribute('d',d);svg.append(p);document.body.append(svg);try{const b=p.getBBox();return [b.x,b.y,b.x+b.width,b.y+b.height];}finally{svg.remove();}};
 window.capturePainter=()=>{
  const q={};for(const op of Object.keys(defaults))q[op]=(...incoming)=>{
   if(commands.length>=30000)throw Error('Capture command budget exceeded');const a=defaults[op].map((d,i)=>incoming[i]===undefined?d:incoming[i]);let box=[0,0,1000,1000],fill=null,stroke=null;
   if(['poly','line','brush','hatch'].includes(op))box=bounds(a[0]);else if(op==='path')box=pathBox(a[0]);else if(op==='ellipse')box=[a[0]-a[2],a[1]-a[3],a[0]+a[2],a[1]+a[3]];
   if(['poly','path'].includes(op)){fill=rgba(a[1]);stroke=rgba(a[2]);}else if(op==='ellipse'){fill=rgba(a[4]);stroke=rgba(a[5]);}else if(op==='background')fill=rgba(a[0]);else if(['line','brush','hatch','grain'].includes(op))stroke=rgba(a[op==='grain'?0:1]);
   const args=JSON.parse(JSON.stringify(a));commands.push({op,args,box,fill,stroke});return painter[op](...a);
  };return Object.freeze(q);
 };
 window.readCapture=()=>commands;
})();
