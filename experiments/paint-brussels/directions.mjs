import {TREATMENTS, renderTreatment, directionOptions} from './treatments.mjs';

const form=document.querySelector('#direction-controls');
const grid=document.querySelector('#directions-grid');
const status=document.querySelector('#direction-status');
const sheetLink=document.querySelector('#sheet-download');
const hybridSheetLink=document.querySelector('#hybrid-comparison-download');
const restrainedLink=document.querySelector('#restrained-download');
const exportLinks=[sheetLink,hybridSheetLink,restrainedLink];
const originalTreatments=TREATMENTS.filter(recipe=>recipe.id!=='hybrid');
const dialog=document.querySelector('#detail-dialog');
const cards=new Map();
let busy=false;
window.directionStudy={state:'loading'};
form.elements.seed.value=directionOptions(location.search).seed;

function showDetail(recipe,card) {
  document.querySelector('#detail-title').textContent=recipe.title;
  const image=document.querySelector('#detail-image');
  image.src=card.png;image.alt=`${recipe.title}: code-rendered interpretation of Democratiestraat 29`;
  document.querySelector('#detail-description').textContent=recipe.description;
  const download=document.querySelector('#detail-download');
  download.href=card.png;download.download=card.download.download;
  dialog.showModal();
}
for(const recipe of TREATMENTS) {
  const article=document.createElement('article');article.className='direction-card';
  if(recipe.id==='hybrid') article.id='hybrid';
  const subtitle=document.createElement('p');subtitle.className='eyebrow';subtitle.textContent=`${recipe.number} / ${recipe.subtitle}`;
  const heading=document.createElement('h2');heading.textContent=recipe.title;
  const button=document.createElement('button');button.className='art-button';button.type='button';
  button.setAttribute('aria-label',`Look closer: ${recipe.title}`);
  const canvas=document.createElement('canvas');canvas.width=1000;canvas.height=1000;canvas.id=`treatment-${recipe.id}`;
  canvas.setAttribute('role','img');canvas.setAttribute('aria-label',`${recipe.title}: computational study of Democratiestraat 29`);
  button.append(canvas);
  const caption=document.createElement('div');caption.className='direction-caption';
  const description=document.createElement('p');description.textContent=recipe.description;
  const download=document.createElement('a');download.textContent='Save PNG ↓';download.setAttribute('aria-disabled','true');
  caption.append(description,download);article.append(subtitle,heading,button,caption);
  (recipe.id==='hybrid'?document.querySelector('#hybrid-feature'):grid).append(article);
  const card={canvas,button,download,png:null};cards.set(recipe.id,card);
  button.disabled=true;
  button.addEventListener('click',()=>{if(card.png) showDetail(recipe,card);});
}

document.querySelector('#close-detail').addEventListener('click',()=>dialog.close());
for(const ref of document.querySelectorAll('#direction-reference,#detail-reference')) {
  const missing=()=>{ref.hidden=true;document.querySelector('#reference-error').hidden=false;};
  ref.addEventListener('error',missing);
  if(ref.complete&&!ref.naturalWidth) missing();
}

function makeContactSheet(seed) {
  const canvas=document.createElement('canvas');canvas.width=1600;canvas.height=1800;
  const ctx=canvas.getContext('2d');
  if(!ctx) throw new Error('Cannot create contact sheet');
  ctx.fillStyle='#f6f3ec';ctx.fillRect(0,0,1600,1800);ctx.fillStyle='#293a34';
  ctx.font='44px Georgia';ctx.fillText('Same corner. Four ways of seeing.',60,75);
  ctx.font='17px sans-serif';ctx.fillText('BUILDINGS OF BRUSSELS / DEMOCRATIESTRAAT 29 / AGENT-AUTHORED CODE STUDIES',60,113);
  for(const [i,recipe] of originalTreatments.entries()) {
    const x=60+(i%2)*770,y=155+Math.floor(i/2)*795;
    ctx.drawImage(cards.get(recipe.id).canvas,x,y,710,710);
    ctx.fillStyle='#293a34';ctx.font='28px Georgia';ctx.fillText(`${recipe.number} / ${recipe.title}`,x,y+755);
  }
  ctx.font='15px sans-serif';ctx.fillText(`Same geometry · Canvas 2D · seed ${seed} · no trained model`,60,1770);
  return canvas.toDataURL('image/png');
}
function makeHybridComparison(seed) {
  const canvas=document.createElement('canvas');canvas.width=2200;canvas.height=1000;
  const ctx=canvas.getContext('2d');
  if(!ctx) throw new Error('Cannot create hybrid comparison');
  ctx.fillStyle='#f6f3ec';ctx.fillRect(0,0,2200,1000);ctx.fillStyle='#293a34';
  ctx.font='46px Georgia';ctx.fillText('Drawing + imperfect ink',60,75);
  ctx.font='18px sans-serif';ctx.fillText('BUILDINGS OF BRUSSELS / DEMOCRATIESTRAAT 29 / 03 + 04 → 05',60,115);
  for(const [i,id] of ['drawing','hybrid','print'].entries()) {
    const recipe=TREATMENTS.find(t=>t.id===id),x=60+i*715;
    ctx.drawImage(cards.get(id).canvas,x,155,650,650);
    ctx.fillStyle='#293a34';ctx.font='30px Georgia';ctx.fillText(`${recipe.number} / ${recipe.title}`,x,855);
  }
  ctx.font='17px sans-serif';ctx.fillText(`Same geometry · Canvas 2D · seed ${seed} · agent-authored, not trained`,60,950);
  return canvas.toDataURL('image/png');
}
async function rebuild(options) {
  if(busy) return;
  busy=true;status.hidden=false;status.textContent='Building the hybrid and its starting points…';
  form.querySelector('button').disabled=true;
  for(const link of exportLinks) {link.removeAttribute('href');link.setAttribute('aria-disabled','true');}
  for(const card of cards.values()) {
    card.png=null;card.button.disabled=true;card.download.removeAttribute('href');card.download.setAttribute('aria-disabled','true');
  }
  window.directionStudy={state:'rendering'};
  try {
    await new Promise(resolve=>requestAnimationFrame(resolve));
    const results={};
    for(const recipe of TREATMENTS) {
      const card=cards.get(recipe.id);
      const metadata=renderTreatment(card.canvas,recipe.id,options);
      card.png=card.canvas.toDataURL('image/png');
      card.download.href=card.png;card.download.download=`brussels-001-${recipe.id}-seed${options.seed}.png`;
      card.download.setAttribute('aria-disabled','false');card.button.disabled=false;
      results[recipe.id]=metadata;
    }
    const restrainedCanvas=document.querySelector('#restrained-preview');
    renderTreatment(restrainedCanvas,'hybrid',{...options,colour:'restrained'});
    restrainedLink.href=restrainedCanvas.toDataURL('image/png');
    restrainedLink.download=`brussels-001-hybrid-restrained-seed${options.seed}.png`;
    restrainedLink.setAttribute('aria-disabled','false');
    sheetLink.href=makeContactSheet(options.seed);sheetLink.download=`brussels-001-four-directions-seed${options.seed}.png`;
    sheetLink.setAttribute('aria-disabled','false');
    hybridSheetLink.href=makeHybridComparison(options.seed);
    hybridSheetLink.download=`brussels-001-hybrid-comparison-seed${options.seed}.png`;
    hybridSheetLink.setAttribute('aria-disabled','false');
    history.replaceState(null,'',`${location.pathname}?seed=${options.seed}`);
    window.directionStudy={state:'ready',seed:options.seed,results};status.hidden=true;
  } catch(error) {
    window.directionStudy={state:'error',error:String(error)};
    status.textContent=`The sheet could not render: ${error.message}`;console.error(error);
    for(const link of exportLinks) {link.removeAttribute('href');link.setAttribute('aria-disabled','true');}
    for(const card of cards.values()) {
      card.png=null;card.button.disabled=true;card.download.removeAttribute('href');card.download.setAttribute('aria-disabled','true');
    }
  } finally {busy=false;form.querySelector('button').disabled=false;}
}
form.addEventListener('submit',event=>{
  event.preventDefault();if(!form.reportValidity()) return;
  rebuild(directionOptions(new URLSearchParams(new FormData(form)).toString()));
});
rebuild(directionOptions(location.search));
