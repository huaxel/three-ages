(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const model = ReviewWorkbenchModel.create(JSON.parse($('reviewData').textContent));
  let storage;
  try { storage = window.localStorage; } catch (e) { storage = {getItem() { throw e; }}; }
  let locks = null;
  try { locks = window.navigator && window.navigator.locks; } catch (_) { /* Memory-only fallback. */ }
  const local = ReviewWorkbenchModel.connectStorage(model, storage,
    window.location ? window.location.pathname : '', locks);
  $('exportRecovery').hidden = local.recoveryData === null;
  $('exportRecovery').addEventListener('click', () => {
    if (local.recoveryData !== null) download(local.recoveryData, 'text/plain;charset=utf-8', '-stored-recovery.txt');
  });
  let current = model.keys()[0] || null, dirty = false, editRevision = 0;
  const inputs = new Map();
  function status(message) {
    $('exportRecovery').hidden = local.recoveryData === null;
    $('status').textContent = [message, local.warning].filter(Boolean).join(' ');
  }
  async function persist() {
    const revision = ++editRevision;
    dirty = true;
    const saved = await local.save();
    if (revision === editRevision) {
      if (saved) dirty = false;
      status(saved ? 'Draft saved locally.' : 'Draft retained in memory; download a JSON backup.');
    }
    return saved;
  }
  function download(content, mime, suffix) {
    const url = URL.createObjectURL(new Blob([content], {type: mime}));
    const a = document.createElement('a');
    a.href = url; a.download = model.data.kind + '-' + model.data.cohort_id + suffix;
    a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function render() {
    const visible = model.keys($('hideCompleted').checked);
    $('caseSelect').replaceChildren();
    for (const key of visible) {
      const option = document.createElement('option'); option.value = key; option.textContent = key;
      $('caseSelect').appendChild(option);
    }
    // Keep the currently edited case visible even if autosave completes it.
    if (current && !visible.includes(current)) {
      const option = document.createElement('option'); option.value = current; option.textContent = current + ' (completed)';
      $('caseSelect').appendChild(option);
    }
    $('caseSelect').value = current || '';
    $('progress').textContent = model.keys().filter(k => model.completed(k)).length + ' / ' + model.keys().length + ' complete';
    $('images').replaceChildren(); $('context').replaceChildren(); $('fields').replaceChildren(); inputs.clear();
    for (const id of ['previous', 'next', 'saveNext', 'caseSelect']) $(id).disabled = !current;
    if (!current) { $('caseTitle').textContent = visible.length ? 'Select a case' : 'No cases remaining'; return; }
    const row = model.data.rows.find(r => r.key === current), values = model.values(current);
    $('caseTitle').textContent = current + (model.locked(current) ? ' — source review locked' : '');
    for (const item of row.images || []) {
      const figure = document.createElement('figure'), img = document.createElement('img'), caption = document.createElement('figcaption');
      // Python pins/constrains baked paths; parent segments locate sibling image roots.
      // Reject active, remote, absolute and browser-normalized backslash/control paths.
      if (/^data:image\/(?:png|jpeg|jpg|webp|gif|bmp);base64,[a-z0-9+/=]+$/i.test(item.src || '') ||
          (/^(?![\/\s])[^:?#\\\x00-\x1f\x7f]+$/.test(item.src || ''))) img.src = item.src;
      else img.alt = 'Image unavailable: unsafe or remote source';
      img.alt = img.alt || item.caption || 'Review image';
      caption.textContent = item.caption || ''; figure.append(img, caption); $('images').appendChild(figure);
    }
    for (const item of row.context || []) {
      const dt = document.createElement('dt'), dd = document.createElement('dd');
      dt.textContent = item.label; dd.textContent = item.value; $('context').append(dt, dd);
    }
    for (const field of model.data.editable) {
      const label = document.createElement('label'); label.textContent = field;
      let input;
      if (field === model.data.decision_field || field === 'confidence') {
        input = document.createElement('select');
        const choices = ['', ...(field === 'confidence' ? ['high', 'medium', 'low'] : model.data.decisions)];
        if (model.locked(current) && !choices.includes(values[field])) choices.push(values[field]);
        for (const value of choices) {
          const option = document.createElement('option'); option.value = value; option.textContent = value || (field === 'confidence' ? '— no confidence —' : '— no decision —'); input.appendChild(option);
        }
      } else {
        input = document.createElement(/^(evidence|observation)$/.test(field) ? 'textarea' : 'input');
        if (/^(date|review_date|reviewed_at)$/.test(field)) input.type = values[field].length > 10 ? 'text' : 'date';
      }
      input.value = values[field]; input.disabled = model.locked(current); input.name = field;
      // Capture key, not visible index: filtering can never redirect an input event.
      const key = current;
      input.addEventListener('input', async () => {
        try { model.setDraft(key, {[field]: input.value}); await persist(); $('progress').textContent = model.keys().filter(k => model.completed(k)).length + ' / ' + model.keys().length + ' complete'; }
        catch (e) { status(e.message); }
      });
      inputs.set(field, input); label.appendChild(input); $('fields').appendChild(label);
    }
  }
  function move(direction) {
    current = model.navigate(current, direction, $('hideCompleted').checked); render();
  }
  $('previous').addEventListener('click', () => move(-1));
  $('next').addEventListener('click', () => move(1));
  $('caseSelect').addEventListener('change', () => { current = $('caseSelect').value || null; render(); });
  $('hideCompleted').addEventListener('change', () => {
    if (!current || ($('hideCompleted').checked && model.completed(current))) current = model.keys($('hideCompleted').checked)[0] || null;
    render();
  });
  $('saveNext').addEventListener('click', async () => {
    const key = current;
    if (!key) return;
    try {
      if (!model.locked(key)) {
        const values = model.values(key), patch = {};
        if (!model.data.decisions.includes(values[model.data.decision_field])) {
          status('Choose a decision before committing; no review metadata was generated.');
          return;
        }
        if (model.data.editable.includes('reviewer') && !values.reviewer.trim() && $('globalReviewer').value.trim()) patch.reviewer = $('globalReviewer').value.trim();
        const field = model.data.editable.find(f => /^(date|review_date|reviewed_at)$/.test(f));
        if (field && !values[field].trim()) {
          const now = new Date();
          patch[field] = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
        }
        model.setDraft(key, patch); await persist();
      }
      if (current !== key) return; // A delayed save cannot move a newly selected case.
      const missing = model.incomplete(key);
      if (missing.length) { render(); status('Incomplete review: ' + missing.join(', ')); return; }
      move(1); status('Review complete.');
    } catch (e) { status(e.message); }
  });
  $('exportJSON').addEventListener('click', () => {
    download(JSON.stringify(model.exportDrafts(), null, 2), 'application/json;charset=utf-8', '-drafts.json');
    status('JSON backup downloaded.');
  });
  $('importJSON').addEventListener('change', async () => {
    const file = $('importJSON').files[0]; if (!file) return;
    try { model.importDrafts(await file.text()); await persist(); render(); status('Backup merged without conflicts.'); }
    catch (e) { status('Import refused: ' + e.message); }
    $('importJSON').value = '';
  });
  $('exportCSV').addEventListener('click', () => {
    try { download(model.exportCSV(), 'text/csv;charset=utf-8', '-reviews.csv'); status('CSV downloaded; source files unchanged.'); }
    catch (e) { status('CSV export refused: ' + e.message); }
  });
  window.addEventListener('beforeunload', event => {
    if (dirty) { event.preventDefault(); event.returnValue = ''; }
  });
  render(); status('No labels are generated. Partial drafts are retained; export JSON backups.');
})();
