'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const dir = path.join(__dirname, 'three-ages/training');
const API = require(path.join(dir, 'review_workbench_model.js'));
const clone = x => JSON.parse(JSON.stringify(x));
function lockManager() {
  const tails = new Map();
  return {request(key, _options, callback) {
    const next = (tails.get(key) || Promise.resolve()).catch(() => {}).then(callback);
    tails.set(key, next);
    return next;
  }};
}
function bundle() {
  const fields = ['image_id', 'identity', 'observation', 'reviewer', 'reviewed_at', 'confidence'];
  return {schema: 'image-review-workbench/1', kind: 'pair', cohort_id: 'abcd', baseline_sha256: 'f'.repeat(64), fields,
    editable: fields.slice(1), decision_field: 'identity', decisions: ['same', 'different', 'uncertain'],
    rows: ['a', 'b', 'c'].map(key => ({key, values: Object.fromEntries(fields.map(f => [f, f === 'image_id' ? key : ''])), images: [], context: []}))};
}
const complete = {identity: 'uncertain', observation: 'Visible masonry differs', reviewer: 'Human', reviewed_at: '2026-10-25', confidence: 'low'};
function backup(model, rows) { return {...model.exportDrafts(), rows}; }

test('blank defaults never generate labels or phantom drafts', () => {
  const m = API.create(bundle());
  assert.equal(m.values('a').identity, '');
  assert.equal(m.completed('a'), false);
  assert.deepEqual(m.exportDrafts().rows, []);
  m.setDraft('a', {identity: ''});
  assert.deepEqual(m.exportDrafts().rows, []);
  assert.doesNotThrow(() => m.exportCSV());
});
test('partial rows persist but block CSV; all required fields and real ISO dates required', () => {
  const m = API.create(bundle());
  m.setDraft('a', {observation: 'Partial note'});
  assert.throws(() => m.exportCSV(), /Incomplete/);
  const n = API.create(bundle()); n.importDrafts(JSON.stringify(m.exportDrafts()));
  assert.equal(n.values('a').observation, 'Partial note');
  n.setDraft('a', {...complete, reviewed_at: '2026-02-30'});
  assert.equal(n.completed('a'), false);
  assert.throws(() => n.exportCSV(), /ISO date/);
  n.setDraft('a', {reviewed_at: '2024-02-29'});
  assert.equal(n.completed('a'), true);
  n.setDraft('a', {confidence: ' '});
  assert.equal(n.completed('a'), false);
});
test('confidence is controlled and backend-compatible timestamps complete locked sources', () => {
  const m = API.create(bundle());
  m.setDraft('a', {...complete, confidence: 'certain'});
  assert.equal(m.completed('a'), false);
  assert.throws(() => m.exportCSV(), /confidence/);
  m.setDraft('a', {confidence: 'medium'});
  assert.equal(m.completed('a'), true);
  for (const stamp of ['2026-10-25', '2026-10-25T13:15:27Z', '2026-10-25T13:15:27.123456+02:00', '2026-10-25T13:15:27-04:30']) {
    const b = bundle(); Object.assign(b.rows[0].values, complete, {reviewed_at: stamp});
    const source = API.create(b);
    assert.equal(source.locked('a'), true);
    assert.equal(source.completed('a'), true, stamp);
    assert.deepEqual(source.keys(true), ['b', 'c']);
    assert.ok(source.exportCSV().includes(stamp));
  }
  const spaced = bundle(); Object.assign(spaced.rows[0].values, complete, {reviewed_at: '2026-10-25 13:15:27'});
  assert.equal(API.create(spaced).completed('a'), false, 'pair validator requires T timestamp separator');
  spaced.kind = 'construction';
  assert.equal(API.create(spaced).completed('a'), true);
  for (const stamp of ['2026-10-25T13:15:27z', '0000-01-01', '2026-02-30T13:00:00Z', '2026-10-25T24:00:00Z', '2026-10-25T13:60:00Z', '2026-10-25T13:15:60Z', '2026-10-25T13:15:27+25:00', '2026-10-25nonsense']) assert.equal(API.dateValid(stamp), false, stamp);
});
test('canonical quoted CSV preserves unicode, commas, quotes, newlines and immutable rows', () => {
  const b = bundle(); b.rows[1].values.image_id = 'é,\n"石"';
  const m = API.create(b); m.setDraft('a', {...complete, observation: 'façade, "oui"\n石'});
  const csv = m.exportCSV();
  assert.ok(csv.startsWith('"image_id","identity","observation","reviewer","reviewed_at","confidence"\r\n'));
  assert.ok(csv.includes('"façade, ""oui""\n石"'));
  assert.ok(csv.includes('"é,\n""石"""'));
  assert.ok(csv.endsWith('"c","","","","",""\r\n'));
});
test('raw formula-looking immutable cells and optional source pins remain unchanged', () => {
  const b = bundle(); b.rows[0].values.image_id = '=SUM(1,2)';
  b.source_pins = {cohort: 'a'.repeat(64)};
  const m = API.create(b);
  assert.ok(m.exportCSV().includes('"=SUM(1,2)"'));
  assert.equal(m.values('a').image_id, '=SUM(1,2)');
  assert.deepEqual(m.data.source_pins, b.source_pins);
  assert.deepEqual(m.exportDrafts().rows, []);
});
test('baseline source locks apply even to partially reviewed rows', () => {
  const b = bundle(); b.rows[0].values.observation = 'Source work';
  const m = API.create(b);
  assert.equal(m.locked('a'), true);
  assert.throws(() => m.setDraft('a', {reviewer: 'Override'}), /read-only/);
  assert.throws(() => m.importDrafts(backup(m, [{key: 'a', fields: {identity: 'same'}}])), /locked/);
  assert.ok(m.exportCSV().includes('Source work'));
  assert.throws(() => { m.data.rows[0].values.observation = 'Override'; }, TypeError);
  assert.equal(b.rows[0].values.observation, 'Source work');
});
test('stable-key navigation remains correctly attributed when completed row leaves filter', () => {
  const m = API.create(bundle());
  m.setDraft('b', complete);
  assert.deepEqual(m.keys(true), ['a', 'c']);
  assert.equal(m.navigate('b', 1, true), 'c');
  assert.equal(m.navigate('b', -1, true), 'a');
  m.setDraft('c', {observation: 'Only C'});
  assert.equal(m.values('a').observation, '');
  assert.equal(m.navigate('c', 1, true), 'a');
});
test('empty and all-decided queues have no filtered navigation target', () => {
  const b = bundle(); b.rows = [];
  const empty = API.create(b);
  assert.equal(empty.navigate(null, 1, true), null);
  assert.deepEqual(empty.keys(), []);
  const m = API.create(bundle()); m.keys().forEach(k => m.setDraft(k, complete));
  assert.deepEqual(m.keys(true), []);
  assert.equal(m.navigate('a', 1, true), null);
});
test('imports reject schema, stale provenance, duplicates and unknown/immutable fields atomically', () => {
  const m = API.create(bundle()); m.setDraft('a', {observation: 'Keep me'});
  const before = JSON.stringify(m.exportDrafts());
  const valid = backup(m, [{key: 'c', fields: {observation: 'New note'}}]);
  const bad = [
    {...valid, schema: 'old'}, {...valid, cohort_id: 'dead'}, {...valid, baseline_sha256: 'e'.repeat(64)},
    {...valid, extra: true}, backup(m, [{key: 'unknown', fields: {}}]),
    backup(m, [{key: 'b', fields: {image_id: 'x'}}]), backup(m, [{key: 'b', fields: {identity: 'positive'}}]),
    backup(m, [{key: 'b', fields: {reviewer: 3}}]),
    backup(m, [{key: 'b', fields: {}}, {key: 'b', fields: {}}]),
    backup(m, [{key: 'c', fields: {observation: 'New note'}}, {key: 'a', fields: {observation: 'Conflict'}}]),
    backup(m, [{key: 'a', fields: {observation: ''}}])
  ];
  for (const payload of bad) {
    assert.throws(() => m.importDrafts(payload));
    assert.equal(JSON.stringify(m.exportDrafts()), before);
  }
  m.importDrafts(valid); assert.equal(m.values('c').observation, 'New note');
  m.importDrafts(valid); assert.equal(m.values('a').observation, 'Keep me');
  m.importDrafts(backup(m, [{key: 'a', fields: {reviewer: 'New reviewer'}}]));
  assert.equal(m.values('a').reviewer, 'New reviewer');
});
test('storage is scoped, partial drafts reload, failed recovery never overwrites history', async () => {
  const m = API.create(bundle()), store = new Map();
  const storage = {getItem: k => store.get(k) ?? null, setItem: (k, v) => store.set(k, v)};
  const locks = lockManager();
  const local = API.connectStorage(m, storage, '', locks);
  m.setDraft('a', {observation: 'Partial'}); assert.equal(await local.save(), true);
  const n = API.create(bundle()); API.connectStorage(n, storage, '', locks);
  assert.equal(n.values('a').observation, 'Partial');
  const b = bundle(); b.baseline_sha256 = 'e'.repeat(64);
  assert.notEqual(API.create(b).storageKey, m.storageKey);
  b.cohort_id = 'dead'; assert.notEqual(API.create(b).storageKey, m.storageKey);
  for (const content of ['corrupt JSON', JSON.stringify({...m.exportDrafts(), cohort_id: 'dead'})]) {
    store.set(m.storageKey, content);
    const recovered = API.connectStorage(API.create(bundle()), storage, '', locks);
    assert.equal(recovered.writable, false); assert.ok(recovered.warning);
    assert.equal(recovered.recoveryData, content);
    assert.equal(await recovered.save(), false); assert.equal(store.get(m.storageKey), content);
  }
  const unavailable = API.connectStorage(m, {getItem() { return null; }, setItem() { throw Error('Quota'); }}, '', locks);
  assert.equal(await unavailable.save(), false); assert.equal(unavailable.writable, false);
  assert.ok(unavailable.warning.includes('JSON backup'));
  assert.doesNotThrow(() => JSON.stringify(m.exportDrafts()));
});
test('concurrent tabs refuse stale writes for disjoint and conflicting edits', async () => {
  for (const sameRow of [false, true]) {
    const store = new Map(), locks = lockManager();
    const storage = {getItem: key => store.get(key) ?? null, setItem: (key, value) => store.set(key, value)};
    const a = API.create(bundle()), b = API.create(bundle());
    const first = API.connectStorage(a, storage, '/same-page', locks);
    const second = API.connectStorage(b, storage, '/same-page', locks);
    a.setDraft('a', {observation: 'First tab saved work'});
    b.setDraft(sameRow ? 'a' : 'b', {observation: 'Second tab retained work'});
    const results = await Promise.all([first.save(), second.save()]);
    assert.deepEqual(results, [true, false]);
    const stored = [...store.values()][0];
    assert.equal(JSON.parse(stored).rows[0].fields.observation, 'First tab saved work');
    assert.equal(b.values(sameRow ? 'a' : 'b').observation, 'Second tab retained work');
    assert.equal(second.recoveryData, stored);
    assert.match(second.warning, /Another tab/);
    assert.equal(second.writable, false);
  }
});
test('without cross-tab locking new work stays in memory and old storage is untouched', async () => {
  let writes = 0;
  const model = API.create(bundle());
  const local = API.connectStorage(model, {getItem: () => null, setItem() { writes++; }});
  model.setDraft('a', {observation: 'Memory only'});
  assert.equal(await local.save(), false);
  assert.equal(writes, 0);
  assert.match(local.warning, /Coordinated local storage unavailable/);
  assert.equal(model.exportDrafts().rows[0].fields.observation, 'Memory only');
});
test('different review pages never silently share identical-cohort drafts', async () => {
  const store = new Map();
  const storage = {getItem: key => store.get(key) ?? null, setItem: (key, value) => store.set(key, value)};
  const first = API.create(bundle());
  const locks = lockManager();
  const local = API.connectStorage(first, storage, '/reviewer-one/workbench.html', locks);
  first.setDraft('a', {observation: 'First reviewer context'}); await local.save();
  const second = API.create(bundle());
  API.connectStorage(second, storage, '/reviewer-two/workbench.html', locks);
  assert.equal(second.values('a').observation, '');
  const restored = API.create(bundle());
  API.connectStorage(restored, storage, '/reviewer-one/workbench.html', locks);
  assert.equal(restored.values('a').observation, 'First reviewer context');
});
test('construction aliases and browser global export work', () => {
  const b = bundle(); b.kind = 'construction'; b.decision_field = 'applicability';
  b.fields = b.fields.map(f => f === 'identity' ? 'applicability' : f === 'observation' ? 'evidence' : f);
  b.editable = b.fields.slice(1); b.decisions = ['applicable', 'not_applicable', 'uncertain'];
  b.rows.forEach(r => {r.values.applicability = ''; r.values.evidence = ''; delete r.values.identity; delete r.values.observation;});
  const m = API.create(b); m.setDraft('a', {applicability: 'uncertain', evidence: 'Human note', reviewer: 'H', reviewed_at: '2026-10-25', confidence: 'low'});
  assert.equal(m.completed('a'), true);
  const context = {}; vm.runInNewContext(fs.readFileSync(path.join(dir, 'review_workbench_model.js'), 'utf8'), context);
  assert.equal(typeof context.ReviewWorkbenchModel.create, 'function');
});

// Minimal DOM VM: no browser or third-party packages required.
function uiHarness(b = bundle(), broken = false, storedRaw = null, locks = lockManager()) {
  class Element {
    constructor() { this.children = []; this.listeners = {}; this.value = ''; this.checked = false; this.disabled = false; this.textContent = ''; this.files = []; }
    appendChild(child) { this.children.push(child); return child; }
    append(...children) { this.children.push(...children); }
    replaceChildren() { this.children = []; }
    addEventListener(name, fn) { this.listeners[name] = fn; }
    fire(name) { if (this.listeners[name]) return this.listeners[name]({}); }
    click() {}
    set innerHTML(_) { throw Error('Unsafe HTML'); }
  }
  const ids = ['reviewData', 'status', 'hideCompleted', 'caseSelect', 'progress', 'images', 'context', 'fields', 'previous', 'next', 'saveNext', 'caseTitle', 'globalReviewer', 'exportJSON', 'exportRecovery', 'importJSON', 'exportCSV'];
  const elements = Object.fromEntries(ids.map(id => [id, new Element()]));
  elements.reviewData.textContent = JSON.stringify(b);
  const store = new Map(), events = {}, downloads = [];
  const context = {ReviewWorkbenchModel: API, document: {getElementById: id => elements[id], createElement: () => new Element()},
    window: {navigator: {locks}, localStorage: {getItem(key) { if (broken) throw Error('Denied'); return store.has(key) ? store.get(key) : storedRaw; }, setItem(k, v) {store.set(k, v);}}, addEventListener: (name, fn) => {events[name] = fn;}},
    URL: {createObjectURL(blob) { downloads.push(blob); return 'blob:offline'; }, revokeObjectURL() {}}, Blob, setTimeout: fn => fn(), console};
  vm.runInNewContext(fs.readFileSync(path.join(dir, 'review_workbench_ui.js'), 'utf8'), context);
  const inputs = () => Object.fromEntries(elements.fields.children.map(label => [label.children[0].name, label.children[0]]));
  return {elements, inputs, store, events, downloads};
}
test('UI autosaves partial drafts with stable IDs, no defaults; commit alone fills date/reviewer', async () => {
  const h = uiHarness(), e = h.elements;
  assert.equal(h.inputs().identity.value, ''); assert.equal(h.inputs().confidence.value, '');
  e.globalReviewer.value = 'Explicit Human';
  h.inputs().observation.value = '<script>石</script>'; await h.inputs().observation.fire('input');
  const saved = () => JSON.parse([...h.store.values()][0]);
  assert.equal(saved().rows[0].key, 'a');
  assert.equal(saved().rows[0].fields.reviewer, undefined);
  await e.saveNext.fire('click');
  assert.equal(saved().rows[0].fields.reviewer, undefined);
  assert.equal(saved().rows[0].fields.reviewed_at, undefined);
  assert.equal(saved().rows[0].fields.identity, undefined);
  assert.equal(e.caseSelect.value, 'a');
  h.inputs().identity.value = 'different'; await h.inputs().identity.fire('input');
  h.inputs().confidence.value = 'low'; await h.inputs().confidence.fire('input');
  e.hideCompleted.checked = true; await e.saveNext.fire('click');
  assert.equal(saved().rows[0].fields.reviewer, 'Explicit Human');
  assert.match(saved().rows[0].fields.reviewed_at, /^\d{4}-\d{2}-\d{2}$/);
  assert.equal(e.caseSelect.value, 'b');
  h.inputs().observation.value = 'B only'; await h.inputs().observation.fire('input');
  assert.equal(saved().rows.find(r => r.key === 'b').fields.observation, 'B only');
  assert.equal(saved().rows.find(r => r.key === 'a').fields.observation, '<script>石</script>');
});
test('pending storage warns on unload and delayed save never advances a newly selected case', async () => {
  const seed = API.create(bundle());
  seed.setDraft('a', {identity: 'uncertain', observation: 'A note', confidence: 'low'});
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const h = uiHarness(bundle(), false, JSON.stringify(seed.exportDrafts()), {
    async request(_key, _options, callback) { await gate; return callback(); }
  });
  h.elements.globalReviewer.value = 'Explicit Human';
  const saving = h.elements.saveNext.fire('click');
  let prevented = false;
  h.events.beforeunload({preventDefault() { prevented = true; }});
  assert.equal(prevented, true);
  h.elements.next.fire('click');
  assert.equal(h.elements.caseSelect.value, 'b');
  release(); await saving;
  assert.equal(h.elements.caseSelect.value, 'b');
  const saved = JSON.parse([...h.store.values()][0]);
  assert.equal(saved.rows[0].key, 'a');
  assert.equal(saved.rows[0].fields.reviewer, 'Explicit Human');
});
test('UI accepts pinned parent-relative images, rejects unsafe sources and shows timestamps', () => {
  const b = bundle();
  const allowed = ['../../monument-inbox/ID/photo.jpg', '../images/photo with spaces.jpg', 'image.jpg', 'data:image/png;base64,YQ=='];
  const blocked = ['/absolute.jpg', '//remote.invalid/photo.jpg', 'https://remote.invalid/photo.jpg', 'photo.jpg?query', 'photo.jpg#fragment', '..\\\\image.jpg', 'bad\u0001image.jpg', 'data:image/svg+xml;base64,YQ==', ' //remote.invalid/photo.jpg'];
  b.rows[0].images = [...allowed, ...blocked].map(src => ({src, caption: '<Human caption>'}));
  Object.assign(b.rows[0].values, complete, {reviewed_at: '2026-10-25T13:15:27Z'});
  const h = uiHarness(b);
  const images = h.elements.images.children.map(figure => figure.children[0]);
  allowed.forEach((src, i) => assert.equal(images[i].src, src));
  blocked.forEach((src, i) => assert.equal(images[i + allowed.length].src, undefined, src));
  assert.equal(h.inputs().reviewed_at.type, 'text');
  assert.equal(h.inputs().reviewed_at.value, '2026-10-25T13:15:27Z');
  assert.equal(h.inputs().reviewed_at.disabled, true);
  assert.deepEqual(h.inputs().confidence.children.map(option => option.value), ['', 'high', 'medium', 'low']);
});
test('UI storage failure warns before unload, retains export fallback and empty queues', async () => {
  const h = uiHarness(bundle(), true);
  assert.match(h.elements.status.textContent, /recovery failed/);
  h.inputs().observation.value = 'Retain'; await h.inputs().observation.fire('input');
  let prevented = false;
  const event = {preventDefault() {prevented = true;}};
  h.events.beforeunload(event); assert.equal(prevented, true);
  h.elements.exportJSON.fire('click'); assert.equal(h.downloads.length, 1);
  const b = bundle(); b.rows = [];
  const empty = uiHarness(b); assert.equal(empty.elements.next.disabled, true);
});
test('UI exports raw failed-recovery data separately from new partial drafts', async () => {
  const raw = '{broken, recoverable: notes}';
  const h = uiHarness(bundle(), false, raw);
  assert.equal(h.elements.exportRecovery.hidden, false);
  h.elements.exportRecovery.fire('click');
  assert.equal(await h.downloads[0].text(), raw);
  h.inputs().observation.value = 'New partial work'; await h.inputs().observation.fire('input');
  assert.equal(h.store.size, 0, 'failed original recovery is never overwritten');
  h.elements.exportJSON.fire('click');
  assert.equal(JSON.parse(await h.downloads[1].text()).rows[0].fields.observation, 'New partial work');
});
test('template contains each safe embedding placeholder and required IDs exactly once', () => {
  const html = fs.readFileSync(path.join(dir, 'review_workbench.html'), 'utf8');
  for (const token of ['__REVIEW_DATA__', '__REVIEW_MODEL__', '__REVIEW_UI__']) assert.equal(html.split(token).length - 1, 1);
  assert.match(html, /<script type="application\/json" id="reviewData">/);
  const h = uiHarness();
  for (const id of Object.keys(h.elements)) assert.equal(html.split('id="' + id + '"').length - 1, 1);
});
