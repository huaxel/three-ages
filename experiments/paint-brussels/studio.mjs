import {PALETTES, optionsFrom, selectedMarks} from './scene.mjs';

const form = document.querySelector('#controls');
const status = document.querySelector('#status');
const download = document.querySelector('#download');
let busy = false;
let canvas;
window.paintStudy = {state:'loading'};
const initial = optionsFrom(location.search);
for (const [key,value] of Object.entries(initial)) form.elements[key].value = value;
const ref = document.querySelector('#reference');
const missing = () => { ref.hidden=true; document.querySelector('#missing').hidden=false; };
ref.addEventListener('error', missing);
if (ref.complete && !ref.naturalWidth) missing();

async function paint(options) {
  if (busy) return;
  busy = true;
  form.querySelector('button').disabled=true;
  download.removeAttribute('href'); download.setAttribute('aria-disabled','true');
  status.hidden=false;
  window.paintStudy = {state:'painting', options};
  try {
    const b=window.brush;
    if (!b) throw new Error('The local brush engine did not load.');
    status.textContent='Laying in the masses…';
    await new Promise(resolve=>requestAnimationFrame(resolve));
    if (!canvas) {
      canvas=b.createCanvas(700,700,{parent:'#painting',pixelDensity:1,id:'paint-canvas'});
      // scaleBrushes multiplies the engine's brush definitions; apply only once.
      b.scaleBrushes(2);
    }
    b.seed(options.seed); b.noiseSeed(options.seed);
    b.clear(PALETTES[options.palette].paper);
    b.noHatch(); b.noField(); b.noWash();
    const palette=PALETTES[options.palette];
    const marks=selectedMarks(options.stage);
    b.push();
    try {
      b.translate(-350,-350); b.scale(1.4);
      for (const mark of marks) {
        if(mark.kind==='wash') {
          b.noStroke(); b.fill(palette[mark.color],mark.opacity);
          b.fillBleed(.08,'out'); b.fillTexture(.32,.18,false);
          b.beginShape(0);
          for(const [x,y] of mark.points) b.vertex(x,y);
          b.endShape(true);
        } else {
          b.noFill(); b.set('rotring',palette[mark.color],mark.weight);
          for(let i=1;i<mark.points.length;i++) b.line(...mark.points[i-1],...mark.points[i]);
        }
      }
    } finally { b.pop(); }
    b.render();
    // Capture in the render task: WebGL's drawing buffer need not survive a frame.
    const png=canvas.toDataURL('image/png');
    download.href=png;
    download.download=`brussels-study-001-${options.palette}-pass${options.stage}-seed${options.seed}.png`;
    download.setAttribute('aria-disabled','false');
    document.querySelector('#mark-count').textContent=`${marks.length} authored marks · seed ${options.seed}`;
    const query=new URLSearchParams(Object.entries(options).map(([k,v])=>[k,String(v)]));
    history.replaceState(null,'',`${location.pathname}?${query}`);
    window.paintStudy={state:'ready',options,marks:marks.length,png};
    status.hidden=true;
  } catch(error) {
    console.error(error);
    window.paintStudy={state:'error',error:String(error)};
    status.textContent=`Painting could not render: ${error.message}. A WebGL2-capable browser is required.`;
  } finally {
    busy=false; form.querySelector('button').disabled=false;
  }
}
form.addEventListener('submit',event=>{
  event.preventDefault();
  if (!form.reportValidity()) return;
  const query=new URLSearchParams(new FormData(form));
  paint(optionsFrom(query.toString()));
});
paint(initial);
