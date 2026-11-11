import {parseCatalog,parseSceneJSON,compileScene} from './scene-format.mjs';
import {renderTreatment,directionOptions} from './treatments.mjs';
import {sheetLayout} from './sheet-layout.mjs';

const status=document.querySelector('#batch-status');
const form=document.querySelector('#batch-controls');
const download=document.querySelector('#batch-download');
const cards=[];
let busy=false;
window.batchStudy={state:'loading'};
form.elements.seed.value=directionOptions(location.search).seed;
async function getText(path) {
  const response=await fetch(path);
  if(!response.ok) throw new Error(`Missing local study asset: ${path}`);
  return response.text();
}
function addStudy(item,scene,index) {
  const article=document.createElement('article');article.className='building-study';article.id=item.id;
  const header=document.createElement('div');header.className='study-header';
  const heading=document.createElement('h2');heading.textContent=`0${index+1} / ${item.title}`;
  const place=document.createElement('p');place.textContent=item.place;header.append(heading,place);
  const pair=document.createElement('div');pair.className='study-pair';
  const source=document.createElement('figure'),painting=document.createElement('figure');
  const image=document.createElement('img');image.className='source-image';image.alt=`Buildings of Brussels photograph: ${item.title}`;
  image.src=`/local/paint-brussels/batch/${item.file}`;
  const missing=document.createElement('p');missing.className='source-missing';missing.hidden=true;
  missing.textContent='Reference not prepared. Run python3 experiments/paint-brussels/prepare-batch.py.';
  image.addEventListener('error',()=>{image.hidden=true;missing.hidden=false;});
  const sourceCaption=document.createElement('figcaption');
  const sourceLabel=document.createElement('span');sourceLabel.textContent='THE PHOTOGRAPH';
  const credit=document.createElement('a');credit.href=item.post;credit.textContent='Buildings of Brussels ↗';
  sourceCaption.append(sourceLabel,credit);source.append(image,missing,sourceCaption);
  const canvas=document.createElement('canvas');canvas.width=1000;canvas.height=1000;canvas.id=`batch-${item.id}`;
  canvas.setAttribute('role','img');canvas.setAttribute('aria-label',`Code-painted interpretation of ${item.title}`);
  const caption=document.createElement('figcaption');
  const label=document.createElement('span');label.textContent='THE SAME PAINTER';
  const counts=document.createElement('span');caption.append(label,counts);painting.append(canvas,caption);
  pair.append(source,painting);
  const detail=document.createElement('div');detail.className='study-detail';
  const notes=document.createElement('details'),summary=document.createElement('summary');summary.textContent='What was simplified · agent interpretation, not reviewed';
  const list=document.createElement('ul');
  for(const note of scene.omissions) {const li=document.createElement('li');li.textContent=note;list.append(li);}
  notes.append(summary,list);
  const data=document.createElement('a');data.href=`/scenes/${item.scene}`;data.download=item.scene;data.textContent='Scene JSON ↓';
  const save=document.createElement('a');save.textContent='Save PNG ↓';save.setAttribute('aria-disabled','true');
  detail.append(notes,data,save);article.append(header,pair,detail);document.querySelector('#collection').append(article);
  cards.push({item,scene,canvas,save,counts});
}
function contactSheet(seed) {
  const layout=sheetLayout(cards.length);
  const canvas=document.createElement('canvas');canvas.width=layout.width;canvas.height=layout.height;
  const ctx=canvas.getContext('2d');if(!ctx) throw new Error('Cannot create contact sheet');
  ctx.fillStyle='#f6f3ec';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#293a34';
  ctx.font='46px Georgia';ctx.fillText('One painter. Different buildings.',60,75,canvas.width-120);
  ctx.font='18px sans-serif';ctx.fillText(`BUILDINGS OF BRUSSELS / ${cards.length}-SUBJECT TRANSFER STUDY`,60,115,canvas.width-120);
  for(const [index,card] of cards.entries()) {
    const {x,y,size}=layout.tiles[index];
    ctx.drawImage(card.canvas,x,y,size,size);ctx.fillStyle='#293a34';ctx.font='27px Georgia';ctx.fillText(card.item.title,x,y+700,size);
    ctx.font='17px sans-serif';ctx.fillText(card.item.place,x,y+735,size);
  }
  ctx.font='17px sans-serif';ctx.fillText(`Same instrument and palette · seed ${seed} · agent-interpreted scenes, no trained model`,60,canvas.height-50,canvas.width-120);
  return canvas.toDataURL('image/png');
}
async function repaint(options) {
  if(busy) return;
  busy=true;form.querySelector('button').disabled=true;
  download.removeAttribute('href');download.setAttribute('aria-disabled','true');
  status.hidden=false;status.textContent='Painting the collection with one shared instrument…';
  for(const card of cards) {card.save.removeAttribute('href');card.save.setAttribute('aria-disabled','true');}
  window.batchStudy={state:'rendering'};
  try {
    await new Promise(resolve=>requestAnimationFrame(resolve));
    const report=[];
    for(const card of cards) {
      const result=renderTreatment(card.canvas,'hybrid',{...options,scene:card.scene});
      card.save.href=card.canvas.toDataURL('image/png');card.save.download=`brussels-batch-${card.item.id}-seed${options.seed}.png`;
      card.save.setAttribute('aria-disabled','false');
      card.counts.textContent=`${card.scene.elements.length} scene elements → ${result.marks} marks`;
      report.push({id:card.item.id,elements:card.scene.elements.length,marks:result.marks,method:card.scene.method});
    }
    download.href=contactSheet(options.seed);download.download=`brussels-batch-seed${options.seed}.png`;download.setAttribute('aria-disabled','false');
    document.querySelector('#batch-summary').textContent=`${cards.length} photographs · one painter · no per-building drawing code`;
    history.replaceState(null,'',`${location.pathname}?seed=${options.seed}`);
    window.batchStudy={state:'ready',seed:options.seed,report};status.hidden=true;
  } catch(error) {
    console.error(error);status.textContent=`Collection could not render: ${error.message}`;
    window.batchStudy={state:'error',error:String(error)};
    download.removeAttribute('href');download.setAttribute('aria-disabled','true');
    for(const card of cards) {card.save.removeAttribute('href');card.save.setAttribute('aria-disabled','true');}
  } finally {busy=false;form.querySelector('button').disabled=false;}
}
try {
  const catalog=parseCatalog(await getText('/batch-catalog.json'));
  // All data is checked before any scene is sent to the painter.
  const loaded=await Promise.all(catalog.items.map(async item=>{
    const scene=parseSceneJSON(await getText(`/scenes/${item.scene}`));
    if(scene.id!==item.id||scene.source!==item.id) throw new Error(`Source identity mismatch: ${item.id}`);
    compileScene(scene);return {item,scene};
  }));
  loaded.forEach(({item,scene},index)=>addStudy(item,scene,index));
  form.addEventListener('submit',event=>{
    event.preventDefault();if(form.reportValidity()) repaint(directionOptions(new URLSearchParams(new FormData(form)).toString()));
  });
  await repaint(directionOptions(location.search));
} catch(error) {
  console.error(error);status.textContent=`Collection could not load: ${error.message}`;
  window.batchStudy={state:'error',error:String(error)};form.querySelector('button').disabled=true;
}
