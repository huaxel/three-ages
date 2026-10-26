#!/usr/bin/env node
"use strict";
// Offline DOM harness: execute the shipped inline script, including its handlers.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

async function workbench(hide = true, labelled = []) {
  const elements = new Map(), listeners = {}, sessions = [];
  function element(id = "") {
    if (id && elements.has(id)) return elements.get(id);
    const e = {
      value: "", checked: false, children: [],
      classList: { add() {}, remove() {} },
      appendChild(child) { this.children.push(child); },
      click() { this.onclick(); },
      focus() {},
      set innerHTML(html) {
        this.html = html;
        this.children = [];
        if (id === "workspace") {
          // A browser replaces the form on every render. Model its values so a
          // navigation bug cannot pass merely by retaining the previous form.
          for (const key of ["eraVal", "phase", "confidence", "depicts", "evidence", "eras"])
            elements.delete(key);
          for (const match of html.matchAll(/<input[^>]*id="([^"]+)"[^>]*value="([^"]*)"/g))
            element(match[1]).value = match[2];
          for (const match of html.matchAll(/<select id="([^"]+)">([\s\S]*?)<\/select>/g)) {
            const selected = match[2].match(/<option(?: value="([^"]+)")? selected>([^<]+)/);
            element(match[1]).value = selected ? selected[1] || selected[2] : "";
          }
          const evidence = html.match(/<textarea id="evidence">([\s\S]*?)<\/textarea>/);
          if (evidence) element("evidence").value = evidence[1];
        }
      },
      get innerHTML() { return this.html || ""; },
    };
    if (id) elements.set(id, e);
    return e;
  }
  element("hideDone").checked = hide;
  const records = ["a", "b", "c", "d"].map(building_id => ({
    building_id, identity_name: building_id, labelled_era: labelled.includes(building_id) ? "pre-1850" : "",
    notice_excerpt: `Evidence ${building_id}`, photos: [], photo_count: 0,
  }));
  const context = vm.createContext({
    document: { getElementById: element, createElement: () => element(),
      addEventListener: (type, fn) => { listeners[type] = fn; } },
    localStorage: { getItem: () => "Reviewer", setItem() {} },
    Blob: class { constructor(parts) { this.parts = parts; } },
    URL: { createObjectURL(blob) { sessions.push(JSON.parse(blob.parts.join(''))); return 'blob:fixture'; } },
    fetch: async () => ({ ok: true, json: async () => ({records, eras: ["pre-1850"]}) }),
  });
  const html = fs.readFileSync(path.join(__dirname, "three-ages/taskb_review.html"), "utf8");
  vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
  await new Promise(resolve => setImmediate(resolve));
  const current = () => vm.runInContext("rec()?.building_id", context);
  const pick = () => element("eras").children[0].click();
  const key = key => listeners.keydown({ key });
  const select = id => element("caseList").children.find(b => b.innerHTML.includes(`<strong>${id}</strong>`)).click();
  const draft = id => vm.runInContext(`drafts.get('${id}')`, context);
  return {element, current, pick, key, select, draft, sessions};
}

(async () => {
  // Default hide-decided flow must visit every row, then clear the queue.
  const w = await workbench();
  assert.equal(w.element('depicts').value, '', 'unreviewed applicability must remain unknown');
  w.element("saveNext").click();
  assert.equal(w.current(), "a", "empty era must not advance");
  for (const [index, id] of ["a", "b", "c", "d"].entries()) {
    assert.equal(w.current(), id);
    w.pick();
    if (index % 2) w.key("s"); else w.element("saveNext").click();
    assert.equal(w.draft(id).era, "pre-1850");
    assert.equal(w.draft(id).evidence, `Evidence ${id}`);
  }
  assert.equal(w.current(), undefined);
  assert.match(w.element("workspace").innerHTML, /Queue clear/);
  w.key("ArrowRight"); // Empty queues are safe.
  w.element('exportSession').click();
  assert.equal(w.sessions[0].records.length, 4);
  assert.ok(w.sessions[0].records.every(r => r.depicts_building === ''), 'export cannot invent yes');

  // Both arrow buttons and keyboard arrows use the pre-save destination.
  for (const hide of [true, false]) {
    for (const [action, start, expected] of [
      [w => w.element("nextBtn").click(), "b", "c"],
      [w => w.element("prevBtn").click(), "c", "b"],
      [w => w.key("ArrowRight"), "b", "c"],
      [w => w.key("ArrowLeft"), "c", "b"],
      [w => w.key("ArrowRight"), "d", "a"],
      [w => w.key("ArrowLeft"), "a", "d"],
      [w => w.select("d"), "a", "d"],
      [w => w.select("a"), "c", "a"],
      [w => w.element("saveNext").click(), "b", "c"],
    ]) {
      const w = await workbench(hide);
      w.select(start);
      w.pick();
      action(w);
      assert.equal(w.current(), expected, `navigation from ${start}, hide=${hide}`);
      assert.equal(w.draft(start).era, "pre-1850");
      assert.equal(w.element("eraVal").value, "", "destination form belongs to destination");
    }
  }
  const prelabelled = await workbench(true, ["b", "d"]);
  prelabelled.pick(); prelabelled.key("s");
  assert.equal(prelabelled.current(), "c");
  prelabelled.pick(); prelabelled.key("s");
  assert.equal(prelabelled.current(), undefined);

  const toggle = await workbench(false);
  toggle.select("a"); toggle.pick(); toggle.select("c");
  toggle.element("hideDone").checked = true;
  toggle.element("hideDone").onchange();
  assert.equal(toggle.current(), "c", "filter toggles preserve current identity");
  console.log("Task B review navigation passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
