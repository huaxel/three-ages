/* Dependency-free, deliberately label-free review state.
 * CommonJS require(path) or browser global ReviewWorkbenchModel:
 *   const model = ReviewWorkbenchModel.create(bundle);
 *   model.setDraft(rowKey, {identity: 'ambiguous', evidence: 'Human note',
 *     reviewer: 'Human', reviewed_at: '2026-10-25', confidence: 'low'});
 *   const csv = model.exportCSV(); // all rows/columns; throws on incomplete drafts
 *   const backup = model.exportDrafts(); // JSON-safe object, editable fields only
 *   model.importDrafts(backup); // also accepts JSON text; atomic conflict refusal
 * keys(hideCompleted=false) returns stable keys; navigate(key, +/-1, hideCompleted)
 * returns a stable key or null. values(key) returns an independent merged object.
 * locked(key), completed(key), incomplete(key) expose validation/read-only state.
 * data is the deeply frozen input clone; optional bundle source_pins are retained.
 * Draft format: {schema:'image-review-workbench-drafts/1', cohort_id,
 *   baseline_sha256, rows:[{key, fields:{editableField:string}}]}.
 * connectStorage(model, storage, pageScope='', locks=null) recovers once, then offers async save(), writable,
 * warning. Recovery/write failure permanently blocks further key writes for the
 * session. It never clears keys; model and JSON import/export remain usable.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.ReviewWorkbenchModel = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const SCHEMA = 'image-review-workbench-drafts/1';
  const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
  const object = o => o !== null && typeof o === 'object' && !Array.isArray(o);
  const nonblank = s => s.trim() !== '';
  function freeze(value) {
    if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value); }
    return value;
  }
  function fail(message) { throw new Error(message); }
  function dateValid(s) {
    if (typeof s !== 'string') return false;
    // Validate the calendar component independently: Date.parse normalizes Feb 30.
    const match = /^(\d{4}-\d{2}-\d{2})(?:[Tt ](\d{2}):(\d{2})(?::(\d{2})(?:[.,]\d+)?)?(?:Z|([+-])(\d{2}):?(\d{2}))?)?$/.exec(s);
    if (!match || Number(match[1].slice(0, 4)) === 0) return false;
    const d = new Date(match[1] + 'T00:00:00Z');
    if (Number.isNaN(d.valueOf()) || d.toISOString().slice(0, 10) !== match[1]) return false;
    return match[2] === undefined || (Number(match[2]) < 24 && Number(match[3]) < 60 &&
      (match[4] === undefined || Number(match[4]) < 60) &&
      (match[5] === undefined || (Number(match[6]) < 24 && Number(match[7]) < 60)));
  }
  function create(bundle) {
    // Clone to prevent callers from mutating immutable source values later.
    const data = JSON.parse(JSON.stringify(bundle));
    if (!object(data) || data.schema !== 'image-review-workbench/1' || !['pair', 'construction'].includes(data.kind) ||
        !/^[a-f0-9]+$/i.test(data.cohort_id || '') || !/^[a-f0-9]{64}$/i.test(data.baseline_sha256 || '') ||
        !Array.isArray(data.fields) || !Array.isArray(data.editable) || !Array.isArray(data.rows) ||
        !Array.isArray(data.decisions)) fail('Invalid review bundle');
    for (const list of [data.fields, data.editable, data.decisions]) {
      if (list.some(x => typeof x !== 'string' || !x) || new Set(list).size !== list.length) fail('Invalid schema columns or decisions');
    }
    if (!data.editable.includes(data.decision_field) || !['identity', 'applicability'].includes(data.decision_field) ||
        data.editable.some(f => !data.fields.includes(f)) || data.decisions.includes('')) fail('Invalid editable schema');
    const rows = new Map();
    for (const row of data.rows) {
      if (!object(row) || typeof row.key !== 'string' || !row.key || rows.has(row.key) || !object(row.values) ||
          Object.keys(row.values).length !== data.fields.length || data.fields.some(f => !own(row.values, f) || typeof row.values[f] !== 'string')) fail('Invalid source row');
      rows.set(row.key, row);
    }
    freeze(data);
    let drafts = new Map();
    const rowFor = key => rows.get(key) || fail('Unknown row key');
    const locked = key => data.editable.some(f => nonblank(rowFor(key).values[f]));
    const values = key => ({...rowFor(key).values, ...(drafts.get(key) || {})});
    function validateFields(fields) {
      if (!object(fields) || Object.keys(fields).some(f => !data.editable.includes(f) || typeof fields[f] !== 'string')) fail('Unknown or immutable draft field');
      if (own(fields, data.decision_field) && fields[data.decision_field] !== '' && !data.decisions.includes(fields[data.decision_field])) fail('Unknown decision');
    }
    function setDraft(key, patch) {
      rowFor(key); validateFields(patch);
      if (locked(key)) fail('Source review is read-only');
      const next = {...(drafts.get(key) || {}), ...patch};
      // Canonicalize against the source so blank input does not create phantom reviews.
      for (const f of Object.keys(next)) if (next[f] === rowFor(key).values[f]) delete next[f];
      if (Object.keys(next).length) drafts.set(key, next); else drafts.delete(key);
    }
    function incomplete(key) {
      const v = values(key);
      const missing = [];
      if (!data.decisions.includes(v[data.decision_field])) missing.push(data.decision_field);
      const required = [data.editable.find(f => /^(evidence|observation)$/.test(f)),
        data.editable.find(f => f === 'reviewer'), data.editable.find(f => /^(reviewed_at|review_date|date)$/.test(f)),
        data.editable.find(f => f === 'confidence')];
      for (const f of required) if (!f || !nonblank(v[f])) missing.push(f || 'required review field');
      const dateField = required[2];
      if (dateField && nonblank(v[dateField]) && (!dateValid(v[dateField]) ||
          (data.kind === 'pair' && v[dateField].length > 10 && v[dateField][10] !== 'T'))) missing.push('ISO date or timestamp');
      const confidenceField = required[3];
      if (confidenceField && nonblank(v[confidenceField]) && !['high', 'medium', 'low'].includes(v[confidenceField])) missing.push('confidence (high/medium/low)');
      return missing;
    }
    const completed = key => incomplete(key).length === 0;
    const keys = (hideCompleted = false) => data.rows.filter(r => !hideCompleted || !completed(r.key)).map(r => r.key);
    function navigate(key, direction, hideCompleted = false) {
      const all = keys();
      if (!all.length) return null;
      const visible = new Set(keys(hideCompleted));
      let index = all.indexOf(key);
      if (index < 0) return keys(hideCompleted)[0] || null;
      for (let n = 1; n <= all.length; n++) {
        const candidate = all[(index + direction * n + all.length * n) % all.length];
        if (visible.has(candidate)) return candidate;
      }
      return null;
    }
    function exportDrafts() {
      return {schema: SCHEMA, cohort_id: data.cohort_id, baseline_sha256: data.baseline_sha256,
        rows: [...drafts].map(([key, fields]) => ({key, fields: {...fields}}))};
    }
    function importDrafts(payload) {
      const p = typeof payload === 'string' ? JSON.parse(payload) : payload;
      if (!object(p) || Object.keys(p).sort().join(',') !== 'baseline_sha256,cohort_id,rows,schema' ||
          p.schema !== SCHEMA || p.cohort_id !== data.cohort_id || p.baseline_sha256 !== data.baseline_sha256 || !Array.isArray(p.rows)) fail('Stale or invalid draft backup');
      const next = new Map(drafts), seen = new Set();
      for (const item of p.rows) {
        if (!object(item) || Object.keys(item).sort().join(',') !== 'fields,key' || typeof item.key !== 'string' || seen.has(item.key)) fail('Invalid or duplicate draft row');
        seen.add(item.key); rowFor(item.key); validateFields(item.fields);
        if (locked(item.key)) fail('Backup modifies a locked source review');
        const fields = Object.create(null);
        const existing = next.get(item.key);
        if (existing && Object.keys(item.fields).some(f => own(existing, f) && existing[f] !== item.fields[f])) fail('Draft conflict');
        for (const f of Object.keys(item.fields)) if (item.fields[f] !== rowFor(item.key).values[f]) fields[f] = item.fields[f];
        const merged = {...existing, ...fields};
        if (Object.keys(merged).length) next.set(item.key, merged);
      }
      drafts = next;
    }
    function exportCSV() {
      for (const key of drafts.keys()) if (!completed(key)) fail('Incomplete draft review: ' + key + ' (' + incomplete(key).join(', ') + ')');
      const quote = s => '"' + s.replace(/"/g, '""') + '"';
      return [data.fields, ...data.rows.map(r => data.fields.map(f => values(r.key)[f]))].map(cells => cells.map(quote).join(',')).join('\r\n') + '\r\n';
    }
    return {data, locked, values, setDraft, incomplete, completed, keys, navigate, exportDrafts, importDrafts, exportCSV,
      storageKey: 'image-review-workbench:' + data.cohort_id + ':' + data.baseline_sha256};
  }
  // A failed recovery blocks ALL writes for this session; never destroy recoverable history.
  function connectStorage(model, storage, pageScope = '', locks = null) {
    if (typeof pageScope !== 'string') fail('Invalid review page scope');
    const key = model.storageKey + (pageScope ? ':' + pageScope : '');
    let writable = true, warning = '', raw = null, recoveryData = null;
    try { raw = storage.getItem(key); if (raw !== null) model.importDrafts(raw); }
    catch (e) {
      writable = false;
      recoveryData = typeof raw === 'string' ? raw : null;
      warning = 'Local recovery failed; existing history preserved. Download stored recovery data when available; back up new drafts separately. ' + e.message;
    }
    if (!locks || typeof locks.request !== 'function') {
      writable = false;
      warning = warning || 'Coordinated local storage unavailable; new drafts stay in memory only. Export JSON backups before leaving.';
    }
    return {
      get warning() { return warning; },
      get recoveryData() { return recoveryData; },
      get writable() { return writable; },
      async save() {
        if (!writable) return false;
        try {
          return await locks.request(key, {mode: 'exclusive'}, () => {
            if (!writable) return false;
            const observed = storage.getItem(key);
            if (observed !== raw) {
              writable = false;
              recoveryData = typeof observed === 'string' ? observed : null;
              warning = 'Another tab changed saved drafts; stale save refused and stored work preserved. Export your local JSON backup, reload, then import it to merge explicitly.';
              return false;
            }
            const next = JSON.stringify(model.exportDrafts());
            storage.setItem(key, next);
            raw = next;
            return true;
          });
        } catch (e) {
          writable = false;
          warning = 'Local storage unavailable; export a JSON backup before leaving. ' + e.message;
          return false;
        }
      }
    };
  }
  return {create, connectStorage, dateValid, DRAFT_SCHEMA: SCHEMA};
});
