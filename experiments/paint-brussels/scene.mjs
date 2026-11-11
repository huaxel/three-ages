// First study: agent-authored from visual inspection, not CV extraction or training.
// Coordinates refer to the 500 × 500 source photograph, including its white margin.
export const SOURCE = Object.freeze({
  title: 'Democratiestraat 29',
  place: 'Veeweide–Aurora, Anderlecht',
  project: 'Buildings of Brussels',
  post: 'https://www.tumblr.com/buildingsofbrussels/162278233614/democratiestraat-29-veeweide-aurora-district',
  image: 'https://64.media.tumblr.com/073de691721dce57c05ba309feb16415/tumblr_os5s6i5A771vensaeo1_500.jpg',
  sha256: '7e09f6e22ba769ad95d89c1719f7b41fcc2bcdd23b427b22d542773f6829b3cd',
  rights: 'User identifies Buildings of Brussels as their photographic project. No public reuse licence verified; reference pixels stay in ignored local/. Revisit rights before redistribution.',
});

export const PALETTES = Object.freeze({
  earth: {paper:'#f5f0e5', sky:'#b3bdc3', cloud:'#e6daca', brick:'#a76448', shade:'#775d59', plaster:'#ddd2b9', glass:'#555e66', light:'#eee5cf', ink:'#645e59', context:'#a28d7c'},
  dusk: {paper:'#f2ece6', sky:'#a4a6c2', cloud:'#ddbdad', brick:'#a66568', shade:'#6d617d', plaster:'#d6c8c1', glass:'#535d79', light:'#e8d8bd', ink:'#696078', context:'#a88c9a'},
});
export const STAGES = ['Masses', 'Window rhythm', 'Architectural accents'];

export function pointOn(quad, u, v) {
  const [a,b,c,d] = quad;
  return [0,1].map(k => (1-v)*((1-u)*a[k]+u*b[k]) + v*((1-u)*d[k]+u*c[k]));
}
export function patch(quad, u0, v0, u1, v1) {
  return [[u0,v0],[u1,v0],[u1,v1],[u0,v1]].map(([u,v]) => pointOn(quad,u,v));
}
export function optionsFrom(search = '') {
  const p = new URLSearchParams(search);
  const n = Number(p.get('stage') ?? 3);
  const seed = Number(p.get('seed') ?? 29);
  return {
    palette: Object.hasOwn(PALETTES, p.get('palette')) ? p.get('palette') : 'earth',
    stage: Number.isInteger(n) && n >= 1 && n <= 3 ? n : 3,
    seed: Number.isSafeInteger(seed) && seed >= 0 && seed <= 999999 ? seed : 29,
  };
}

// A mark is one polygon wash or one drawn line, not a simulated bristle stroke.
export function makeScene() {
  const marks = [];
  const wash = (name, points, color, stage=1, opacity=180) => marks.push({kind:'wash', name, points, color, stage, opacity});
  const line = (name, points, color='ink', stage=3, weight=0.5) => marks.push({kind:'line', name, points, color, stage, weight});
  wash('sky', [[72,14],[427,14],[427,477],[73,486]], 'sky',1,80);
  wash('warm light', [[180,14],[427,14],[427,325],[220,246]], 'cloud',1,75);
  wash('sky movement', [[74,127],[165,89],[285,73],[397,92],[275,112],[140,159]], 'light',1,45);
  wash('left neighbour', [[73,365],[104,347],[102,476],[73,487]], 'context',1,160);
  wash('right streetscape', [[325,327],[348,332],[351,358],[370,365],[376,394],[392,405],[410,405],[427,433],[427,487],[351,487]], 'context',1,155);
  wash('neighbour shadow', [[355,370],[377,397],[392,416],[393,485],[360,482]], 'shade',1,130);

  const left = [[121,251],[187,190],[173,449],[77,485]];
  const front = [[187,190],[272,192],[289,450],[173,449]];
  const right = [[272,192],[326,252],[359,482],[289,450]];
  wash('left brick plane', left, 'brick',1,195);
  wash('left plane cool shadow', left, 'shade',1,60);
  wash('rounded corner brick plane', front, 'brick',1,200);
  wash('right brick plane', right, 'brick',1,160);
  wash('roof coping', [[117,251],[188,177],[201,173],[264,175],[275,181],[330,253],[326,258],[271,190],[190,188],[121,256]], 'plaster');
  wash('roof shadow', [[126,246],[192,183],[267,184],[320,248],[270,193],[190,192]], 'shade',1,115);
  wash('ground-floor plinth', [[78,454],[173,428],[287,429],[355,455],[359,486],[73,486]], 'plaster',1,225);

  // Repeated bays share perspective. Geometry and the painting medium are separate.
  // Five rows preserve the source's vertical rhythm; omissions remain explicit.
  const rows = [[.075,.125],[.23,.292],[.405,.477],[.585,.658],[.785,.88]];
  const faces = [{q:left, bays:[[.08,.22],[.32,.48],[.58,.74],[.83,.95]], label:'left'},
    {q:front, bays:[[.09,.43],[.56,.9]], label:'corner'},
    {q:right, bays:[[.08,.29],[.42,.61],[.73,.92]], label:'right'}];
  for (const {q,bays,label} of faces) {
    for (const [row,[v0,v1]] of rows.entries()) {
      wash(`${label} sill band ${row+1}`, patch(q,0,v1+.008,1,v1+.072), 'plaster',2,220);
      for (const [bay,[u0,u1]] of bays.entries()) {
        wash(`${label} window ${row+1}.${bay+1}`, patch(q,u0,v0,u1,v1), 'glass',2,185);
        if (label === 'corner') {
          const mid=(u0+u1)/2;
          line(`${label} mullion ${row+1}.${bay+1}`, [pointOn(q,mid,v0), pointOn(q,mid,v1)],'light',3,.8);
        }
      }
      line(`${label} sill shadow ${row+1}`, [pointOn(q,0,v1+.074),pointOn(q,1,v1+.074)],'shade',3,.55);
    }
  }
  wash('central cream pilaster', [[228,188],[235,189],[235,449],[225,449]], 'light',3,245);
  line('pilaster shadow', [[226,192],[224,446]], 'shade',3,.65);
  line('left cornice edge', [[118,251],[189,179],[202,176],[264,178]],'ink',3,.85);
  line('right cornice edge', [[265,178],[274,183],[330,253]],'ink',3,.65);
  line('corner shoulder', [[188,192],[183,270],[177,367],[173,428]],'brick',3,1.2);
  line('ground-floor ledge', [[79,454],[173,429],[287,430],[354,456]],'shade',3,1.1);
  line('street edge', [[75,486],[358,486]],'shade',3,.75);
  // Background gets fewer, lighter marks than the subject; no invented fine ornament.
  for (let i=0;i<5;i++) {
    const x=365+i*12, top=367+i*12;
    line(`neighbour vertical ${i}`,[[x,top],[x+8,482]],'shade',3,.6);
    for(let j=0;j<3;j++) line(`neighbour opening ${i}.${j}`,[[x+2,top+17+j*24],[x+7,top+20+j*24]],'glass',3,1.5);
  }
  return marks;
}
export function selectedMarks(stage) {
  if (!Number.isInteger(stage) || stage < 1 || stage > 3) throw new RangeError('stage must be 1, 2 or 3');
  return makeScene().filter(m => m.stage <= stage).sort((a,b)=>a.stage-b.stage);
}
