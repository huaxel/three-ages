#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = __dirname;

function elementStore(defaultValues = {}) {
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) {
      elements.set(id, {
        id,
        value: defaultValues[id] || "",
        textContent: "",
        innerHTML: "",
        hidden: true,
        href: "",
        addEventListener() {},
        setAttribute() {},
        classList: { toggle() {} },
      });
    }
    return elements.get(id);
  }
  return { elements, element };
}

function makeQuerySelectorAll(element) {
  const cache = new Map();
  function buildFakes(html, attribute) {
    const pattern = new RegExp(`data-${attribute}="([^"]+)"`, "g");
    const fakes = [];
    let match;
    while ((match = pattern.exec(html)) !== null) {
      const listeners = {};
      fakes.push({
        dataset: attribute === "id" ? { id: match[1] } : { sourceId: match[1] },
        attributes: {},
        setAttribute(name, value) { this.attributes[name] = value; },
        classList: { toggle() {} },
        addEventListener(type, handler) { (listeners[type] ||= []).push(handler); },
        click() { (listeners.click || []).forEach(handler => handler()); },
      });
    }
    return fakes;
  }
  function buttonsFrom(containerId, attribute) {
    const html = element(containerId).innerHTML;
    const key = `${containerId}\n${html}`;
    if (!cache.has(key)) cache.set(key, buildFakes(html, attribute));
    return cache.get(key);
  }
  return selector => {
    if (selector === "#list .building") return buttonsFrom("list", "id");
    if (selector === ".source-building") return buttonsFrom("sourceList", "source-id");
    return [];
  };
}

async function loadPrototype(name, defaultValues = {}) {
  const html = fs.readFileSync(path.join(ROOT, name, "index.html"), "utf8");
  const match = html.match(/<script>([\s\S]*?)<\/script>/);
  if (!match) throw new Error(`${name}: inline script not found`);
  const { element } = elementStore(defaultValues);
  const document = {
    getElementById: element,
    querySelectorAll: makeQuerySelectorAll(element),
  };
  const fetch = async relative => ({
    json: async () => JSON.parse(fs.readFileSync(path.join(ROOT, name, relative), "utf8")),
  });
  const context = {
    document,
    fetch,
    console,
    Map,
    Math,
    Number,
    String,
    Object,
    Promise,
    encodeURIComponent,
    setTimeout,
  };
  vm.createContext(context);
  vm.runInContext(match[1], context, { filename: `${name}/index.html` });
  await new Promise(resolve => setTimeout(resolve, 100));
  return { context, element };
}

function requireIncludes(value, expected, label) {
  if (!value.includes(expected)) {
    throw new Error(`${label}: missing ${JSON.stringify(expected)}`);
  }
}

async function testThreeAges() {
  const { context, element } = await loadPrototype("three-ages");
  const source = element("source").textContent;
  requireIncludes(source, "24 aligned case crops", "Three Ages source summary");
  requireIncludes(source, "CC BY 4.0", "Three Ages dataset licence");
  requireIncludes(source, "Behind Brussels, Google Maps", "Three Ages dataset attribution");
  requireIncludes(source, "0 completed register decisions", "Three Ages source summary");
  requireIncludes(element("access").innerHTML, "text quotations and reused information permitted with explicit source attribution", "Three Ages heritage text terms");
  requireIncludes(element("access").innerHTML, "CC0 1.0 for structured data", "Three Ages Wikidata terms");
  requireIncludes(element("access").innerHTML, "Wikidata contributors", "Three Ages Wikidata acknowledgement");
  requireIncludes(element("access").innerHTML, "EmDee, via Wikimedia Commons", "Three Ages image attribution");
  for (const id of ["imageReviewLink", "structuralReviewLink", "registerReviewLink"]) {
    if (element(id).hidden) throw new Error(`Three Ages: ${id} remains hidden`);
  }
  context.show("024");
  const content = element("content").innerHTML;
  for (const expected of [
    "Identity check · pending reviewer confirmation",
    "wikimedia-commons 2043-0177/0",
    "british-library-flickr-commons 11271682895",
    "024-bruciel-grand-place-1935.png",
    "024-bruciel-grand-place-1996.png",
    "024-urbisgrid-grand-place-2022.png",
    "No completed register-semantics decision",
    "No completed case-level structural review",
  ]) requireIncludes(content, expected, "Three Ages case rendering");
  context.show("022");
  const josephAnne = element("content").innerHTML;
  for (const expected of [
    "kik-irpa-A102887.jpg",
    "kik-irpa-T001802.jpg",
    "kik-irpa-A133254.jpg",
    "022-bruciel-grand-place-1971.png",
  ]) requireIncludes(josephAnne, expected, "Three Ages second-epoch rendering");
  context.show("005");
  requireIncludes(element("content").innerHTML, "kik-irpa-E049753.jpg", "Three Ages 1890 ensemble rendering");
  for (const [caseId, preview] of [["005", "kik-irpa-T001817.jpg"], ["009", "kik-irpa-T001820.jpg"], ["023", "kik-irpa-T001803.jpg"], ["026", "kik-irpa-T001805.jpg"]]) {
    context.show(caseId);
    requireIncludes(element("content").innerHTML, preview, `Three Ages 1969 rendering for ${caseId}`);
  }
  const buildings = JSON.parse(fs.readFileSync(path.join(ROOT, "three-ages/data/grand-place-buildings.json"), "utf8"));
  const nameFor = id => (buildings.records.find(record => record.id === id) || {}).name || id;
  const buildingButtons = context.document.querySelectorAll("#list .building");
  if (buildingButtons.length !== 6) throw new Error(`Three Ages: expected 6 case buttons, found ${buildingButtons.length}`);
  const other = buildingButtons.find(button => button.dataset.id !== "024");
  other.click();
  requireIncludes(element("content").innerHTML, nameFor(other.dataset.id), "Three Ages case switching");
  if (other.attributes["aria-pressed"] !== true) throw new Error("Three Ages: clicked building did not become pressed");
  if (!buildingButtons.filter(button => button !== other).every(button => button.attributes["aria-pressed"] === false)) {
    throw new Error("Three Ages: unclicked buildings did not become unpressed");
  }
  const sourceButtons = context.document.querySelectorAll(".source-building");
  sourceButtons[0].click();
  requireIncludes(element("sourceDetail").innerHTML, nameFor(sourceButtons[0].dataset.sourceId), "Three Ages source preview");
}

(async () => {
  await testThreeAges();
  console.log("Three Ages UI smoke test passed");
})().catch(error => {
  console.error(error.stack || error);
  process.exit(1);
});
