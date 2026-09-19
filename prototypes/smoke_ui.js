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

async function loadPrototype(name, defaultValues = {}) {
  const html = fs.readFileSync(path.join(ROOT, name, "index.html"), "utf8");
  const match = html.match(/<script>([\s\S]*?)<\/script>/);
  if (!match) throw new Error(`${name}: inline script not found`);
  const { element } = elementStore(defaultValues);
  const document = {
    getElementById: element,
    querySelectorAll() { return []; },
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
  requireIncludes(source, "18 aligned case crops", "Three Ages source summary");
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
}

(async () => {
  await testThreeAges();
  console.log("Three Ages UI smoke test passed");
})().catch(error => {
  console.error(error.stack || error);
  process.exit(1);
});
