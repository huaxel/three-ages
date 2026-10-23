#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const root = __dirname;
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const bundle = fs.readFileSync(path.join(root, "_build/default/main.bc.js"), "utf8");
const embedded = fs.readFileSync(path.join(root, "_build/default/pilot_data.ml"), "utf8");
const structural = fs.readFileSync(path.join(root, "_build/default/structural_data.ml"), "utf8");
const pilot = JSON.parse(fs.readFileSync(path.join(root, "../prototypes/three-ages/data/three-ages-pilot.json"), "utf8"));

const bundleBytes = Buffer.byteLength(bundle);
if (bundleBytes > 2_500_000) {
  throw new Error(`Bonsai bundle is not release-sized: ${bundleBytes.toLocaleString()} bytes`);
}

for (const expected of [
  "id=\"app\"",
  "_build/default/main.bc.js",
  "three-ages-image-review.csv",
  "three-ages-structural-review.csv",
  "three-ages-register-review.csv",
  "three-ages-pilot-export.csv",
  "source-inventory.json",
]) {
  if (!html.includes(expected)) throw new Error(`HTML shell missing ${expected}`);
}
if (!embedded.includes("source_id") || !embedded.includes("005")) {
  throw new Error("build did not embed canonical pilot JSON");
}
if (!structural.includes("crop_preview") || !structural.includes("1935")) {
  throw new Error("build did not embed structural crop JSON");
}
for (const expected of ["005", "009", "022", "023", "024", "026"]) {
  if (!pilot.records.some(record => record.source_id === expected)) {
    throw new Error(`canonical pilot snapshot missing case ${expected}`);
  }
}
if (!bundle.includes("No completed reviewer decisions.")) {
  throw new Error("bundle missing explicit pending-review state");
}
if (!bundle.includes("Draft facade review")) {
  throw new Error("bundle missing reactive draft-review form");
}
if (!bundle.includes("Draft remains incomplete")) {
  throw new Error("bundle missing draft completeness feedback");
}
if (!bundle.includes("Download draft JSON")) {
  throw new Error("bundle missing draft JSON export link");
}
console.log("Bonsai bundle smoke test passed");
